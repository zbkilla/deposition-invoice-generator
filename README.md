# invoice-generator

A draft-invoice generator for court-reporting / deposition jobs.

It assembles a rough-draft invoice from two cheap, deterministic sources:

- **PDF page counts** for transcripts and exhibits, read straight off the file
  structure with [`pypdf`](https://pypi.org/project/pypdf/).
- **Job data** (sessions, times, flags) from a CSV you export from your
  scheduling spreadsheet or court-reporting software.

It then applies a rate card and writes a draft you review before sending.

## Why it is cheap

The expensive, slow way to "read" a PDF is to feed it to an AI model, which
turns every page into image + text tokens. A long transcript can cost a fortune
in tokens and may not even fit.

This tool never does that. Page counts come from the PDF's internal structure
only (`len(reader.pages)`) — nothing is sent to any model. A 5,000-page
transcript costs the same as a 5-page exhibit: zero tokens, instant. The only
thing a human (or an AI assistant) does is build and maintain the code; running
it is free.

## Layout

```
invoice-generator/
├── config.yaml          # paths, folder convention, firm info, template choice
├── rates.yaml           # prices and billing rules (data, not code)
├── sample_jobs.csv      # the jobs CSV format (one row per session)
├── schema.sql           # SQLite schema
├── cli.py               # command-line entry point
├── invoice/
│   ├── pdfcount.py      # PDF page counting (the free, no-AI part)
│   ├── egnyte.py        # finds a job's PDFs on the mounted drive
│   ├── billing.py       # applies rates -> line items (pure arithmetic)
│   ├── render.py        # fills a template with the computed invoice
│   └── db.py            # SQLite access layer
├── templates/
│   ├── invoice.md.j2    # simple markdown draft (default)
│   └── invoice.html.j2  # branded, print/PDF-ready invoice
└── sample_egnyte/       # fixture PDFs so the demo runs out of the box
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (manages the venv and dependencies)

## Quick start

```sh
uv run cli.py initdb                       # create the SQLite database
uv run cli.py import-jobs sample_jobs.csv  # load jobs + sessions
uv run cli.py invoice --job JOB1001        # count PDFs, compute, write a draft
uv run cli.py list-jobs                    # list loaded jobs
```

Drafts are written to `output/`. For a branded HTML invoice:

```sh
uv run cli.py invoice --job JOB1001 --template templates/invoice.html.j2
```

Convert the HTML draft to a PDF (requires `weasyprint`):

```sh
weasyprint output/invoice_JOB1001_<stamp>.html output/invoice_JOB1001_<stamp>.pdf
```

## Configuration

Everything you change to fit your firm is **data, not code**:

- **`config.yaml`** — the path to your mounted file drive (e.g. Egnyte), the
  per-job folder convention, your firm details, and which template to use.
  Files are read in place; nothing is downloaded or copied.
- **`rates.yaml`** — every price and rule. Turn a line off by setting its price
  to `0`. The numbers shipped here are examples; replace them.

### Jobs CSV format

One row per on-record session (a job with two sessions gets two rows that share
a `job_id`). Columns:

```
job_id, case_caption, witness_name, depo_date, client_name, client_email,
location, copies, expedite, e_transcript, rough_draft,
session_date, start_time, end_time, notes
```

`expedite` is `none | daily | same_day`; `e_transcript` and `rough_draft` are
yes/no flags. See `sample_jobs.csv`.

### Folder convention

Under the drive root, each job's PDFs live at:

```
<egnyte_root>/<job_id>/transcripts/*.pdf
<egnyte_root>/<job_id>/exhibits/*.pdf
```

This lets the tool match the right PDFs to a job with no guessing.

## Templates

The invoice layout lives in `templates/*.j2`, not in the code. Edit those to
restyle the invoice without touching Python. Values available in a template:

| In the template | Meaning |
|---|---|
| `firm.name / address / phone / email` | from `config.yaml` |
| `job.*` | job fields (`job_id`, `case_caption`, `witness_name`, ...) |
| `sessions` | loop of `{session_date, start_time, end_time}` |
| `docs.transcript_pages / exhibit_pages / unreadable` | page totals |
| `items` | loop of `{description, quantity, unit, unit_price, amount}` |
| `subtotal`, `total`, `currency`, `created_at` | totals and meta |
| `value | money` | formats a number as `$1,234.50` |

## Data model

SQLite (`data/invoices.db`) — a real relational store with history, but no
server to run. Tables: `jobs`, `sessions`, `documents`, `invoices`,
`line_items`. Every generated draft is recorded.

## Roadmap

- **Stage 0 (this repo):** local script, reads a mounted drive, SQLite store,
  run on demand. Zero hosting, zero per-invoice cost.
- **Stage 2:** small cloud server + hosted database + drive API, for unattended
  scheduling or multi-user access. Only `egnyte.py` and `db.py` need to change.
- **Stage 3:** web UI / event-triggered generation, if this becomes a product.

Climb only when real pain (concurrent edits, unattended runs, volume) demands
it — not for the appeal of "fully automated."
