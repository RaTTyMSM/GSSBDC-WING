"""
GSSBDC WING - data/ backup script.

Zips the data/ folder into backups/ with a timestamped filename, and
deletes old backups beyond KEEP_BACKUPS so the folder doesn't grow
forever.

Run manually:
    python backup.py

Or schedule it to run automatically (recommended: once a day):

  Windows (Task Scheduler):
    1. Open Task Scheduler -> Create Basic Task.
    2. Trigger: Daily, pick a time (e.g. 2:00 AM).
    3. Action: Start a program.
       Program/script:  C:\\path\\to\\venv\\Scripts\\python.exe
       Add arguments:   backup.py
       Start in:        C:\\path\\to\\GSSBDC WING
    4. Finish. It will now run every day even if nobody opens the app.

  Linux/macOS (cron):
    Add a line to `crontab -e`:
    0 2 * * *  cd "/path/to/GSSBDC WING" && /path/to/venv/bin/python backup.py
"""

import os
import zipfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

# How many most-recent backups to keep. Older ones are deleted automatically.
KEEP_BACKUPS = 30


def create_backup():
    if not os.path.isdir(DATA_DIR):
        print(f"No data/ folder found at {DATA_DIR}, nothing to back up.")
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"data_backup_{timestamp}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in sorted(os.listdir(DATA_DIR)):
            file_path = os.path.join(DATA_DIR, filename)
            if os.path.isfile(file_path):
                zf.write(file_path, arcname=os.path.join("data", filename))

    size_kb = os.path.getsize(backup_path) / 1024
    print(f"Backup created: {backup_path} ({size_kb:.1f} KB)")
    return backup_path


def prune_old_backups():
    if not os.path.isdir(BACKUP_DIR):
        return

    backups = sorted(
        (f for f in os.listdir(BACKUP_DIR) if f.startswith("data_backup_") and f.endswith(".zip")),
        reverse=True,  # newest first (timestamp is in the filename)
    )

    for old_backup in backups[KEEP_BACKUPS:]:
        old_path = os.path.join(BACKUP_DIR, old_backup)
        os.remove(old_path)
        print(f"Removed old backup: {old_backup}")


if __name__ == "__main__":
    create_backup()
    prune_old_backups()