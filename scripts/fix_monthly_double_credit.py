"""
Fix double monthly VL/SL credit for August 2026.

Finds employees who have more than one MONTHLY_CREDIT row for VL or SL
in the current month, deletes the extras (keeps the earliest by id),
then recalculates ledger snapshots for affected employees.

Run once:
    python scripts/fix_monthly_double_credit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # add project root to path

from dotenv import load_dotenv  # load environment variables from .env
load_dotenv()  # populate os.environ from .env file

from gateway.mysql_gateway import fetch_query, query  # DB helpers
from model.annual_leave_credit import AnnualLeaveCredit  # for recalculate helper

TARGET_YEAR  = 2026  # year to fix
TARGET_MONTH = 8     # month to fix (August)

def recalculate_ledger_snapshots(employee_id: int, leave_type_id: int):
    """
    Recalculates balance_snapshot_after for every transaction of (employee, leave_type)
    in chronological order, then updates the employee_leave_balances cache.

    Parameters:
        employee_id (int): Employee primary key.
        leave_type_id (int): Leave type primary key.
    """
    rows = fetch_query(  # fetch all transactions ordered chronologically
        """SELECT id, transaction_type, amount
           FROM leave_credit_transactions
           WHERE employee_id = %s AND leave_type_id = %s
           ORDER BY transaction_date ASC, id ASC""",
        [employee_id, leave_type_id]
    )

    running = 0.0  # running balance
    for row in rows:  # compute snapshot after each transaction
        if row["transaction_type"] == "CREDIT":  # add for credits
            running += float(row["amount"])
        else:  # subtract for debits
            running -= float(row["amount"])
        query(  # update snapshot in place
            "UPDATE leave_credit_transactions SET balance_snapshot_after = %s WHERE id = %s",
            [round(running, 4), row["id"]]
        )

    query(  # update the balance cache for this employee+type
        """INSERT INTO employee_leave_balances (employee_id, leave_type_id, balance)
           VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE balance = VALUES(balance)""",
        [employee_id, leave_type_id, round(running, 4)]
    )
    print(f"  Recalculated emp {employee_id} lt {leave_type_id}: final balance = {round(running, 4)}")  # progress log


def main():
    """
    Entry point. Finds duplicate MONTHLY_CREDIT rows for VL and SL in the target month,
    deletes all but the earliest per employee, then recalculates balances.
    """
    # Resolve VL and SL leave type IDs
    leave_types = fetch_query(  # fetch VL and SL IDs
        "SELECT id, code FROM leave_types WHERE code IN ('VL', 'SL') AND is_active = 1", []
    )
    lt_map = {lt["code"]: lt["id"] for lt in leave_types}  # code -> id map
    vl_id = lt_map.get("VL")  # VL primary key
    sl_id = lt_map.get("SL")  # SL primary key

    if not vl_id or not sl_id:  # cannot proceed without both types
        print("ERROR: VL or SL leave type not found")
        return

    print(f"VL id={vl_id}, SL id={sl_id}")
    print(f"Looking for duplicate MONTHLY_CREDIT rows for {TARGET_YEAR}-{TARGET_MONTH:02d}...\n")

    total_deleted = 0  # track total rows removed
    affected_employees = set()  # track which employees need recalculation

    for leave_type_id in (vl_id, sl_id):  # check VL then SL
        code = "VL" if leave_type_id == vl_id else "SL"  # label for logging

        # Find employees with more than one MONTHLY_CREDIT this month for this type
        duplicates = fetch_query(
            """SELECT employee_id, COUNT(*) AS cnt, MIN(id) AS keep_id
               FROM leave_credit_transactions
               WHERE leave_type_id = %s
                 AND source_type = 'MONTHLY_CREDIT'
                 AND YEAR(transaction_date) = %s
                 AND MONTH(transaction_date) = %s
               GROUP BY employee_id
               HAVING cnt > 1""",
            [leave_type_id, TARGET_YEAR, TARGET_MONTH]
        )

        if not duplicates:  # no duplicates found for this type
            print(f"{code}: no duplicates found")
            continue

        print(f"{code}: {len(duplicates)} employee(s) with duplicate credits")

        for row in duplicates:  # process each affected employee
            emp_id   = row["employee_id"]  # employee primary key
            keep_id  = row["keep_id"]      # earliest row to keep
            cnt      = row["cnt"]          # total rows (cnt - 1 are extra)

            # Fetch the extra row IDs (all except the one to keep)
            extras = fetch_query(
                """SELECT id FROM leave_credit_transactions
                   WHERE employee_id = %s AND leave_type_id = %s
                     AND source_type = 'MONTHLY_CREDIT'
                     AND YEAR(transaction_date) = %s AND MONTH(transaction_date) = %s
                     AND id != %s""",
                [emp_id, leave_type_id, TARGET_YEAR, TARGET_MONTH, keep_id]
            )

            for extra in extras:  # delete each extra row
                result = query(
                    "DELETE FROM leave_credit_transactions WHERE id = %s",
                    [extra["id"]]
                )
                if result["statusCode"] == 200:  # deletion succeeded
                    print(f"  Deleted txn id={extra['id']} for emp={emp_id} ({code}) — was extra #{cnt}")
                    total_deleted += 1  # increment deletion count
                else:
                    print(f"  FAILED to delete txn id={extra['id']}: {result}")

            affected_employees.add((emp_id, leave_type_id))  # mark for recalculation

    print(f"\nDeleted {total_deleted} duplicate row(s)")
    print(f"Recalculating balances for {len(affected_employees)} (employee, leave_type) pair(s)...\n")

    for emp_id, lt_id in sorted(affected_employees):  # recalculate in stable order
        recalculate_ledger_snapshots(emp_id, lt_id)  # rebuild snapshots and update cache

    print("\nDone.")


if __name__ == "__main__":
    main()  # run the cleanup
