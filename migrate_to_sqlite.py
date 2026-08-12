"""
One-time migration: reads the existing data/*.json files and loads
them into data/gssbdc.db (SQLite). Safe to re-run -- each table is
fully replaced from the JSON on every run, so it will not duplicate
rows. Run this once after pulling the SQLite changes:

    python migrate_to_sqlite.py

After this succeeds, the app reads/writes only the SQLite database.
The original data/*.json files are left untouched as a backup.
"""

import json
import os
from core import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = {
    "donors": "data/donors.json",
    "donations": "data/donations.json",
    "requests": "data/requests.json",
    "members": "data/members.json",
    "contacts": "data/contacts.json",
    "notices": "data/notices.json",
    "committees": "data/committees.json",
}
SIMPLE_LIST_FILES = {
    "titles": "data/titles.json",
    "departments": "data/departments.json",
}


def load_json(path):
    full = os.path.join(BASE_DIR, path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def main():
    print("Setting up SQLite schema at:", db.DB_PATH)
    db.init_db()

    for table, path in FILES.items():
        rows = load_json(path)
        db.db_save(table, rows)
        print(f"  {table:12s} <- {len(rows)} record(s) from {path}")

    for table, path in SIMPLE_LIST_FILES.items():
        rows = load_json(path)
        db.db_save_simple_list(table, rows)
        print(f"  {table:12s} <- {len(rows)} record(s) from {path}")

    print("Migration complete.")


if __name__ == "__main__":
    main()