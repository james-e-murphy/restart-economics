# Paper

The manuscript and its build, in the house pipeline used for the author's other working papers:
a markdown source, pandoc with xelatex, a custom header for the title page and callouts, and a
build script that runs regression checks after typesetting.

    bash paper/build/build.sh            # reads results/, writes the manuscript and the PDF
    python paper/facts.py                # every number the text quotes, from results/, to facts.md

## Layout

    parts/          the manuscript's source, one file per group of sections; edit these
    assemble.py     joins the parts and sets each {{table ...}} and {{figure ...}} block from the
                    exhibits, and {{ladder ...}} and {{transfer ...}} from the ladder's own files,
                    so a table in the paper is the table exhibits/make.py or results/ hold
    Restart_Economics_Manuscript_v0_1_2026_09_21.md
                    the assembled manuscript, written by the build; do not edit by hand
    facts.py        selects, rounds and summarizes results/ into facts.md, the sheet the text is
                    written and checked against; it estimates nothing
    build/          the typesetting: build.sh, meta.yaml, the title page, headings, table and
                    callout styles, blocks.lua, and a copy of pandoc's LaTeX template

## What the build does

1. Runs `exhibits/make.py --bare` into `build/figures/`: every figure and table from the results,
   the figures without their own titles and notes, which the manuscript carries in its captions.
2. Assembles the manuscript from `parts/`. An exhibit whose results file does not exist yet is set
   as a note saying it is pending, and the build reports how many are.
3. Strips the internal front matter above the abstract and typesets `build/restart-economics.pdf`
   with pandoc and xelatex.
4. Checks the PDF: no doubled figure or table labels, no em or en dashes, no hyphen standing for
   a minus sign in a table, the AI disclosure present, every linked figure present, and no
   mention of any earlier draft.

Requirements: pandoc 3, a TeX distribution with xelatex, the Liberation fonts, poppler's
`pdftotext` and `pdfinfo`, and the Python environment the tests use.

## Conventions

- No em or en dashes anywhere; page ranges in the references take a hyphen.
- Negative numbers take the minus sign, U+2212; `assemble.py` converts the exhibits' hyphens.
- Inline math is `\( \)` and display math `\[ \]`; dollar signs are literal.
- A table's caption is the paragraph `Table: **Table N. Title.** ...` above it; a figure is
  `![Figure N](figures/name.pdf)` followed by a blockquote beginning `**Figure N. Title.**`.
- Anything not in the registered plan is called exploratory where it appears.
