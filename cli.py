"""Stage 0 draft-invoice generator -- command-line entry point.

Usage (from this folder):
    uv run cli.py initdb                      # create the SQLite database
    uv run cli.py import-jobs sample_jobs.csv # load job + session data
    uv run cli.py invoice --job JOB1001       # count PDFs, compute, write draft
    uv run cli.py list-jobs                   # show loaded jobs

No part of this reads PDF *content*: page counts come from the file structure
only, so generating invoices costs nothing in AI tokens/coins."""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import yaml

from invoice import db
from invoice.billing import build_line_items, totals
from invoice.egnyte import collect_documents
from invoice.render import render_invoice, write_draft

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"
RATES_PATH = ROOT / "rates.yaml"
SCHEMA_PATH = ROOT / "schema.sql"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _truthy(value) -> int:
    return 1 if str(value or "").strip().lower() in {"1", "y", "yes", "true"} else 0


def cmd_initdb(args, cfg) -> None:
    conn = db.connect(cfg["database"])
    db.init_db(conn, str(SCHEMA_PATH))
    print(f"Initialized database at {cfg['database']}")


def cmd_import_jobs(args, cfg) -> None:
    conn = db.connect(cfg["database"])
    db.init_db(conn, str(SCHEMA_PATH))

    jobs: dict[str, dict] = {}
    sessions: list[tuple] = []
    with open(args.csv, newline="") as fh:
        for row in csv.DictReader(fh):
            jid = (row.get("job_id") or "").strip()
            if not jid:
                continue
            if jid not in jobs:
                jobs[jid] = {
                    "job_id": jid,
                    "case_caption": (row.get("case_caption") or "").strip(),
                    "witness_name": (row.get("witness_name") or "").strip(),
                    "depo_date": (row.get("depo_date") or "").strip(),
                    "client_name": (row.get("client_name") or "").strip(),
                    "client_email": (row.get("client_email") or "").strip(),
                    "location": (row.get("location") or "").strip(),
                    "copies": int(row.get("copies") or 0),
                    "expedite": (row.get("expedite") or "none").strip() or "none",
                    "e_transcript": _truthy(row.get("e_transcript")),
                    "rough_draft": _truthy(row.get("rough_draft")),
                    "notes": (row.get("notes") or "").strip(),
                }
            start = (row.get("start_time") or "").strip()
            end = (row.get("end_time") or "").strip()
            if start or end:
                session_date = (row.get("session_date") or row.get("depo_date") or "").strip()
                sessions.append((jid, session_date, start, end))

    db.delete_sessions(conn, list(jobs.keys()))
    for job in jobs.values():
        db.upsert_job(conn, job)
    for jid, sdate, start, end in sessions:
        db.add_session(conn, jid, sdate, start, end)
    conn.commit()
    print(f"Imported {len(jobs)} job(s), {len(sessions)} session(s).")


def cmd_invoice(args, cfg) -> None:
    rates = _load_yaml(RATES_PATH)
    if args.template:
        override = Path(args.template)
        cfg = {**cfg, "template": str(override if override.is_absolute() else ROOT / override)}
    conn = db.connect(cfg["database"])

    job = db.get_job(conn, args.job)
    if job is None:
        sys.exit(f"No job '{args.job}' in the database. Run import-jobs first.")

    sessions = db.get_sessions(conn, args.job)
    docs = collect_documents(cfg, args.job)
    db.replace_documents(conn, args.job, [(d.doc_type, d.file_path, d.page_count) for d in docs])

    items = build_line_items(job, sessions, docs, rates)
    subtotal, total = totals(items)

    now = datetime.now()
    created_at = now.isoformat(timespec="seconds")
    stamp = now.strftime("%Y%m%d-%H%M%S")
    db.save_invoice(conn, args.job, created_at, subtotal, total,
                    [(i.description, i.quantity, i.unit, i.unit_price, i.amount) for i in items])
    conn.commit()

    text = render_invoice(cfg, rates.get("currency", "USD"), job, sessions, docs,
                          items, subtotal, total, created_at)
    path = write_draft(cfg, args.job, stamp, text)

    t_pages = sum(d.page_count or 0 for d in docs if d.doc_type == "transcript")
    e_pages = sum(d.page_count or 0 for d in docs if d.doc_type == "exhibit")
    print(f"Job {args.job}: {t_pages} transcript pages, {e_pages} exhibit pages, "
          f"{len(sessions)} session(s)")
    for d in docs:
        if d.page_count is None:
            print(f"  WARNING unreadable: {d.file_path} ({d.error})")
    print(f"Draft total: ${total:,.2f}")
    print(f"Draft written to: {path}")


def cmd_list_jobs(args, cfg) -> None:
    conn = db.connect(cfg["database"])
    for row in db.list_jobs(conn):
        print(f"{row['job_id']:>10}  {row['depo_date'] or '':>10}  {row['case_caption'] or ''}")


def main() -> None:
    cfg = _load_yaml(CONFIG_PATH)
    parser = argparse.ArgumentParser(prog="invoice",
                                     description="Stage 0 draft-invoice generator")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("initdb", help="create the SQLite database")
    p_import = sub.add_parser("import-jobs", help="load jobs + sessions from a CSV")
    p_import.add_argument("csv", help="path to a jobs CSV (see sample_jobs.csv)")
    p_invoice = sub.add_parser("invoice", help="generate a draft invoice for one job")
    p_invoice.add_argument("--job", required=True, help="job id to invoice")
    p_invoice.add_argument("--template", help="override the template file from config.yaml")
    sub.add_parser("list-jobs", help="list loaded jobs")

    args = parser.parse_args()
    handlers = {
        "initdb": cmd_initdb,
        "import-jobs": cmd_import_jobs,
        "invoice": cmd_invoice,
        "list-jobs": cmd_list_jobs,
    }
    handlers[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
