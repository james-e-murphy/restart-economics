#!/usr/bin/env bash
# Build the Restart Economics PDF from the manuscript's parts and the results.
#   usage: bash paper/build/build.sh [results-dir]     (default: results/)
# Writes paper/Restart_Economics_Manuscript_v0_1_2026_09_21.md and paper/build/restart-economics.pdf.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESULTS="$(cd "${1:-$ROOT/results}" && pwd)"
PY="${PYTHON:-python3}"
cd "$ROOT/paper/build"

# 1. exhibits: every figure and table from the results, figures without their own titles and
#    notes, which the manuscript carries in its captions
"$PY" "$ROOT/exhibits/make.py" --results "$RESULTS" --out figures --bare > /dev/null

# 2. the manuscript: parts, tables and figures assembled into one markdown file
"$PY" "$ROOT/paper/assemble.py" --exhibits figures

# 3. body: strip the internal front matter above the abstract
"$PY" - <<'PY'
import glob
src = glob.glob("../Restart_Economics_Manuscript_*.md")
assert len(src) == 1, src
s = open(src[0]).read()
i = s.find("# Abstract")
assert i > 0, "no '# Abstract' heading found; front matter cannot be stripped"
open("body.md", "w").write(s[i:])
PY

# 4. typeset
pandoc meta.yaml body.md -o restart-economics.pdf \
  --pdf-engine=xelatex -H header.tex --template=default.latex \
  -f markdown+tex_math_single_backslash-tex_math_dollars-implicit_figures \
  --lua-filter=blocks.lua

# 5. checks that have caught real defects before
"$PY" - <<'PY'
import os, re, subprocess, sys
subprocess.run(["pdftotext", "restart-economics.pdf", "_t.txt"], check=True)
t = open("_t.txt").read()
body = open("body.md").read()
bad = []
def check(name, ok):
    print(("  ok    " if ok else "  FAIL  ") + name)
    if not ok:
        bad.append(name)
check("no double figure labels", not re.search(r"Figure [A-Z]?\d+: Figure [A-Z]?\d+", t))
check("no double table labels", not re.search(r"Table [A-Z]?\d+: Table", t))
check("no em or en dashes", not any(c in t or c in body for c in "—–"))
check("no hyphen-minus before a number in a table", not re.search(r"^\|.*(?<![\w.])-\d", body, re.M))
check("AI disclosure present", "Declaration of generative AI" in t)
check("every figure linked exists", all(os.path.exists(f) for f in
                                        re.findall(r"\]\((figures/[^)]+)\)", body)))
check("no unrendered blocks", "{{" not in body)
check("stands alone", "Beyond Average Cost" not in body)
pending = len(re.findall(r"^> Pending", body, re.M))
print(f"  note  {pending} exhibit(s) pending their results files")
sys.exit(1 if bad else 0)
PY
echo "built: $(pdfinfo restart-economics.pdf | grep -i '^pages')"
