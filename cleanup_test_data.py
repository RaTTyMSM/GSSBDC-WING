"""
Cleanup script — finds and removes TEST data (donors, members, requests,
and everything linked to them) whose name/username starts with "test"
(case-insensitive, e.g. "Test Donor One", "test_admin").

SAFE BY DESIGN:
  - Step 1 only PRINTS what it found. Nothing is deleted yet.
  - You must type "yes" to actually delete.
  - Only rows matching the "test" pattern (and things that reference them)
    are touched. Real data is never matched unless it happens to start
    with the word "test", so double-check the preview before confirming.

Usage:
    python cleanup_test_data.py
(run from the project root, where data/gssbdc.db lives)
"""

import sqlite3
import os

DB_PATH = os.path.join("data", "gssbdc.db")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Could not find {DB_PATH} — edit DB_PATH in this script if your db lives elsewhere.")
        return

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = OFF")
    cur = con.cursor()

    # --- find matching test donors and members ---
    cur.execute("SELECT id, name FROM donors WHERE name LIKE 'test%'")
    test_donors = cur.fetchall()
    donor_ids = [d[0] for d in test_donors]

    cur.execute("SELECT id, name, username FROM members WHERE name LIKE 'test%' OR username LIKE 'test%'")
    test_members = cur.fetchall()
    member_ids = [m[0] for m in test_members]

    # requests linked to a test donor/member, or that look like test data themselves
    q_marks_d = ",".join("?" for _ in donor_ids) or "NULL"
    q_marks_m = ",".join("?" for _ in member_ids) or "NULL"
    cur.execute(f"""
        SELECT id, patient_problem, donation_place FROM requests
        WHERE donor_id IN ({q_marks_d})
           OR created_by IN ({q_marks_m})
           OR managed_by IN ({q_marks_m})
           OR patient_problem LIKE 'test%'
           OR donation_place LIKE 'test%'
    """, donor_ids + member_ids + member_ids)
    test_requests = cur.fetchall()
    request_ids = [r[0] for r in test_requests]

    q_marks_r = ",".join("?" for _ in request_ids) or "NULL"

    cur.execute(f"""
        SELECT fid, donor_name FROM fulfillments
        WHERE request_id IN ({q_marks_r}) OR donor_id IN ({q_marks_d})
    """, request_ids + donor_ids)
    test_fulfillments = cur.fetchall()

    cur.execute(f"""
        SELECT id, donor_name FROM donations
        WHERE request_id IN ({q_marks_r}) OR donor_id IN ({q_marks_d}) OR member_id IN ({q_marks_m})
    """, request_ids + donor_ids + member_ids)
    test_donations = cur.fetchall()

    cur.execute(f"""
        SELECT id, donor_name FROM contacts
        WHERE donor_id IN ({q_marks_d}) OR member_id IN ({q_marks_m})
    """, donor_ids + member_ids)
    test_contacts = cur.fetchall()

    # --- preview ---
    print("=== The following will be PERMANENTLY deleted ===\n")
    print(f"Donors ({len(test_donors)}):", test_donors)
    print(f"Members ({len(test_members)}):", test_members)
    print(f"Requests ({len(test_requests)}):", test_requests)
    print(f"Fulfillments ({len(test_fulfillments)}):", test_fulfillments)
    print(f"Donations ({len(test_donations)}):", test_donations)
    print(f"Contacts ({len(test_contacts)}):", test_contacts)

    total = len(test_donors) + len(test_members) + len(test_requests) + len(test_fulfillments) + len(test_donations) + len(test_contacts)
    if total == 0:
        print("\nNothing matched -- nothing to delete.")
        con.close()
        return

    print(f"\nTotal rows to delete: {total}")
    confirm = input("\nType 'yes' to permanently delete the above, anything else to cancel: ").strip().lower()
    if confirm != "yes":
        print("Cancelled. Nothing was deleted.")
        con.close()
        return

    # --- delete, children first ---
    cur.execute(f"DELETE FROM fulfillments WHERE request_id IN ({q_marks_r}) OR donor_id IN ({q_marks_d})", request_ids + donor_ids)
    cur.execute(f"DELETE FROM donations WHERE request_id IN ({q_marks_r}) OR donor_id IN ({q_marks_d}) OR member_id IN ({q_marks_m})", request_ids + donor_ids + member_ids)
    cur.execute(f"DELETE FROM contacts WHERE donor_id IN ({q_marks_d}) OR member_id IN ({q_marks_m})", donor_ids + member_ids)
    cur.execute(f"DELETE FROM requests WHERE id IN ({q_marks_r})", request_ids)
    cur.execute(f"DELETE FROM donors WHERE id IN ({q_marks_d})", donor_ids)
    cur.execute(f"DELETE FROM members WHERE id IN ({q_marks_m})", member_ids)

    con.commit()

    cur.execute("PRAGMA foreign_key_check")
    problems = cur.fetchall()
    con.execute("PRAGMA foreign_keys = ON")
    if problems:
        print("\nWARNING: foreign_key_check found issues after delete:", problems)
    else:
        print("\nDone. Test data deleted, database integrity OK.")

    con.close()


if __name__ == "__main__":
    main()