from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
from flask import g  # import g to read the authenticated user set by the auth decorator
import uuid  # import uuid to generate unique monetization numbers


class LeaveMonetization(BaseModel):
    """
    Pydantic model for leave monetization records stored in leave_applications.
    Monetization converts unused VL and/or SL credits into monetary value by
    deducting the requested days from the employee's balance and recording them
    in leave_applications with leave_type = MNT.

    Attributes:
        employee_id: FK to the employee submitting the monetization.
        vl_days: Number of Vacation Leave days to monetize (0 if none).
        sl_days: Number of Sick Leave days to monetize (0 if none).
        date_filed: Date the monetization was filed (YYYY-MM-DD).
        remarks: Optional notes or reason for the monetization.
    """
    employee_id: int  # FK to employees table
    vl_days: float = 0.0  # VL days to deduct; may be 0 if only SL is monetized
    sl_days: float = 0.0  # SL days to deduct; may be 0 if only VL is monetized
    date_filed: str  # date the monetization was filed
    remarks: Optional[str] = None  # optional reason or notes

    # --------------------------
    # Generate monetization application number
    # --------------------------

    @staticmethod
    def _generate_monetization_number() -> str:
        """
        Generates a unique monetization number using a UUID-based suffix.

        Returns:
            str: A monetization number in the format 'MN-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"MN-{suffix}"  # format as MN-XXXXXXXX

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
    # Submit monetization
    # --------------------------

    @staticmethod
    def submit(data: dict) -> dict:
        """
        Submits a new leave monetization by inserting into leave_applications with
        leave_type = MNT. Validates the employee, checks VL/SL balances, then
        immediately posts DEBIT ledger entries for each deducted leave type.
        No dates are inserted into leave_application_dates — total days are derived
        from mnt_vl_days + mnt_sl_days.

        Parameters:
            data (dict): Must contain employee_id, date_filed. At least one of
                         vl_days or sl_days must be greater than 0.
                         Optional: remarks.

        Returns:
            dict with statusCode 201 and the created application data on success,
            or an error dict with statusCode 400/404/500.
        """
        try:
            employee_id = data.get("employee_id")  # read employee FK
            vl_days = float(data.get("vl_days", 0) or 0)  # VL days to monetize; default 0
            sl_days = float(data.get("sl_days", 0) or 0)  # SL days to monetize; default 0
            date_filed = (data.get("date_filed") or "").strip()  # date the form was filed
            remarks = (data.get("remarks") or "").strip() or None  # optional remarks

            if not employee_id or not date_filed:  # validate required fields
                return {"statusCode": 400, "message": "employee_id and date_filed are required"}

            if vl_days < 0 or sl_days < 0:  # days must be non-negative
                return {"statusCode": 400, "message": "vl_days and sl_days must be 0 or greater"}

            if vl_days == 0 and sl_days == 0:  # at least one must be positive
                return {"statusCode": 400, "message": "At least one of vl_days or sl_days must be greater than 0"}

            employee = fetch_query(  # verify employee exists
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}

            mnt_type = fetch_query(  # fetch MNT leave type ID
                "SELECT id FROM leave_types WHERE code = 'MNT' AND is_active = 1", []
            )
            if not mnt_type:  # MNT leave type not configured in DB
                return {"statusCode": 500, "message": "MNT leave type not found in system"}
            mnt_type_id = mnt_type[0]["id"]  # MNT leave type primary key

            vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # fetch VL leave type
            sl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'SL'", [])  # fetch SL leave type
            vl_type_id = vl_type[0]["id"] if vl_type else None  # VL leave type ID or None
            sl_type_id = sl_type[0]["id"] if sl_type else None  # SL leave type ID or None

            if vl_days > 0:  # check VL balance only if VL days are being monetized
                if not vl_type_id:  # VL leave type not configured
                    return {"statusCode": 500, "message": "VL leave type not found in system"}
                vl_bal = fetch_query(  # read current VL balance from cache
                    "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                    [employee_id, vl_type_id]
                )
                vl_balance = float(vl_bal[0]["balance"]) if vl_bal else 0.0  # default to 0 if no record
                if vl_balance < vl_days:  # insufficient VL balance
                    return {
                        "statusCode": 400,
                        "message": f"Insufficient VL balance. Available: {vl_balance}, Requested: {vl_days}",
                    }

            if sl_days > 0:  # check SL balance only if SL days are being monetized
                if not sl_type_id:  # SL leave type not configured
                    return {"statusCode": 500, "message": "SL leave type not found in system"}
                sl_bal = fetch_query(  # read current SL balance from cache
                    "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                    [employee_id, sl_type_id]
                )
                sl_balance = float(sl_bal[0]["balance"]) if sl_bal else 0.0  # default to 0 if no record
                if sl_balance < sl_days:  # insufficient SL balance
                    return {
                        "statusCode": 400,
                        "message": f"Insufficient SL balance. Available: {sl_balance}, Requested: {sl_days}",
                    }

            application_number = LeaveMonetization._generate_monetization_number()  # unique MN-XXXXXXXX identifier

            result = query_insert(  # insert leave_applications row for this monetization
                """INSERT INTO leave_applications
                       (application_number, employee_id, leave_type_id, date_filed,
                        reason, mnt_vl_days, mnt_sl_days, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'FOR HRMO ACTION')""",
                [
                    application_number,   # unique monetization number (MN-XXXXXXXX)
                    employee_id,          # employee submitting the monetization
                    mnt_type_id,          # MNT leave type FK
                    date_filed,           # date the monetization was filed
                    remarks or "",        # reason field holds the remarks
                    vl_days if vl_days > 0 else None,  # VL portion; NULL if none
                    sl_days if sl_days > 0 else None,  # SL portion; NULL if none
                ]
            )
            if result.get("statusCode") != 200:  # check for DB insert error
                return {"statusCode": 500, "message": "Failed to create monetization record"}

            application_id = result["insertId"]  # new leave_applications primary key

            if vl_days > 0:  # post VL debit only if VL days are included
                vl_txn = query_insert(  # insert DEBIT ledger entry for VL
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'DEBIT', %s, 'MONETIZATION', %s, %s, 0, %s)""",
                    [
                        LeaveMonetization._generate_transaction_number(),  # unique transaction number
                        employee_id,       # employee being debited
                        vl_type_id,        # VL leave type
                        vl_days,           # days deducted
                        application_id,    # source: the leave_applications row
                        date_filed,        # transaction date
                        f"Leave monetization {application_number} — VL deduction",  # audit remarks
                    ]
                )
                if vl_txn.get("statusCode") != 200:  # check if ledger insert failed
                    return {"statusCode": 500, "message": "Failed to post VL ledger debit"}
                recalculate_ledger_snapshots(employee_id, vl_type_id)  # update VL balance cache

            if sl_days > 0:  # post SL debit only if SL days are included
                sl_txn = query_insert(  # insert DEBIT ledger entry for SL
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'DEBIT', %s, 'MONETIZATION', %s, %s, 0, %s)""",
                    [
                        LeaveMonetization._generate_transaction_number(),  # unique transaction number
                        employee_id,       # employee being debited
                        sl_type_id,        # SL leave type
                        sl_days,           # days deducted
                        application_id,    # source: the leave_applications row
                        date_filed,        # transaction date
                        f"Leave monetization {application_number} — SL deduction",  # audit remarks
                    ]
                )
                if sl_txn.get("statusCode") != 200:  # check if ledger insert failed
                    return {"statusCode": 500, "message": "Failed to post SL ledger debit"}
                recalculate_ledger_snapshots(employee_id, sl_type_id)  # update SL balance cache

            record = fetch_query(  # fetch the created application record for the response
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s""",
                [application_id]
            )

            return {  # return success response
                "statusCode": 201,  # HTTP 201 Created
                "message": "Leave monetization submitted successfully",  # confirmation message
                "data": record[0] if record else {"id": application_id},  # return created record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get all (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves all leave monetization applications (leave_type = MNT) across all
        employees, ordered by date filed descending, with pagination.

        Parameters:
            page (int): The page number (1-indexed).
            limit (int): Number of records per page.

        Returns:
            dict with statusCode 200, pagination metadata, and data list.
        """
        try:
            offset = (page - 1) * limit  # compute the row offset for the current page

            rows = fetch_query(  # fetch paginated MNT applications with employee info
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE lt.code = 'MNT' AND la.is_deleted = 0
                   ORDER BY la.date_filed DESC, la.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            total_row = fetch_query(  # count total MNT records for pagination metadata
                """SELECT COUNT(*) AS total
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE lt.code = 'MNT' AND la.is_deleted = 0""",
                []
            )
            total = total_row[0]["total"] if total_row else 0  # total record count

            return {  # build paginated response
                "statusCode": 200,          # HTTP 200 OK
                "page": page,               # current page number
                "limit": limit,             # records per page
                "total": total,             # total matching records
                "pages": -(-total // limit) if limit else 1,  # ceiling division for total pages
                "data": rows if rows else [],  # monetization rows for this page
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get by ID
    # --------------------------

    @staticmethod
    def get_by_id(monetization_id: int) -> dict:
        """
        Retrieves a single leave monetization application by its leave_applications primary key.

        Parameters:
            monetization_id (int): The leave_applications.id of the monetization record.

        Returns:
            dict with statusCode 200 and data on success, or 404 if not found.
        """
        try:
            row = fetch_query(  # fetch the MNT application with employee info
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s AND lt.code = 'MNT' AND la.is_deleted = 0""",
                [monetization_id]
            )
            if not row:  # not found or soft-deleted
                return {"statusCode": 404, "message": "Leave monetization not found"}

            return {"statusCode": 200, "data": row[0]}  # return single record

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get by employee
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int) -> dict:
        """
        Retrieves all leave monetization applications (leave_type = MNT) for a specific
        employee, ordered by date filed descending.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict with statusCode 200 and data list, or 404 if employee not found.
        """
        try:
            employee = fetch_query(  # verify employee exists
                "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
                [employee_id]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}

            rows = fetch_query(  # fetch all MNT applications for this employee
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.employee_id = %s AND lt.code = 'MNT' AND la.is_deleted = 0
                   ORDER BY la.date_filed DESC, la.id DESC""",
                [employee_id]
            )

            return {  # build response
                "statusCode": 200,  # HTTP 200 OK
                "employee": employee[0],  # basic employee info
                "count": len(rows) if rows else 0,  # total records
                "data": rows if rows else [],  # monetization records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Soft delete with balance reversal
    # --------------------------

    @staticmethod
    def soft_delete(monetization_id: int) -> dict:
        """
        Soft-deletes a leave monetization record in leave_applications. Reverses the
        VL and/or SL deductions by posting CREDIT ledger entries unless the record
        is already RETURNED or DISAPPROVED (those statuses mean the balance was
        already restored by the approval workflow).

        Parameters:
            monetization_id (int): The leave_applications.id of the monetization to delete.

        Returns:
            dict with statusCode 200 on success, or an error dict.
        """
        try:
            row = fetch_query(  # fetch the MNT application before deleting
                """SELECT la.*, lt.code AS leave_type_code
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.id = %s AND lt.code = 'MNT' AND la.is_deleted = 0""",
                [monetization_id]
            )
            if not row:  # not found or already deleted
                return {"statusCode": 404, "message": "Leave monetization not found"}

            record = row[0]  # the leave_applications row
            employee_id = record["employee_id"]  # employee who owns the record
            status = record["status"]  # current approval status
            vl_days = float(record["mnt_vl_days"] or 0)  # VL days originally deducted
            sl_days = float(record["mnt_sl_days"] or 0)  # SL days originally deducted
            date_filed = str(record["date_filed"])  # original date filed for transaction date
            application_number = record["application_number"]  # MN-XXXXXXXX for audit remarks

            REVERSED_STATUSES = {"RETURNED", "DISAPPROVED"}  # these statuses already restored the balance

            if status not in REVERSED_STATUSES:  # only reverse if balance was not already restored
                vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # fetch VL type
                sl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'SL'", [])  # fetch SL type
                vl_type_id = vl_type[0]["id"] if vl_type else None  # VL type ID
                sl_type_id = sl_type[0]["id"] if sl_type else None  # SL type ID

                if vl_days > 0 and vl_type_id:  # restore VL balance if applicable
                    query_insert(  # insert CREDIT ledger entry to reverse the VL deduction
                        """INSERT INTO leave_credit_transactions
                               (transaction_number, employee_id, leave_type_id, transaction_type,
                                amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                           VALUES (%s, %s, %s, 'CREDIT', %s, 'MONETIZATION', %s, %s, 0, %s)""",
                        [
                            LeaveMonetization._generate_transaction_number(),  # unique transaction number
                            employee_id,       # employee receiving the credit
                            vl_type_id,        # VL leave type
                            vl_days,           # days being restored
                            monetization_id,   # source: the leave_applications record being deleted
                            date_filed,        # transaction date
                            f"Reversal of monetization {application_number} — VL restored",  # audit remarks
                        ]
                    )
                    recalculate_ledger_snapshots(employee_id, vl_type_id)  # update VL balance cache

                if sl_days > 0 and sl_type_id:  # restore SL balance if applicable
                    query_insert(  # insert CREDIT ledger entry to reverse the SL deduction
                        """INSERT INTO leave_credit_transactions
                               (transaction_number, employee_id, leave_type_id, transaction_type,
                                amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                           VALUES (%s, %s, %s, 'CREDIT', %s, 'MONETIZATION', %s, %s, 0, %s)""",
                        [
                            LeaveMonetization._generate_transaction_number(),  # unique transaction number
                            employee_id,       # employee receiving the credit
                            sl_type_id,        # SL leave type
                            sl_days,           # days being restored
                            monetization_id,   # source: the leave_applications record being deleted
                            date_filed,        # transaction date
                            f"Reversal of monetization {application_number} — SL restored",  # audit remarks
                        ]
                    )
                    recalculate_ledger_snapshots(employee_id, sl_type_id)  # update SL balance cache

            deleted_by = g.current_user.get("user_id") if hasattr(g, "current_user") else None  # admin performing the delete

            query(  # soft-delete the leave_applications record
                """UPDATE leave_applications
                   SET is_deleted = 1, deleted_at = NOW(), deleted_by = %s
                   WHERE id = %s""",
                [deleted_by, monetization_id]
            )

            return {"statusCode": 200, "message": "Leave monetization deleted successfully"}  # success response

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}
