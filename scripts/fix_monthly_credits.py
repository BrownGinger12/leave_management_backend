"""
One-off repair script for MONTHLY_CREDIT ledger rows.

Fixes three problems introduced by the old month-start crediting logic:
  1. Premature credits — a month credited before it had ended.
  2. Misdated credits — dated the 1st of the month instead of the last day.
  3. Duplicate credits — more than one credit for the same employee/type/month,
     caused by the old idempotency guard drifting from the ledger.

Runs as a dry run by default and prints what it would change.
Pass --apply to actually write the changes.

Usage:
    python scripts/fix_monthly_credits.py            # dry run, shows findings
    python scripts/fix_monthly_credits.py --apply     # performs the repair
"""

import sys  # read CLI flags and exit codes
from calendar import monthrange  # resolve the last day of a month
from datetime import date  # determine the current month boundary
from pathlib import Path  # locate the project root

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make project modules importable

from dotenv import load_dotenv  # load DB credentials from .env

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")  # populate os.environ before gateway import

from gateway.mysql_gateway import fetch_query, query, recalculate_ledger_snapshots  # DB access


def main():
    """
    Inspects every MONTHLY_CREDIT ledger row, reports premature, misdated and
    duplicate entries, and repairs them when --apply is passed.

    Returns:
        None
    """
    apply_changes = "--apply" in sys.argv  # whether to write or just report
    mode = "APPLY" if apply_changes else "DRY RUN"  # label for the output
    print(f"[fix] Mode: {mode}\n")  # announce the mode

    today = date.today()  # reference date
    current_month_start = f"{today.year}-{today.month:02d}-01"  # first day of the in-progress month

    affected = set()  # (employee_id, leave_type_id) pairs needing a snapshot recalc

    # ------------------------------------------------------------------
    # 1. Premature credits — the credited month has not ended yet
    # ------------------------------------------------------------------
    premature = fetch_query(  # any monthly credit falling in the current month or later
        """SELECT id, employee_id, leave_type_id, transaction_date, amount, remarks
           FROM leave_credit_transactions
           WHERE source_type = 'MONTHLY_CREDIT'
             AND transaction_date >= %s
           ORDER BY employee_id, transaction_date""",
        [current_month_start]
    ) or []

    print(f"[fix] Premature credits (month not yet ended): {len(premature)}")  # report count
    for row in premature:  # list each offending row
        print(f"       id={row['id']} emp={row['employee_id']} "
              f"type={row['leave_type_id']} date={row['transaction_date']} amt={row['amount']}")

    if apply_changes and premature:  # remove them
        ids = [r["id"] for r in premature]  # ledger row ids to delete
        placeholders = ",".join(["%s"] * len(ids))  # build IN clause
        query(f"DELETE FROM monthly_leave_credits WHERE transaction_id IN ({placeholders})", ids)  # drop guard rows
        query(f"DELETE FROM leave_credit_transactions WHERE id IN ({placeholders})", ids)  # drop ledger rows
        for r in premature:  # mark affected pairs for recalc
            affected.add((r["employee_id"], r["leave_type_id"]))
        print(f"[fix] Deleted {len(ids)} premature credit rows.")  # confirm

    # ------------------------------------------------------------------
    # 2. Misdated credits — dated the 1st instead of the month's last day
    # ------------------------------------------------------------------
    misdated = fetch_query(  # monthly credits still dated day 1
        """SELECT id, employee_id, leave_type_id, transaction_date
           FROM leave_credit_transactions
           WHERE source_type = 'MONTHLY_CREDIT'
             AND DAY(transaction_date) = 1
           ORDER BY employee_id, transaction_date""",
        []
    ) or []

    print(f"\n[fix] Misdated credits (dated the 1st): {len(misdated)}")  # report count
    for row in misdated[:10]:  # preview the first few
        d = row["transaction_date"]  # the current (wrong) date
        new_day = monthrange(d.year, d.month)[1]  # last day of that month
        print(f"       id={row['id']} emp={row['employee_id']} {d} → {d.year}-{d.month:02d}-{new_day:02d}")
    if len(misdated) > 10:  # note truncation
        print(f"       ... and {len(misdated) - 10} more")

    if apply_changes and misdated:  # move each to the month's last day
        for row in misdated:  # update one row at a time — the target day varies by month
            d = row["transaction_date"]  # current date
            new_day = monthrange(d.year, d.month)[1]  # last day of that month
            query(  # shift the transaction date to month end
                "UPDATE leave_credit_transactions SET transaction_date = %s WHERE id = %s",
                [f"{d.year}-{d.month:02d}-{new_day:02d}", row["id"]]
            )
            affected.add((row["employee_id"], row["leave_type_id"]))  # mark for recalc
        print(f"[fix] Re-dated {len(misdated)} credits to month end.")  # confirm

    # ------------------------------------------------------------------
    # 3. Duplicate credits — same employee/type/month credited twice
    #    Checked after re-dating so collapsed dates are caught too.
    # ------------------------------------------------------------------
    dupes = fetch_query(  # groups with more than one credit for the same month
        """SELECT employee_id, leave_type_id, transaction_date,
                  COUNT(*) AS cnt, MIN(id) AS keep_id
           FROM leave_credit_transactions
           WHERE source_type = 'MONTHLY_CREDIT'
           GROUP BY employee_id, leave_type_id, transaction_date
           HAVING cnt > 1""",
        []
    ) or []

    print(f"\n[fix] Duplicated credit groups: {len(dupes)}")  # report count
    for row in dupes:  # list each duplicated group
        print(f"       emp={row['employee_id']} type={row['leave_type_id']} "
              f"date={row['transaction_date']} count={row['cnt']} (keeping id={row['keep_id']})")

    if apply_changes and dupes:  # keep the earliest row in each group, delete the rest
        removed = 0  # count of deleted duplicate rows
        for row in dupes:  # handle each group
            extras = fetch_query(  # ledger ids to remove for this group
                """SELECT id FROM leave_credit_transactions
                   WHERE source_type = 'MONTHLY_CREDIT'
                     AND employee_id = %s AND leave_type_id = %s
                     AND transaction_date = %s AND id <> %s""",
                [row["employee_id"], row["leave_type_id"], row["transaction_date"], row["keep_id"]]
            ) or []
            ids = [e["id"] for e in extras]  # extract the ids
            if not ids:  # nothing to remove
                continue
            placeholders = ",".join(["%s"] * len(ids))  # build IN clause
            query(f"DELETE FROM monthly_leave_credits WHERE transaction_id IN ({placeholders})", ids)  # drop guard rows
            query(f"DELETE FROM leave_credit_transactions WHERE id IN ({placeholders})", ids)  # drop ledger rows
            affected.add((row["employee_id"], row["leave_type_id"]))  # mark for recalc
            removed += len(ids)  # accumulate
        print(f"[fix] Deleted {removed} duplicate credit rows.")  # confirm

    # ------------------------------------------------------------------
    # 4. Recalculate snapshots and balance cache for every touched pair
    # ------------------------------------------------------------------
    if apply_changes and affected:  # rebuild running balances where rows changed
        print(f"\n[fix] Recalculating snapshots for {len(affected)} employee/leave-type pairs...")
        for emp_id, lt_id in sorted(affected):  # walk each affected pair
            final = recalculate_ledger_snapshots(emp_id, lt_id)  # rebuild the running total
            print(f"       emp={emp_id} type={lt_id} → final balance {final}")
        print("[fix] Done.")  # confirm completion
    elif not apply_changes:  # dry run finished
        print("\n[fix] Dry run complete. Re-run with --apply to perform these changes.")


if __name__ == "__main__":
    main()  # run when executed directly
