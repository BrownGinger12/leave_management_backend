from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
import uuid  # import uuid to generate unique transaction numbers


class LeaveApproval(BaseModel):
    """
    Pydantic model representing a leave approval decision.

    Attributes:
        leave_application_id: FK to the leave application being acted on.
        approver_id: FK to the employee making the approval decision.
        level: Approval level (1 = immediate supervisor, 2 = HR, etc.).
        status: Decision — APPROVED or REJECTED.
        remarks: Optional remarks from the approver.
    """
    leave_application_id: int  # FK to leave_applications table
    approver_id: int  # FK to employees table (the approver)
    level: int  # approval level number
    status: str  # APPROVED or REJECTED
    remarks: Optional[str] = None  # optional remarks from the approver

    # --------------------------
    # Generate transaction number
    # --------------------------

    @staticmethod
    def _generate_transaction_number() -> str:
        """
        Generates a unique ledger transaction number using a UUID-based suffix.

        Returns:
            str: A transaction number in the format 'TXN-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"TXN-{suffix}"  # format as TXN-XXXXXXXX

    # --------------------------
    # Restore CTO per-credit balances on reversal
    # --------------------------

    @staticmethod
    def _restore_cto(employee_id: int, leave_type_id: int,
                     application_id: int, start_date: str) -> dict | None:
        """
        Restores CTO per-credit balances when a CTO leave is returned or disapproved.
        Reads cto_deduction_log to find which credits were charged, adds each amount back
        to cto_credit_balances.remaining_balance, posts a matching CREDIT ledger entry per
        deduction row, deletes the log rows, then recalculates snapshots once.

        Parameters:
            employee_id (int): The employee whose CTO credits are being restored.
            leave_type_id (int): The CTO leave type ID for ledger entries.
            application_id (int): The leave application being reversed.
            start_date (str): First day of the leave (same date as original DEBIT transaction_date).

        Returns:
            dict | None: An error dict if any step fails, None on full success.
        """
        logs = fetch_query(  # fetch all deduction log rows tied to this application
            """SELECT cdl.id, cdl.cto_credit_balance_id, cdl.amount_deducted,
                      ccb.valid_until,
                      (SELECT application_number FROM service_credit_applications
                       WHERE id = ccb.service_credit_application_id) AS app_number
               FROM cto_deduction_log cdl
               JOIN cto_credit_balances ccb ON ccb.id = cdl.cto_credit_balance_id
               WHERE cdl.leave_application_id = %s""",
            [application_id]
        )

        if not logs:  # no log entries — nothing was deducted or already reversed
            return None  # nothing to restore

        for log in logs:  # iterate each partial deduction recorded at submission
            restore_result = query(  # add the deducted amount back to this credit's remaining balance
                "UPDATE cto_credit_balances SET remaining_balance = remaining_balance + %s WHERE id = %s",
                [log["amount_deducted"], log["cto_credit_balance_id"]]
            )
            if restore_result["statusCode"] != 200:  # check if balance restore failed
                return restore_result  # return the error

            valid_label = str(log["valid_until"])  # format expiry date for ledger remarks
            txn_result = query_insert(  # post a CREDIT ledger entry matching each original DEBIT
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApproval._generate_transaction_number(),  # unique transaction number
                    employee_id,               # employee being restored
                    leave_type_id,             # CTO leave type ID
                    log["amount_deducted"],    # amount restored to this specific credit
                    application_id,            # source: the reversed leave application
                    start_date,                # same date as the original DEBIT for correct ledger pairing
                    f"CTO leave reversed — credit {log['app_number']} restored (valid until {valid_label})",  # audit trail
                ]
            )
            if txn_result["statusCode"] != 200:  # check if CREDIT insert failed
                return txn_result  # return the error

        # log entries are intentionally kept after reversal so the application still appears
        # in the CTO leave summary; _deduct_cto will clear them on re-activation before re-inserting
        recalculate_ledger_snapshots(employee_id, leave_type_id)  # recalculate all CTO ledger snapshots once

        return None  # CTO credits fully restored

    # --------------------------
    # Restore VSC per-credit balances on reversal
    # --------------------------

    @staticmethod
    def _restore_vsc(employee_id: int, application_id: int, start_date: str) -> dict | None:
        """
        Restores VSC per-credit balances when a VSC-funded leave (SL or PR) is returned
        or disapproved. Reads vsc_deduction_log to find which credits were charged, adds
        each amount back to the appropriate table (OLD → vsc_old_credit_balances,
        NEW → vsc_new_credit_balances), posts a matching CREDIT ledger entry per deduction
        row, then recalculates VSC snapshots once. Log entries are kept as audit trail;
        _deduct_vsc will clear them on re-activation before re-inserting.

        Parameters:
            employee_id (int): The employee whose VSC credits are being restored.
            application_id (int): The leave application being reversed.
            start_date (str): First day of the leave (same date as the original DEBIT entries).

        Returns:
            dict | None: An error dict if any step fails, None on full success.
        """
        vsc_type = fetch_query(  # fetch VSC leave type ID for CREDIT ledger entries
            "SELECT id FROM leave_types WHERE code = 'VSC'", []
        )
        if not vsc_type:  # VSC type not found in system
            return {"statusCode": 500, "message": "VSC leave type not found in the system"}  # return error
        vsc_leave_type_id = vsc_type[0]["id"]  # VSC leave type ID for all CREDIT entries

        logs = fetch_query(  # fetch all deduction log rows tied to this application
            "SELECT id, credit_pool, credit_balance_id, amount_deducted FROM vsc_deduction_log WHERE leave_application_id = %s",
            [application_id]
        )

        if not logs:  # no log entries — nothing was deducted or already restored
            return None  # nothing to restore

        for log in logs:  # iterate each partial deduction recorded at submission
            table = "vsc_old_credit_balances" if log["credit_pool"] == "OLD" else "vsc_new_credit_balances"  # determine credit table

            restore_result = query(  # add the deducted amount back to this credit's remaining balance
                f"UPDATE {table} SET remaining_balance = remaining_balance + %s WHERE id = %s",
                [log["amount_deducted"], log["credit_balance_id"]]
            )
            if restore_result["statusCode"] != 200:  # check if balance restore failed
                return restore_result  # return the error

            pool_label = log["credit_pool"].lower()  # format pool name for ledger remarks
            txn_result = query_insert(  # post CREDIT ledger entry matching each original DEBIT
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApproval._generate_transaction_number(),  # unique transaction number
                    employee_id,                    # employee being restored
                    vsc_leave_type_id,              # VSC leave type for the ledger entry
                    log["amount_deducted"],          # days being restored to this credit
                    application_id,                 # source: the reversed leave application
                    start_date,                     # same date as original DEBIT for correct ledger pairing
                    f"Leave reversed — VSC ({pool_label}) credit restored",  # audit trail
                ]
            )
            if txn_result["statusCode"] != 200:  # check if CREDIT insert failed
                return txn_result  # return the error

        recalculate_ledger_snapshots(employee_id, vsc_leave_type_id)  # recalculate all VSC snapshots once
        return None  # VSC credits fully restored

    # --------------------------
    # Post credit reversal to ledger
    # --------------------------

    @staticmethod
    def _post_reversal(employee_id: int, leave_type_id: int, leave_type_code: str,
                       balance_type: str, total_days: float, application_id: int,
                       start_date: str) -> dict | None:
        """
        Posts a CREDIT reversal to the ledger when a leave application is RETURNED or DISAPPROVED.
        Cancels the DEBIT that was posted at submission time, restoring the employee's balance.
        Uses the same start_date as the original DEBIT so the reversal pairs correctly in the ledger.
        CTO is handled separately via _restore_cto because deductions span multiple credit rows.
        No reversal is posted when balance_type is NONE (no debit was made at submission).

        Parameters:
            employee_id (int): The employee whose balance is being restored.
            leave_type_id (int): The leave type being reversed.
            leave_type_code (str): The leave type code (VL, SL, FL, CTO, etc.).
            balance_type (str): SELF, CHARGED_TO_VL, or NONE.
            total_days (float): Number of days to restore (not used for CTO).
            application_id (int): The source leave application ID.
            start_date (str): The first day of the leave (YYYY-MM-DD), same date as the original DEBIT.

        Returns:
            dict | None: An error dict if reversal fails, None on success.
        """
        if balance_type == "NONE":  # no debit was posted for this leave type
            return None  # nothing to reverse

        if balance_type == "CHARGED_TO_VL":  # FL — reverse both FL and VL debits
            vl_type = fetch_query(  # get the VL leave type ID
                "SELECT id FROM leave_types WHERE code = 'VL'", []
            )
            if not vl_type:  # VL type not found in system
                return {"statusCode": 500, "message": "VL leave type not found in the system"}  # return error

            vl_leave_type_id = vl_type[0]["id"]  # VL leave type ID for the VL reversal

            fl_result = query_insert(  # insert CREDIT reversal for FL balance
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApproval._generate_transaction_number(),  # unique transaction number
                    employee_id,                # employee being restored
                    leave_type_id,              # FL leave type ID
                    total_days,                 # days being restored
                    application_id,             # source leave application
                    start_date,                 # same date as original DEBIT
                    f"Leave returned/disapproved — {leave_type_code} deduction reversed",  # auto remarks
                ]
            )
            if fl_result["statusCode"] != 200:  # check if FL reversal failed
                return fl_result  # return the error

            recalculate_ledger_snapshots(employee_id, leave_type_id)  # recalculate FL snapshots after reversal

            vl_result = query_insert(  # insert CREDIT reversal for VL balance
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApproval._generate_transaction_number(),  # unique transaction number
                    employee_id,                # employee being restored
                    vl_leave_type_id,           # VL leave type ID
                    total_days,                 # days being restored
                    application_id,             # source leave application
                    start_date,                 # same date as original DEBIT
                    f"Leave returned/disapproved — VL deduction reversed for {leave_type_code}",  # auto remarks
                ]
            )
            if vl_result["statusCode"] != 200:  # check if VL reversal failed
                return vl_result  # return the error

            recalculate_ledger_snapshots(employee_id, vl_leave_type_id)  # recalculate VL snapshots after reversal

            return None  # both FL and VL reversals posted successfully

        if balance_type == "CHARGED_TO_VSC":  # PR — restore new VSC credits via per-credit log
            return LeaveApproval._restore_vsc(  # delegate to VSC-specific restoration
                employee_id=employee_id,
                application_id=application_id,
                start_date=start_date,
            )

        # SELF — restore the leave type's own balance
        if leave_type_code == "CTO":  # CTO deductions span multiple credits; use per-credit restoration
            return LeaveApproval._restore_cto(  # delegate to CTO-specific reversal that reads cto_deduction_log
                employee_id=employee_id,
                leave_type_id=leave_type_id,
                application_id=application_id,
                start_date=start_date,
            )

        if leave_type_code == "SL":  # SL may have used VSC credits — check log before regular reversal
            vsc_logs = fetch_query(  # check if any VSC deductions exist for this application
                "SELECT id FROM vsc_deduction_log WHERE leave_application_id = %s LIMIT 1",
                [application_id]
            )
            if vsc_logs:  # VSC was used for this SL leave — restore per-credit VSC balances
                return LeaveApproval._restore_vsc(  # delegate to VSC-specific restoration
                    employee_id=employee_id,
                    application_id=application_id,
                    start_date=start_date,
                )
            # No VSC entries — fall through to regular SL CREDIT reversal below

        insert_result = query_insert(  # insert CREDIT reversal for the leave type balance (VL, SL, VSC, etc.)
            """INSERT INTO leave_credit_transactions
                   (transaction_number, employee_id, leave_type_id, transaction_type,
                    amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
               VALUES (%s, %s, %s, 'CREDIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
            [
                LeaveApproval._generate_transaction_number(),  # generated transaction number
                employee_id,                 # employee being restored
                leave_type_id,               # leave type being reversed
                total_days,                  # days being restored
                application_id,              # source: the returned/disapproved leave application
                start_date,                  # same date as original DEBIT
                f"Leave returned/disapproved — {leave_type_code} deduction reversed",  # auto remarks
            ]
        )

        if insert_result["statusCode"] != 200:  # check if reversal insert failed
            return insert_result  # return the error

        recalculate_ledger_snapshots(employee_id, leave_type_id)  # recalculate snapshots after reversal

        return None  # reversal posted successfully

    # --------------------------
    # Process approval decision
    # --------------------------

    @staticmethod
    def decide(data: dict) -> dict:
        """
        Processes an approver's decision on a leave application.
        Supports all status transitions including re-activation from RETURNED/DISAPPROVED.

        Transition rules:
          active → RETURNED / DISAPPROVED : post CREDIT reversal (restore balance)
          RETURNED / DISAPPROVED → active  : re-post DEBIT (re-reserve balance); balance pre-checked first
          active → active                  : no balance change (e.g. FOR APPROVAL → APPROVED)
          reversed → reversed              : no balance change (e.g. RETURNED → DISAPPROVED)

        Parameters:
            data (dict): Decision fields — leave_application_id, approver_id, level,
                         status (FOR HRMO ACTION | FOR APPROVAL | APPROVED | RETURNED | DISAPPROVED),
                         remarks (optional).

        Returns:
            dict: statusCode 200 with the approval record, or an error dict.
        """
        try:
            required_fields = ["leave_application_id", "approver_id", "level", "status"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            valid_statuses = ("FOR HRMO ACTION", "FOR APPROVAL", "APPROVED", "RETURNED", "DISAPPROVED")  # all accepted status values including re-activation targets
            if data["status"] not in valid_statuses:  # validate status value
                return {  # return 400 if status is not recognised
                    "statusCode": 400,
                    "message": f"status must be one of: {', '.join(valid_statuses)}",
                }

            application = fetch_query(  # fetch the leave application with leave type details and computed totals from dates
                """SELECT la.*, lt.code AS leave_type_code, lt.balance_type,
                          (SELECT SUM(CASE WHEN lad.duration_type = 'FULL_DAY' THEN 1.0 ELSE 0.5 END)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS total_days,
                          (SELECT DATE_FORMAT(MIN(lad.leave_date), '%%Y-%%m-%%d')
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS start_date
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.id = %s AND la.is_deleted = 0""",
                [data["leave_application_id"]]
            )

            if not application:  # leave application not found or soft-deleted
                return {"statusCode": 404, "message": "Leave application not found"}  # return 404

            approver = fetch_query(  # verify the approver employee exists
                "SELECT id FROM employees WHERE id = %s", [data["approver_id"]]
            )

            if not approver:  # approver not found
                return {"statusCode": 404, "message": "Approver not found"}  # return 404

            app = application[0]  # shorthand for the application row
            current_status = app["status"]  # the application's status before this decision
            new_status = data["status"]  # the incoming status from the request
            total_days = float(app["total_days"] or 0.0)  # days in the application

            REVERSED_STATUSES = {"RETURNED", "DISAPPROVED"}  # statuses where balance was already restored

            # When re-activating from a reversed status, pre-check balance before any writes
            if current_status in REVERSED_STATUSES and new_status not in REVERSED_STATUSES:  # transitioning back to active
                if app["balance_type"] == "SELF" and app["leave_type_code"] not in ("CTO", "VSC"):  # standard SELF check
                    bal = fetch_query(  # get the employee's current balance for this leave type
                        "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                        [app["employee_id"], app["leave_type_id"]]
                    )
                    available = float(bal[0]["balance"]) if bal else 0.0  # current available balance
                    if available < total_days:  # insufficient balance to re-reserve
                        return {
                            "statusCode": 400,
                            "message": f"Insufficient {app['leave_type_code']} balance to re-activate. "
                                       f"Required: {total_days}, Available: {available}",
                        }

                elif app["balance_type"] == "CHARGED_TO_VL":  # FL — check VL balance
                    vl_bal = fetch_query(  # get the employee's current VL balance
                        """SELECT elb.balance FROM employee_leave_balances elb
                           JOIN leave_types lt ON lt.id = elb.leave_type_id
                           WHERE elb.employee_id = %s AND lt.code = 'VL'""",
                        [app["employee_id"]]
                    )
                    available = float(vl_bal[0]["balance"]) if vl_bal else 0.0  # current VL balance
                    if available < total_days:  # insufficient VL balance to re-reserve FL
                        return {
                            "statusCode": 400,
                            "message": f"Insufficient VL balance to re-activate FL leave. "
                                       f"Required: {total_days}, Available: {available}",
                        }

            insert_result = query_insert(  # insert the approval record
                """INSERT INTO leave_approvals
                       (leave_application_id, approver_id, level, status, remarks, approved_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())""",
                [
                    data["leave_application_id"],  # the application being acted on
                    data["approver_id"],           # the approver
                    data["level"],                 # approval level
                    new_status,                    # the decision
                    data.get("remarks"),           # optional remarks
                ]
            )

            if insert_result["statusCode"] != 200:  # check if insert failed
                return insert_result  # return the error

            # Transitioning FROM a reversed status TO an active status — re-post debit to re-reserve balance
            if current_status in REVERSED_STATUSES and new_status not in REVERSED_STATUSES:
                from model.leave_application import LeaveApplication  # local import to avoid circular dependency
                debit_error = LeaveApplication._post_debit(  # re-deduct the balance so it is reserved again
                    employee_id=app["employee_id"],
                    leave_type_id=app["leave_type_id"],
                    leave_type_code=app["leave_type_code"],
                    balance_type=app["balance_type"],
                    total_days=total_days,
                    application_id=app["id"],
                    start_date=str(app["start_date"]),  # same start date for correct ledger ordering
                )
                if debit_error:  # debit posting failed
                    return debit_error  # return the error

            # Transitioning FROM an active status TO a reversed status — post credit reversal to restore balance
            elif new_status in REVERSED_STATUSES and current_status not in REVERSED_STATUSES:
                reversal_error = LeaveApproval._post_reversal(  # restore the employee's balance
                    employee_id=app["employee_id"],
                    leave_type_id=app["leave_type_id"],
                    leave_type_code=app["leave_type_code"],
                    balance_type=app["balance_type"],
                    total_days=total_days,
                    application_id=app["id"],
                    start_date=str(app["start_date"]),  # same date as the original DEBIT for correct ledger pairing
                )
                if reversal_error:  # reversal posting failed
                    return reversal_error  # return the error

            # reversed → reversed (e.g. RETURNED → DISAPPROVED) or active → active: no balance change

            query(  # update the leave application status; reuse approver_id as status_updated_by
                "UPDATE leave_applications SET status = %s, status_updated_by = %s WHERE id = %s",
                [new_status, data["approver_id"], data["leave_application_id"]]
            )

            approval = fetch_query(  # fetch the full approval record just inserted
                "SELECT * FROM leave_approvals WHERE id = %s", [insert_result["insertId"]]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "message": f"Leave application status updated to '{new_status}' successfully",  # confirmation message
                "data": approval[0] if approval else None,  # the created approval record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get approvals by application
    # --------------------------

    @staticmethod
    def get_by_application(application_id: int) -> dict:
        """
        Retrieves all approval records for a specific leave application.

        Parameters:
            application_id (int): The leave application's primary key.

        Returns:
            dict: statusCode 200 with the list of approval records, or 404 if none found.
        """
        try:
            application = fetch_query(  # verify the application exists and is not soft-deleted
                "SELECT id FROM leave_applications WHERE id = %s AND is_deleted = 0", [application_id]
            )

            if not application:  # application not found or soft-deleted
                return {"statusCode": 404, "message": "Leave application not found"}  # return 404

            rows = fetch_query(  # fetch all approval records for the application
                """SELECT la.*, e.first_name, e.last_name, e.employee_number
                   FROM leave_approvals la
                   JOIN employees e ON e.id = la.approver_id
                   WHERE la.leave_application_id = %s
                   ORDER BY la.level ASC""",
                [application_id]
            )

            return {  # return results
                "statusCode": 200,
                "count": len(rows),  # number of approval records
                "data": rows,  # list of approval records with approver details
            } if rows else {  # return 404 if no approvals yet
                "statusCode": 404,
                "message": "No approval records found for this application",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
