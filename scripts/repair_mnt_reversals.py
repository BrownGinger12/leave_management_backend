"""
One-time repair: post missing MONETIZATION CREDIT reversal entries for any
RETURNED or DISAPPROVED MNT applications whose VL/SL credits were never recorded.

This happened because _post_mnt_reversal() did not exist when those applications
were returned — the old generic _post_reversal() exited early for NONE balance_type.

Run from the project root:
    python scripts/repair_mnt_reversals.py
"""

import os
import sys
import uuid

# ── Add project root to path so gateway imports work ─────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gateway.mysql_gateway import fetch_query, query_insert, recalculate_ledger_snapshots  # noqa: E402

REVERSED_STATUSES = {"RETURNED", "DISAPPROVED"}  # statuses where a credit refund should have been posted


def _txn_number() -> str:
    """Generate a unique transaction number in TXN-XXXXXXXX format."""
    return "TXN-" + uuid.uuid4().hex[:8].upper()  # 8-char hex suffix for uniqueness


def repair():
    """
    Scan all MNT applications with RETURNED or DISAPPROVED status.
    For each, check whether the expected MONETIZATION CREDIT rows exist.
    Post any missing credits and recalculate ledger snapshots.
    """

    # ── Fetch leave type IDs ──────────────────────────────────────────────────
    vl_row = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # look up VL type
    sl_row = fetch_query("SELECT id FROM leave_types WHERE code = 'SL'", [])  # look up SL type
    if not vl_row or not sl_row:  # both must exist
        print("❌ VL or SL leave type not found — aborting")
        return
    vl_type_id = vl_row[0]["id"]  # VL leave type primary key
    sl_type_id = sl_row[0]["id"]  # SL leave type primary key

    # ── Fetch all reversed MNT applications ──────────────────────────────────
    mnt_apps = fetch_query(
        """SELECT la.id, la.application_number, la.employee_id,
                  la.mnt_vl_days, la.mnt_sl_days, la.date_filed, la.status
           FROM leave_applications la
           JOIN leave_types lt ON lt.id = la.leave_type_id
           WHERE lt.code = 'MNT'
             AND la.status IN ('RETURNED', 'DISAPPROVED')
             AND la.is_deleted = 0""",
        []
    ) or []

    if not mnt_apps:  # nothing to repair
        print("✅ No reversed MNT applications found — nothing to repair")
        return

    print(f"Found {len(mnt_apps)} reversed MNT application(s) to inspect...\n")

    repaired = 0  # count of applications where credits were posted

    for app in mnt_apps:  # check each reversed MNT application
        app_id     = app["id"]  # application primary key
        app_num    = app["application_number"]  # MN-XXXXXXXX reference
        emp_id     = app["employee_id"]  # employee who owns the application
        vl_days    = float(app["mnt_vl_days"] or 0)  # VL days to restore
        sl_days    = float(app["mnt_sl_days"] or 0)  # SL days to restore
        date_filed = str(app["date_filed"])  # use date_filed as transaction date
        status     = app["status"]  # RETURNED or DISAPPROVED
        action     = "Disapproved" if status == "DISAPPROVED" else "Returned"  # label for remarks
        posted_any = False  # track whether we posted anything for this app

        # ── Check existing MONETIZATION CREDIT rows for this application ─────
        existing = fetch_query(
            """SELECT leave_type_id, transaction_type
               FROM leave_credit_transactions
               WHERE employee_id = %s AND source_type = 'MONETIZATION'
                 AND source_id = %s AND transaction_type = 'CREDIT'""",
            [emp_id, app_id]
        ) or []

        existing_credit_type_ids = {r["leave_type_id"] for r in existing}  # set of type IDs that already have a credit

        # ── Post missing VL credit ────────────────────────────────────────────
        if vl_days > 0 and vl_type_id not in existing_credit_type_ids:  # VL credit not yet posted
            print(f"  [{app_num}] Posting missing VL CREDIT {vl_days} days for employee {emp_id}...")
            result = query_insert(
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'MONETIZATION', %s, %s, 0, %s)""",
                [
                    _txn_number(),                                                       # unique TXN number
                    emp_id,                                                              # employee
                    vl_type_id,                                                          # VL leave type
                    vl_days,                                                             # days restored
                    app_id,                                                              # source application
                    date_filed,                                                          # same date as original debit
                    f"Refund - {action} monetization {app_num} - VL restored (repair)", # audit remark
                ]
            )
            if result["statusCode"] != 200:  # insert failed
                print(f"  ❌ Failed to post VL credit: {result.get('message')}")
                continue  # skip recalculate for this app; try next
            recalculate_ledger_snapshots(emp_id, vl_type_id)  # rebuild VL balance snapshots
            print(f"     ✅ VL credit posted and snapshots recalculated")
            posted_any = True  # mark that we did something

        elif vl_days > 0:  # credit already exists
            print(f"  [{app_num}] VL credit already present — skipping")

        # ── Post missing SL credit ────────────────────────────────────────────
        if sl_days > 0 and sl_type_id not in existing_credit_type_ids:  # SL credit not yet posted
            print(f"  [{app_num}] Posting missing SL CREDIT {sl_days} days for employee {emp_id}...")
            result = query_insert(
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'MONETIZATION', %s, %s, 0, %s)""",
                [
                    _txn_number(),                                                       # unique TXN number
                    emp_id,                                                              # employee
                    sl_type_id,                                                          # SL leave type
                    sl_days,                                                             # days restored
                    app_id,                                                              # source application
                    date_filed,                                                          # same date as original debit
                    f"Refund - {action} monetization {app_num} - SL restored (repair)", # audit remark
                ]
            )
            if result["statusCode"] != 200:  # insert failed
                print(f"  ❌ Failed to post SL credit: {result.get('message')}")
                continue  # skip to next app
            recalculate_ledger_snapshots(emp_id, sl_type_id)  # rebuild SL balance snapshots
            print(f"     ✅ SL credit posted and snapshots recalculated")
            posted_any = True  # mark that we did something

        elif sl_days > 0:  # credit already exists
            print(f"  [{app_num}] SL credit already present — skipping")

        if posted_any:  # at least one credit was posted for this app
            repaired += 1

    print(f"\n{'=' * 50}")
    print(f"Repair complete. {repaired} application(s) had missing credits posted.")


if __name__ == "__main__":
    repair()
