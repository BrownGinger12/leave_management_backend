"""
Continuous database backup scheduler for the DepEd Leave Management System.

Reads connection details from the project's .env file, runs mysqldump on a
configurable interval, saves timestamped .sql files, and prunes old backups.

Usage:
    python scripts/backup_db.py

Runs forever until stopped with Ctrl+C. Performs one backup immediately on
start, then repeats on the configured interval.

Optional .env overrides:
    BACKUP_DIR       — where to store backup files   (default: D:\\backups\\leave_management)
    BACKUP_KEEP      — number of recent backups to keep (default: 30)
    BACKUP_INTERVAL  — how often to back up in hours  (default: 24)
    MYSQLDUMP_PATH   — full path to mysqldump.exe if auto-detect fails
"""

import os  # read environment variables
import subprocess  # run mysqldump as a subprocess
import sys  # exit with non-zero code on unrecoverable failure
from datetime import datetime  # generate timestamp for the backup filename
from pathlib import Path  # cross-platform path handling

from dotenv import load_dotenv  # load .env so we reuse the same credentials as the app
from apscheduler.schedulers.blocking import BlockingScheduler  # run jobs on a schedule, blocks the process


# ------------------------------------------------------------------
# Auto-detect mysqldump from common Windows installation paths
# ------------------------------------------------------------------
COMMON_MYSQLDUMP_PATHS = [  # ordered list of typical mysqldump locations on Windows
    r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
    r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
    r"C:\Program Files (x86)\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
    r"C:\xampp\mysql\bin\mysqldump.exe",
    r"C:\xampp2\mysql\bin\mysqldump.exe",
    r"C:\wamp64\bin\mysql\mysql8.0\bin\mysqldump.exe",
]


def find_mysqldump() -> str:
    """
    Resolves the path to mysqldump.exe.
    Checks MYSQLDUMP_PATH env var first, then common install locations,
    then falls back to 'mysqldump' (relies on system PATH).

    Returns:
        str: Path or command name to use when calling mysqldump.
    """
    env_override = os.getenv("MYSQLDUMP_PATH")  # explicit override takes priority
    if env_override:  # user specified a path — trust it
        return env_override

    for candidate in COMMON_MYSQLDUMP_PATHS:  # check each well-known location
        if Path(candidate).is_file():  # file exists at this path
            return candidate  # use it

    return "mysqldump"  # fall back to PATH — works if MySQL bin dir is in PATH


def run_backup() -> None:
    """
    Performs one full mysqldump backup.
    Saves the dump to BACKUP_DIR with a timestamp in the filename.
    Prunes backups older than the BACKUP_KEEP most recent files.

    Returns:
        None
    """
    # ------------------------------------------------------------------
    # Read MySQL connection details (same keys the app uses)
    # ------------------------------------------------------------------
    db_host     = os.getenv("MYSQL_HOST", "localhost")       # MySQL server host
    db_port     = os.getenv("MYSQL_PORT", "3306")            # MySQL server port
    db_user     = os.getenv("MYSQL_USER", "root")            # MySQL username
    db_password = os.getenv("MYSQL_PASSWORD", "")            # MySQL password
    db_name     = os.getenv("MYSQL_DATABASE", "deped-db")    # database to back up

    backup_dir  = Path(os.getenv("BACKUP_DIR", r"D:\backups\leave_management"))  # output directory
    keep_count  = int(os.getenv("BACKUP_KEEP", "30"))        # retention count
    mysqldump   = find_mysqldump()                            # resolve mysqldump path

    # ------------------------------------------------------------------
    # Ensure backup directory exists
    # ------------------------------------------------------------------
    backup_dir.mkdir(parents=True, exist_ok=True)  # create dirs if missing

    # ------------------------------------------------------------------
    # Build timestamped output filename
    # ------------------------------------------------------------------
    timestamp   = datetime.now().strftime("%Y-%m-%d_%H%M")   # e.g. 2026-09-27_0200
    backup_file = backup_dir / f"backup_{timestamp}.sql"     # full output path

    print(f"[backup] {datetime.now().strftime('%Y-%m-%d %H:%M')} — backing up '{db_name}' → {backup_file}")

    # ------------------------------------------------------------------
    # Build and run the mysqldump command
    # ------------------------------------------------------------------
    cmd = [
        mysqldump,
        f"--host={db_host}",          # server address
        f"--port={db_port}",          # server port
        f"--user={db_user}",          # login user
        f"--password={db_password}",  # login password
        "--single-transaction",       # consistent InnoDB snapshot without table locks
        "--routines",                 # include stored procedures/functions
        "--add-drop-table",           # prepend DROP TABLE IF EXISTS before each CREATE
        db_name,                      # database to dump
    ]

    try:
        with open(backup_file, "w", encoding="utf-8") as out_f:  # open output file
            result = subprocess.run(  # run mysqldump, write stdout to file
                cmd,
                stdout=out_f,
                stderr=subprocess.PIPE,
                text=True,
            )

        if result.returncode != 0:  # non-zero exit = mysqldump error
            print(f"[backup] ERROR: mysqldump failed (exit {result.returncode})")  # log error code
            print(f"[backup] {result.stderr.strip()}")  # print mysqldump error message
            backup_file.unlink(missing_ok=True)  # remove incomplete file
            return  # do not prune — this backup didn't succeed

        size_kb = backup_file.stat().st_size / 1024  # compute file size
        print(f"[backup] Success. File size: {size_kb:.1f} KB")  # log result

    except FileNotFoundError:  # mysqldump binary not found at all
        print(f"[backup] ERROR: mysqldump not found at '{mysqldump}'")
        print(f"[backup] Checked paths: {COMMON_MYSQLDUMP_PATHS}")
        print("[backup] Add MYSQLDUMP_PATH=<full path to mysqldump.exe> to your .env file")
        return  # skip pruning — nothing was written

    # ------------------------------------------------------------------
    # Prune old backups — keep only the most recent `keep_count` files
    # ------------------------------------------------------------------
    all_backups = sorted(  # list .sql files, oldest first
        backup_dir.glob("backup_*.sql"),
        key=lambda f: f.stat().st_mtime,
    )

    to_delete = all_backups[:-keep_count] if len(all_backups) > keep_count else []  # files outside retention window

    for old_file in to_delete:  # remove each expired backup
        old_file.unlink()  # delete the file
        print(f"[backup] Removed old backup: {old_file.name}")  # log deletion

    remaining = len(all_backups) - len(to_delete)  # backups now on disk
    print(f"[backup] Retention: {remaining}/{keep_count} backups kept.\n")  # log status


def main():
    """
    Loads .env, runs one immediate backup, then starts the APScheduler loop
    that fires run_backup() every BACKUP_INTERVAL hours. Runs until Ctrl+C.

    Returns:
        None
    """
    # ------------------------------------------------------------------
    # Load .env from the project root (one level above this script)
    # ------------------------------------------------------------------
    env_path = Path(__file__).resolve().parent.parent / ".env"  # project root .env
    load_dotenv(dotenv_path=env_path)  # populate os.environ

    interval_hours = float(os.getenv("BACKUP_INTERVAL", "24"))  # how often to back up

    print(f"[backup] Scheduler starting. Backup every {interval_hours}h. Press Ctrl+C to stop.\n")

    # ------------------------------------------------------------------
    # Run one backup immediately so we don't wait a full interval on start
    # ------------------------------------------------------------------
    run_backup()  # immediate first backup

    # ------------------------------------------------------------------
    # Schedule recurring backups with APScheduler
    # ------------------------------------------------------------------
    scheduler = BlockingScheduler()  # blocking: this call never returns until stopped
    scheduler.add_job(  # register the backup job
        run_backup,
        trigger="interval",           # repeat on a fixed interval
        hours=interval_hours,         # configured interval
        id="db_backup",               # job identifier
    )

    try:
        scheduler.start()  # blocks here — fires run_backup() every interval
    except (KeyboardInterrupt, SystemExit):  # Ctrl+C or kill signal
        print("\n[backup] Scheduler stopped.")  # clean exit message
        sys.exit(0)  # exit cleanly


if __name__ == "__main__":
    main()  # run when executed directly
