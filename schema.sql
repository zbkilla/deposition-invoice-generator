PRAGMA foreign_keys = ON;

-- One row per deposition job (the unit you invoice).
CREATE TABLE IF NOT EXISTS jobs (
    job_id        TEXT PRIMARY KEY,
    case_caption  TEXT,
    witness_name  TEXT,
    depo_date     TEXT,                  -- ISO date YYYY-MM-DD
    client_name   TEXT,
    client_email  TEXT,
    location      TEXT,
    copies        INTEGER DEFAULT 0,     -- number of certified copies ordered
    expedite      TEXT    DEFAULT 'none',-- none | daily | same_day
    e_transcript  INTEGER DEFAULT 0,     -- 0/1 flag
    rough_draft   INTEGER DEFAULT 0,     -- 0/1 flag
    notes         TEXT
);

-- One row per on-record session. A job may have several (morning/afternoon,
-- multiple days). This is what drives appearance + after-hours math.
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    session_date TEXT,                   -- ISO date; lets one job span days
    start_time   TEXT,                   -- HH:MM 24-hour
    end_time     TEXT                    -- HH:MM 24-hour
);

-- One row per PDF found on the Egnyte drive, with its page count.
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    doc_type    TEXT NOT NULL,           -- transcript | exhibit
    file_path   TEXT NOT NULL,
    page_count  INTEGER,                 -- NULL if the file could not be read
    UNIQUE(job_id, file_path)
);

-- One row per generated draft. Permanent record of what was billed and when.
CREATE TABLE IF NOT EXISTS invoices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,           -- ISO timestamp
    subtotal    REAL NOT NULL,
    total       REAL NOT NULL,
    status      TEXT DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS line_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    quantity    REAL NOT NULL,
    unit        TEXT,
    unit_price  REAL NOT NULL,
    amount      REAL NOT NULL
);
