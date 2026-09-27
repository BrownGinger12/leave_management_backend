"""
Database backup script for the DepEd Leave Management System.

Reads connection details from the project's .env file, runs mysqldump,
saves the output as a timestamped .sql file, and prunes old backups.

Usage:
    python scripts/backup_db.py

Optional env overrides (add to .env or set before running):
    BACKUP_DIR       — where to store backup files (default: D:\\backups\\leave_management)
    BACKUP_KEEP      — number of recent backups to keep (default: 30)
    MYSQLDUMP_PATH   — full path to mysqldump.exe if not on PATH
"""

import os  # read environment variables and manipulate file paths
import subprocess  # run mysqldump as a subprocess
import sys  # exit with non-zero code on failure
from datetime import datetime  # generate timestamp for the backup filename
from pathlib import Path  # cross-platform path handling

from dotenv import load_dotenv  # load .env so we reuse the same credentials as the app


def main():
    """
    Entry point: loads config, runs mysqldump, saves the file, prunes old backups.

    Returns:
        None. Exits with code 1 on failure.
    """
    # ------------------------------------------------------------------
    # Load .env from the project root (one level above this script)
    # ------------------------------------------------------------------
    script_dir = Path(__file__).resolve().parent  # directory containing this script
    env_path = script_dir.parent / ".env"  # project root .env
    load_dotenv(dotenv_path=env_path)  # populate os.environ from .env

    # ------------------------------------------------------------------
    # Read MySQL connection details (same keys the app uses)
    # ------------------------------------------------------------------
    db_host = os.getenv("MYSQL_HOST", "localhost")          # MySQL server host
    db_port = os.getenv("MYSQL_PORT", "3306")               # MySQL server port
    db_user = os.getenv("MYSQL_USER", "root")               # MySQL username
    db_password = os.getenv("MYSQL_PASSWORD", "")           # MySQL password
    db_name = os.getenv("MYSQL_DATABASE", "deped-db")       # database to back up

    # ------------------------------------------------------------------
    # Backup destination and retention settings
    # ------------------------------------------------------------------
    backup_dir = Path(os.getenv("BACKUP_DIR", r"D:\backups\leave_management"))  # where to save .sql files
    keep_count = int(os.getenv("BACKUP_KEEP", "30"))        # how many backups to keep

    # ------------------------------------------------------------------
    # Locate mysqldump
    # ------------------------------------------------------------------
    mysqldump = os.getenv("MYSQLDUMP_PATH", "mysqldump")    # use PATH by default; override via env if needed

    # ------------------------------------------------------------------
    # Create backup directory if it does not exist
    # ------------------------------------------------------------------
    backup_dir.mkdir(parents=True, exist_ok=True)  # create all parent dirs as needed

    # ------------------------------------------------------------------
    # Build output filename with current timestamp
    # ------------------------------------------------------------------
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")    # e.g. 2026-09-27_0200
    backup_file = backup_dir / f"backup_{timestamp}.sql"    # full path for this backup

    # ------------------------------------------------------------------
    # Run mysqldump
    # ------------------------------------------------------------------
    cmd = [  # build the mysqldump command
        mysqldump,
        f"--host={db_host}",           # server address
        f"--port={db_port}",           # server port
        f"--user={db_user}",           # login user
        f"--password={db_password}",   # login password (passed via arg to avoid shell prompt)
        "--single-transaction",        # consistent snapshot without locking tables (InnoDB)
        "--routines",                  # include stored procedures/functions
        "--add-drop-table",            # each CREATE TABLE is preceded by DROP TABLE IF EXISTS
        db_name,                       # the database to dump
    ]

    print(f"[backup] Starting backup of '{db_name}' → {backup_file}")  # log start

    try:
        with open(backup_file, "w", encoding="utf-8") as out_f:  # open output file for writing
            result = subprocess.run(  # run mysqldump and capture output
                cmd,
                stdout=out_f,          # write dump directly to file
                stderr=subprocess.PIPE,  # capture error output separately
                text=True,             # decode output as text
            )

        if result.returncode != 0:  # non-zero exit means mysqldump failed
            print(f"[backup] ERROR: mysqldump exited with code {result.returncode}")  # log error code
            print(f"[backup] {result.stderr.strip()}")  # print the mysqldump error message
            backup_file.unlink(missing_ok=True)  # remove incomplete file
            sys.exit(1)  # exit with failure code

        size_kb = backup_file.stat().st_size / 1024  # compute file size in KB
        print(f"[backup] Done. File size: {size_kb:.1f} KB")  # log success with size

    except FileNotFoundError:  # mysqldump not found on PATH or at MYSQLDUMP_PATH
        print(f"[backup] ERROR: '{mysqldump}' not found.")  # helpful error message
        print("[backup] Set MYSQLDUMP_PATH in .env to the full path of mysqldump.exe")  # hint
        sys.exit(1)  # exit with failure code

    # ------------------------------------------------------------------
    # Prune old backups — keep only the most recent `keep_count` files
    # ------------------------------------------------------------------
    all_backups = sorted(  # list all .sql backup files, oldest first
        backup_dir.glob("backup_*.sql"),
        key=lambda f: f.stat().st_mtime,
    )

    to_delete = all_backups[:-keep_count] if len(all_backups) > keep_count else []  # files outside the retention window

    for old_file in to_delete:  # remove each expired backup
        old_file.unlink()  # delete the file
        print(f"[backup] Removed old backup: {old_file.name}")  # log deletion

    remaining = len(all_backups) - len(to_delete)  # count of backups now on disk
    print(f"[backup] Retention: keeping {remaining} of {keep_count} max backups.")  # log retention status


if __name__ == "__main__":
    main()  # run when executed directly
