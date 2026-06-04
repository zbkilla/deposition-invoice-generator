"""SQLite access layer. The database is a single file (data/invoices.db) -- a
real relational store with history, but zero servers and nothing to host. When
you outgrow it (Stage 2), only this module changes; the rest stays put."""

import sqlite3
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, schema_path: str) -> None:
    conn.executescript(Path(schema_path).read_text())
    conn.commit()


def upsert_job(conn, job: dict) -> None:
    conn.execute(
        """INSERT INTO jobs (job_id, case_caption, witness_name, depo_date,
               client_name, client_email, location, copies, expedite,
               e_transcript, rough_draft, notes)
           VALUES (:job_id,:case_caption,:witness_name,:depo_date,:client_name,
               :client_email,:location,:copies,:expedite,:e_transcript,
               :rough_draft,:notes)
           ON CONFLICT(job_id) DO UPDATE SET
               case_caption=excluded.case_caption,
               witness_name=excluded.witness_name,
               depo_date=excluded.depo_date,
               client_name=excluded.client_name,
               client_email=excluded.client_email,
               location=excluded.location,
               copies=excluded.copies,
               expedite=excluded.expedite,
               e_transcript=excluded.e_transcript,
               rough_draft=excluded.rough_draft,
               notes=excluded.notes""",
        job,
    )


def delete_sessions(conn, job_ids) -> None:
    for jid in job_ids:
        conn.execute("DELETE FROM sessions WHERE job_id = ?", (jid,))


def add_session(conn, job_id, session_date, start_time, end_time) -> None:
    conn.execute(
        "INSERT INTO sessions (job_id, session_date, start_time, end_time) VALUES (?,?,?,?)",
        (job_id, session_date, start_time, end_time),
    )


def get_job(conn, job_id):
    return conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()


def get_sessions(conn, job_id):
    return conn.execute(
        "SELECT * FROM sessions WHERE job_id = ? ORDER BY session_date, start_time",
        (job_id,),
    ).fetchall()


def replace_documents(conn, job_id, docs) -> None:
    conn.execute("DELETE FROM documents WHERE job_id = ?", (job_id,))
    conn.executemany(
        "INSERT INTO documents (job_id, doc_type, file_path, page_count) VALUES (?,?,?,?)",
        [(job_id, dt, fp, pc) for (dt, fp, pc) in docs],
    )


def save_invoice(conn, job_id, created_at, subtotal, total, line_items) -> int:
    cur = conn.execute(
        "INSERT INTO invoices (job_id, created_at, subtotal, total, status) "
        "VALUES (?,?,?,?, 'draft')",
        (job_id, created_at, subtotal, total),
    )
    invoice_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO line_items (invoice_id, description, quantity, unit, unit_price, amount) "
        "VALUES (?,?,?,?,?,?)",
        [(invoice_id, d, q, u, up, amt) for (d, q, u, up, amt) in line_items],
    )
    return invoice_id


def list_jobs(conn):
    return conn.execute(
        "SELECT job_id, depo_date, case_caption FROM jobs ORDER BY depo_date DESC, job_id"
    ).fetchall()
