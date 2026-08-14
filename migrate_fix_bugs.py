"""
One-time migration script — run this ONCE against your real data/gssbdc.db
before deploying the fixed app.py / db.py / donation.py.

What it does:
1. Adds the missing columns to the `fulfillments` table (id, donor_name,
   blood_group, recorded_by, recorded_by_name, donation_id) — these existed
   in the code's CREATE TABLE statement but were never migrated onto your
   already-existing database file, so every "add donor to request" was
   silently failing to save.
2. Fixes any member row where requests_managed / blood_managed /
   successful_cases / donors_contacted is NULL instead of 0 (this crashed
   the app with a 500 error whenever that member completed a request).

Safe to run multiple times — every step checks before changing anything.

Usage:
    python migrate_fix_bugs.py
(run it from the project root, where data/gssbdc.db lives — or edit DB_PATH below)
"""

import sqlite3
import os

DB_PATH = os.path.join("data", "gssbdc.db")

def main():
    if not os.path.exists(DB_PATH):
        print(f"Could not find {DB_PATH} — edit DB_PATH in this script if your db lives elsewhere.")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # --- Step 1: add missing fulfillments columns ---
    cur.execute("PRAGMA table_info(fulfillments)")
    existing_cols = {row[1] for row in cur.fetchall()}

    needed = [
        ("id", "INTEGER"),
        ("donor_name", "TEXT"),
        ("blood_group", "TEXT"),
        ("recorded_by", "INTEGER"),
        ("recorded_by_name", "TEXT"),
        ("donation_id", "INTEGER"),
    ]
    added = []
    for col, typ in needed:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE fulfillments ADD COLUMN {col} {typ}")
            added.append(col)
    if added:
        print(f"fulfillments table: added missing columns -> {added}")
    else:
        print("fulfillments table: already up to date, nothing to add")

    # --- Step 2: fix NULL member stat fields ---
    stat_cols = ["requests_managed", "blood_managed", "successful_cases", "donors_contacted"]
    total_fixed = 0
    for col in stat_cols:
        cur.execute(f"SELECT COUNT(*) FROM members WHERE {col} IS NULL")
        n = cur.fetchone()[0]
        if n:
            cur.execute(f"UPDATE members SET {col} = 0 WHERE {col} IS NULL")
            total_fixed += n
    if total_fixed:
        print(f"members table: fixed {total_fixed} NULL stat value(s) -> set to 0")
    else:
        print("members table: no NULL stat values found, nothing to fix")

    con.commit()

    # --- Step 3: sanity check ---
    cur.execute("PRAGMA foreign_key_check")
    problems = cur.fetchall()
    if problems:
        print("WARNING: foreign_key_check found existing problems (unrelated to this migration):")
        print(problems)
    else:
        print("Foreign key integrity check: OK")

    con.close()
    print("\nDone. You can now deploy the updated app.py / core/db.py / modules/donation.py.")

if __name__ == "__main__":
    main()