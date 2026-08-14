"""
SQLite data layer for GSSBDC WING.

Real relational schema (tables, foreign keys, types) lives here.
load_data(filename) / save_data(filename, data) in core/helpers.py
keep their old signature (list-of-dicts in, list-of-dicts out) so
app.py and every module in modules/ work completely unchanged --
only the storage underneath moved from JSON files to SQLite.
"""

import sqlite3
import json
import os
from contextlib import contextmanager

from core.logging_config import get_logger
log = get_logger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "gssbdc.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT UNIQUE,
    password TEXT,
    type TEXT,
    title TEXT DEFAULT '',
    portfolio TEXT DEFAULT '',
    member_code TEXT DEFAULT '',
    department TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    deleted INTEGER DEFAULT 0,
    temp_permissions TEXT DEFAULT '[]',
    requests_managed INTEGER DEFAULT 0,
    blood_managed INTEGER DEFAULT 0,
    donors_contacted INTEGER DEFAULT 0,
    successful_cases INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS donors (
    id INTEGER PRIMARY KEY,
    donor_code TEXT,
    department TEXT,
    name TEXT NOT NULL,
    blood_group TEXT,
    phone TEXT,
    area TEXT,
    latitude REAL,
    longitude REAL,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY,
    blood_group TEXT,
    area TEXT,
    latitude REAL,
    longitude REAL,
    bags INTEGER DEFAULT 0,
    urgency TEXT,
    status TEXT DEFAULT 'Open',
    created_by INTEGER REFERENCES members(id),
    created_date TEXT,
    donation_date TEXT,
    managed_by INTEGER REFERENCES members(id),
    donor_id INTEGER REFERENCES donors(id),
    collected_bags INTEGER DEFAULT 0,
    completed_date TEXT,
    patient_problem TEXT,
    hemoglobin TEXT,
    donation_place TEXT,
    donation_time TEXT,
    contact TEXT
);

CREATE TABLE IF NOT EXISTS fulfillments (
    fid INTEGER PRIMARY KEY AUTOINCREMENT,
    id INTEGER,
    request_id INTEGER REFERENCES requests(id) ON DELETE CASCADE,
    donor_id INTEGER REFERENCES donors(id),
    donor_name TEXT,
    blood_group TEXT,
    bags INTEGER DEFAULT 0,
    source TEXT,
    managed_by INTEGER REFERENCES members(id),
    managed_by_name TEXT,
    recorded_by INTEGER,
    recorded_by_name TEXT,
    donation_id INTEGER,
    date TEXT
);

CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY,
    donor_id INTEGER REFERENCES donors(id),
    donor_name TEXT,
    blood_group TEXT,
    bags INTEGER DEFAULT 0,
    date TEXT,
    request_id INTEGER REFERENCES requests(id),
    source TEXT DEFAULT 'club',
    managed_by INTEGER REFERENCES members(id),
    managed_by_name TEXT,
    member_id INTEGER REFERENCES members(id),
    member_name TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    member_id INTEGER REFERENCES members(id),
    member_name TEXT,
    donor_id INTEGER REFERENCES donors(id),
    donor_name TEXT,
    blood_group TEXT,
    date TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY,
    title TEXT,
    message TEXT,
    priority TEXT,
    date TEXT,
    posted_by INTEGER REFERENCES members(id),
    posted_by_name TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS committees (
    id INTEGER PRIMARY KEY,
    start_date TEXT,
    end_date TEXT
);

CREATE TABLE IF NOT EXISTS titles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    sort_order INTEGER
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    sort_order INTEGER
);

CREATE INDEX IF NOT EXISTS idx_donors_blood_group ON donors(blood_group);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_donations_donor ON donations(donor_id);
CREATE INDEX IF NOT EXISTS idx_contacts_member ON contacts(member_id);
CREATE INDEX IF NOT EXISTS idx_fulfillments_request ON fulfillments(request_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate_missing_columns(conn)


def _migrate_missing_columns(conn):
    """CREATE TABLE IF NOT EXISTS won't add new columns to a table that
    already exists, so any column added to SCHEMA after the DB was first
    created needs an explicit ALTER TABLE here (safe to run every time --
    it only adds what's missing, existing data is untouched)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(requests)")}
    if "contact" not in existing:
        conn.execute("ALTER TABLE requests ADD COLUMN contact TEXT")

    # members: member_code + department (added later)
    mem_cols = {row["name"] for row in conn.execute("PRAGMA table_info(members)")}
    if "member_code" not in mem_cols:
        conn.execute("ALTER TABLE members ADD COLUMN member_code TEXT DEFAULT ''")
    if "department" not in mem_cols:
        conn.execute("ALTER TABLE members ADD COLUMN department TEXT DEFAULT ''")

    # fulfillments: extra fields the app stores on each entry
    ful_cols = {row["name"] for row in conn.execute("PRAGMA table_info(fulfillments)")}
    for col, coltype in [
        ("id", "INTEGER"),
        ("donor_name", "TEXT"),
        ("blood_group", "TEXT"),
        ("recorded_by", "INTEGER"),
        ("recorded_by_name", "TEXT"),
        ("donation_id", "INTEGER"),
    ]:
        if col not in ful_cols:
            conn.execute(f"ALTER TABLE fulfillments ADD COLUMN {col} {coltype}")

# ---------------------------------------------------------------
# Column definitions per table (order matters for INSERT)
# ---------------------------------------------------------------

COLUMNS = {
    "members": ["id", "name", "username", "password", "type", "title", "portfolio",
                "member_code", "department",
                "active", "phone", "email", "deleted", "temp_permissions",
                "requests_managed", "blood_managed", "donors_contacted", "successful_cases"],
    "donors": ["id", "donor_code", "department", "name", "blood_group", "phone",
                "area", "latitude", "longitude", "active"],
    "requests": ["id", "blood_group", "area", "latitude", "longitude", "bags", "urgency",
                "status", "created_by", "created_date", "donation_date", "managed_by",
                "donor_id", "collected_bags", "completed_date", "patient_problem",
                "hemoglobin", "donation_place", "donation_time", "contact"],
    "donations": ["id", "donor_id", "donor_name", "blood_group", "bags", "date",
                "request_id", "source", "managed_by", "managed_by_name",
                "member_id", "member_name", "status"],
    "contacts": ["id", "member_id", "member_name", "donor_id", "donor_name",
                "blood_group", "date", "status"],
    "notices": ["id", "title", "message", "priority", "date", "posted_by",
                "posted_by_name", "active"],
    "committees": ["id", "start_date", "end_date"],
}

BOOL_FIELDS = {
    "members": ["active", "deleted"],
    "donors": ["active"],
    "notices": ["active"],
}

FULFILLMENT_COLUMNS = [
    "request_id", "id", "donor_id", "donor_name", "blood_group", "bags",
    "source", "managed_by", "managed_by_name", "recorded_by", "recorded_by_name",
    "donation_id", "date"
]

# core/helpers.py *_FILE constants -> table name
FILE_TO_TABLE = {
    "data/donors.json": "donors",
    "data/donations.json": "donations",
    "data/requests.json": "requests",
    "data/members.json": "members",
    "data/contacts.json": "contacts",
    "data/notices.json": "notices",
    "data/committees.json": "committees",
}
SIMPLE_LIST_TABLES = {
    "data/titles.json": "titles",
    "data/departments.json": "departments",
}


def _row_to_dict(row, table):
    d = dict(row)
    for f in BOOL_FIELDS.get(table, []):
        if f in d:
            d[f] = bool(d[f])
    if table == "members" and "temp_permissions" in d:
        try:
            d["temp_permissions"] = json.loads(d["temp_permissions"] or "[]")
        except (TypeError, ValueError):
            d["temp_permissions"] = []
    return d

def db_load(table):
    try:
        with get_conn() as conn:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            records = [_row_to_dict(r, table) for r in rows]

            if table == "requests":
                fulfillments_by_req = {}
                try:
                    for f in conn.execute("SELECT * FROM fulfillments ORDER BY fid").fetchall():
                        fd = dict(f)
                        req_id = fd.pop("request_id", None)
                        fd.pop("fid", None)
                        if req_id is None:
                            continue
                        if fd.get("id") is None:
                            fd["id"] = fd.get("donation_id") or 0
                        fulfillments_by_req.setdefault(req_id, []).append(fd)
                except Exception as e:
                    log.warning("fulfillments_load_failed", error=str(e))
                    fulfillments_by_req = {}
                for r in records:
                    r["fulfillments"] = fulfillments_by_req.get(r["id"], [])

            return records
    except Exception as e:
        log.exception("db_load_failed", table=table, error=str(e))
        return []

def db_save(table, data):
    if table not in COLUMNS:
        log.warning("db_save_unknown_table", table=table)
        return
    if not isinstance(data, list):
        log.warning("db_save_invalid_data", table=table)
        return

    cols = COLUMNS[table]
    bool_fields = set(BOOL_FIELDS.get(table, []))

    try:
        with get_conn() as conn:
            # This function does a full delete+reinsert of the table on every
            # save. Several tables (donors, members, requests) are referenced
            # by other tables' foreign keys without ON DELETE CASCADE, so the
            # DELETE step alone would violate those constraints even though
            # every row gets reinserted with the same id a few lines later.
            # Relaxing enforcement for the duration of this single save
            # (delete + full reinsert) is safe: referential integrity is
            # restored before the transaction commits.
            conn.execute("PRAGMA foreign_keys = OFF")
            if table == "requests":
                conn.execute("DELETE FROM fulfillments")
            conn.execute(f"DELETE FROM {table}")

            for record in data:
                values = []
                for c in cols:
                    v = record.get(c)
                    if c in bool_fields:
                        v = 1 if v else 0
                    elif c == "temp_permissions":
                        v = json.dumps(v or [])
                    values.append(v)
                placeholders = ",".join("?" for _ in cols)
                conn.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                    values
                )

                if table == "requests":
                    for f in record.get("fulfillments", []) or []:
                        fvals = []
                        for c in FULFILLMENT_COLUMNS:
                            if c == "request_id":
                                fvals.append(record["id"])
                            else:
                                fvals.append(f.get(c))
                        try:
                            conn.execute(
                                f"INSERT INTO fulfillments ({','.join(FULFILLMENT_COLUMNS)}) VALUES ({','.join('?' for _ in FULFILLMENT_COLUMNS)})",
                                fvals
                            )
                        except Exception as e:
                            log.warning("fulfillment_insert_failed", error=str(e))

            conn.execute("PRAGMA foreign_keys = ON")
            # Catch any integrity problem that ON/OFF-relaxed inserts could
            # have papered over (e.g. a genuinely dangling reference to a
            # row that no longer exists anywhere) before it commits silently.
            bad = conn.execute("PRAGMA foreign_key_check").fetchall()
            if bad:
                raise sqlite3.IntegrityError(f"foreign_key_check failed: {bad}")

            if table == "requests":
                conn.execute("PRAGMA foreign_keys = ON")
    except Exception as e:
        log.exception("db_save_failed", table=table, error=str(e))
        raise


def db_load_simple_list(table):
    """titles.json / departments.json used to be a plain JSON list of strings."""
    with get_conn() as conn:
        rows = conn.execute(f"SELECT name FROM {table} ORDER BY sort_order, id").fetchall()
        return [r["name"] for r in rows]


def db_save_simple_list(table, data):
    with get_conn() as conn:
        conn.execute(f"DELETE FROM {table}")
        for i, name in enumerate(data):
            conn.execute(f"INSERT INTO {table} (name, sort_order) VALUES (?, ?)", (name, i))