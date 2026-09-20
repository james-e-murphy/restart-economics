"""Acquire the trajectory archives and extract each one, keeping no archive by default.

Reads Hugging Face's own listing of the dataset, so no file name is typed by hand, and takes
every ``.tar.gz`` except the ``_mini`` ones. Each archive is extracted from a local copy when one
is given, and otherwise streamed from Hugging Face through the extractor. While it streams, a
temporary copy is written to disk and hashed; it is deleted once the extraction succeeds and the
hash matches, and kept if either fails, so a failed extraction can be rerun locally without
downloading again.

Every archive's SHA-256 is compared with the one Hugging Face records for the file (the LFS
object id, which is the SHA-256 of the content), and ``archives/SHA256SUMS`` is written.

    python -m restart.acquire --local ~/Downloads/archives --out data/derived
    python -m restart.acquire --only kimi-k2_4runs.tar.gz          # one archive
    python -m restart.acquire --local archives/.partial --only X    # rerun a kept copy
    python -m restart.acquire --sums-only --local ~/Downloads/archives

``--sums-only`` rewrites ``archives/SHA256SUMS`` without extracting anything: each archive's
checksum comes from its extraction's own record (every table records the SHA-256 of the stream
it was read from), or, for an archive that did not extract, from hashing the local copy, and is
recorded only where it equals the value Hugging Face records.

Each archive's tables go to ``<out>/<archive name without .tar.gz>/`` with its extraction log,
so two archives of the same model cannot overwrite each other.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

REPO = "loong0814/openhands_trajectories"
TREE = f"https://huggingface.co/api/datasets/{REPO}/tree/main"
FILE = f"https://huggingface.co/datasets/{REPO}/resolve/main/{{name}}?download=true"


def listing() -> list[dict]:
    out = subprocess.run(["curl", "-sfL", TREE], check=True, capture_output=True).stdout
    return json.loads(out)


def full_archives(tree: list[dict]) -> list[dict]:
    """Every full archive in the listing, with its size and recorded SHA-256."""
    rows = []
    for f in tree:
        name = f.get("path", "")
        if f.get("type") == "file" and name.endswith(".tar.gz") and not name.endswith("_mini.tar.gz"):
            lfs = f.get("lfs") or {}
            rows.append(dict(name=name, size=lfs.get("size", f.get("size")), sha256=lfs.get("oid")))
    return sorted(rows, key=lambda r: r["name"])


def stream(source_cmd: list[str], tmp: pathlib.Path, out: pathlib.Path, log) -> dict:
    """Pipe ``source_cmd``'s output into the extractor while copying and hashing it to ``tmp``.
    If the extractor stops early the copy continues, so ``tmp`` is complete whenever the
    source is."""
    tmp.parent.mkdir(parents=True, exist_ok=True)
    src = subprocess.Popen(source_cmd, stdout=subprocess.PIPE)
    ext = subprocess.Popen([sys.executable, "-m", "restart.extract", "-", "--out", str(out)],
                           stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    h, n, alive = hashlib.sha256(), 0, True
    with open(tmp, "wb") as fh:
        for chunk in iter(lambda: src.stdout.read(1 << 20), b""):
            fh.write(chunk)
            h.update(chunk)
            n += len(chunk)
            if alive:
                try:
                    ext.stdin.write(chunk)
                except BrokenPipeError:
                    alive = False
    try:
        ext.stdin.close()
    except BrokenPipeError:
        pass
    return dict(source_rc=src.wait(), extract_rc=ext.wait(), sha256=h.hexdigest(), bytes=n)


def extracted_sha(out: pathlib.Path) -> set[str]:
    return {json.load(open(p)).get("archive_sha256") for p in out.glob("audit_*.json")}


def file_sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sums(results: list[dict]) -> None:
    """Merge verified checksums into archives/SHA256SUMS. A checksum is recorded only when it equals
    the one Hugging Face records, even if the archive's layout defeated the extractor."""
    sums = pathlib.Path("archives/SHA256SUMS")
    have = {}
    if sums.exists():
        for line in sums.read_text().splitlines():
            if line and not line.startswith("#") and len(line.split()) == 2:
                have[line.split()[1]] = line.split()[0]
    for x in results:
        if x["sha256"] and x["sha256"] == x["expected"]:
            have[x["name"]] = x["sha256"]
    sums.write_text("# Checksums of the raw trajectory archives, verified against the SHA-256 Hugging Face\n"
                    "# records for each file (archives/hf_tree.json). The archives are not committed.\n"
                    "# Format: sha256  filename\n" + "".join(f"{v}  {k}\n" for k, v in sorted(have.items())))


def sums_only(todo: list[dict], out_root: str, local_dir: str | None) -> int:
    results = []
    for r in todo:
        shas = extracted_sha(pathlib.Path(out_root) / r["name"][: -len(".tar.gz")])
        sha, source = (next(iter(shas)), "extraction record") if len(shas) == 1 else (None, None)
        local = pathlib.Path(local_dir).expanduser() / r["name"] if local_dir else None
        if sha is None and local is not None and local.exists():
            sha, source = file_sha(local), "local copy"
        verdict = ("no extraction record and no local copy" if sha is None else
                   "matches" if sha == r["sha256"] else "DIFFERS")
        print(f"{r['name']}: {verdict}" + (f" ({source})" if source else ""), flush=True)
        results.append(dict(name=r["name"], sha256=sha, expected=r["sha256"]))
    write_sums(results)
    bad = sum(x["sha256"] is None or x["sha256"] != x["expected"] for x in results)
    print(f"\n{len(results) - bad} of {len(results)} checksums verified and recorded")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", help="folder holding archives already downloaded; used when a file is there")
    ap.add_argument("--out", default="data/derived", help="where each archive's tables go")
    ap.add_argument("--tmp", default="archives/.partial", help="where streamed copies are held until verified")
    ap.add_argument("--only", nargs="*", help="archive file names to process; default all full archives")
    ap.add_argument("--keep", action="store_true", help="keep streamed copies after a verified extraction")
    ap.add_argument("--sums-only", action="store_true",
                    help="rewrite archives/SHA256SUMS from the extraction records and local copies; extract nothing")
    a = ap.parse_args(argv)

    saved = pathlib.Path("archives/hf_tree.json")
    if a.sums_only and saved.exists():
        tree = json.loads(saved.read_text())          # the listing the archives were acquired against
    else:
        tree = listing()
        pathlib.Path("archives").mkdir(exist_ok=True)
        saved.write_text(json.dumps(tree, indent=2))
    todo = [r for r in full_archives(tree) if not a.only or r["name"] in a.only]
    if a.only and len(todo) != len(a.only):
        sys.exit(f"not in the listing: {sorted(set(a.only) - {r['name'] for r in todo})}")
    if a.sums_only:
        return sums_only(todo, a.out, a.local)
    print(f"{len(todo)} archives, {sum(r['size'] or 0 for r in todo) / 1e9:.1f} GB", flush=True)

    results = []
    for r in todo:
        stem = r["name"][: -len(".tar.gz")]
        out = pathlib.Path(a.out) / stem
        out.mkdir(parents=True, exist_ok=True)
        for old in list(out.glob("*.csv")) + list(out.glob("audit_*.json")):
            old.unlink()                              # a rerun never mixes with a previous one
        local = pathlib.Path(a.local).expanduser() / r["name"] if a.local else None
        print(f"{r['name']}: {'local copy' if local and local.exists() else 'streaming'} "
              f"({(r['size'] or 0) / 1e9:.1f} GB)", flush=True)
        with open(out / "extract.log", "w") as log:
            if local and local.exists():
                rc = subprocess.run([sys.executable, "-m", "restart.extract", str(local), "--out", str(out)],
                                    stdout=log, stderr=subprocess.STDOUT).returncode
                got = dict(source_rc=0, extract_rc=rc, sha256=None, bytes=local.stat().st_size)
                tmp = None
            else:
                tmp = pathlib.Path(a.tmp) / r["name"]
                got = stream(["curl", "-sfL", FILE.format(name=r["name"])], tmp, out, log)
        shas = extracted_sha(out)
        if got["sha256"] is None and not shas and local is not None and local.exists():
            got["sha256"] = file_sha(local)           # nothing extracted: hash the file itself
        sha = got["sha256"] or (next(iter(shas)) if len(shas) == 1 else None)
        expected = r["sha256"]                         # None if Hugging Face records none
        sha_ok = len(shas) == 1 and (expected is None or (sha == expected and shas == {expected}))
        ok = got["source_rc"] == 0 and got["extract_rc"] == 0 and sha_ok
        if tmp is not None and ok and not a.keep:
            tmp.unlink()
        status = ("ok" if ok else "download failed" if got["source_rc"] else
                  "extraction failed" if got["extract_rc"] else "no runs found" if not shas else "checksum mismatch")
        results.append(dict(name=r["name"], status=status, sha256=sha, expected=r["sha256"],
                            kept=str(tmp) if tmp is not None and tmp.exists() else None))
        tail = (out / "extract.log").read_text().strip().splitlines()[-2:]
        verdict = "not recorded by Hugging Face" if expected is None else "matches" if sha == expected else "DIFFERS"
        print(f"  {status}; sha256 {verdict}"
              + (f"; copy kept at {tmp}" if results[-1]["kept"] else "") + "\n  " + "\n  ".join(tail), flush=True)

    write_sums(results)
    bad = [x for x in results if x["status"] != "ok"]
    print(f"\n{len(results) - len(bad)} of {len(results)} archives verified and extracted"
          + ("".join(f"\n  {x['name']}: {x['status']}" for x in bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
