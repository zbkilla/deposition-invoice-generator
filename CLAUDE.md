# CLAUDE.md

Guidance for AI agents working in this repository.

## What this is

A Stage 0 draft-invoice generator for court-reporting / deposition jobs. It
reads PDF page counts and per-job data, applies a rate card, and renders a draft
invoice for human review.

## The cardinal rule

**Never feed a PDF (or its pages) to a language model.** Page counts come from
the PDF structure only, via `pypdf` in `invoice/pdfcount.py` — this is what
makes the tool free to run and able to handle huge transcripts. Do not add any
code path that sends PDF content to an AI model for counting, parsing, or
"reading." If unstructured extraction is ever truly needed (e.g. start/end times
when no CSV provides them), extract the specific page text with code first and
only escalate the smallest possible slice.

## Architecture

```
cli.py            entry point: initdb | import-jobs | invoice | list-jobs
invoice/
  pdfcount.py     count_pages() -- structure-only, no AI
  egnyte.py       collect_documents() -- find a job's PDFs on the mounted drive
  billing.py      build_line_items() / totals() -- pure arithmetic over rates.yaml
  render.py       render_invoice() -- fill a Jinja2 template
  db.py           SQLite access layer
schema.sql        tables: jobs, sessions, documents, invoices, line_items
config.yaml       paths, folder convention, firm info, template choice  (DATA)
rates.yaml        prices and billing rules                              (DATA)
templates/        invoice.md.j2 (default), invoice.html.j2 (branded)    (LAYOUT)
```

Data flow: `import-jobs` loads `jobs`/`sessions` from a CSV -> `invoice` finds
PDFs, counts pages, computes line items from `rates.yaml`, stores the invoice,
and renders a draft into `output/`.

## Run and test

```sh
uv run cli.py initdb
uv run cli.py import-jobs sample_jobs.csv
uv run cli.py invoice --job JOB1001                                   # markdown
uv run cli.py invoice --job JOB1001 --template templates/invoice.html.j2  # HTML
```

`sample_jobs.csv` + `sample_egnyte/` are a self-contained fixture; JOB1001
should total `$1,005.00` and JOB1002 `$721.00`. Use these as a regression check
after changing `billing.py`.

## Conventions

- **uv** for everything: `uv run cli.py ...`. Dependencies live in
  `pyproject.toml`; do not use system Python or pip.
- **Configuration is data.** Pricing changes go in `rates.yaml`, layout changes
  go in `templates/*.j2`. Avoid hardcoding either in Python.
- **Billing rules** belong in `billing.py`; keep each rule readable and driven
  by a `rates.yaml` key so it can be toggled with a price of `0`.
- **Storage** is `data/invoices.db` (SQLite). When the project graduates to a
  cloud/hosted database, only `db.py` should change.
- **Drive access** is `egnyte.py`. Files are read in place from a mounted drive;
  nothing is downloaded or copied. Swapping to a drive API touches only this
  module.

## Do not

- Do not commit `data/` or `output/` (gitignored) or any real client data —
  `sample_*` content is fabricated and safe to publish.
- Do not add documentation files unless asked.
- Do not introduce an AI/LLM dependency for the core counting/billing path.
