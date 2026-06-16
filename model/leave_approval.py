from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert  # import gateway functions
from datetime import date  # import date for transaction date
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
    # Post debit to ledger
    # --------------------------

    @staticmethod
    def _post_debit(employee_id: int, leave_type_id: int, leave_type_code: str,
                    balance_type: str, total_days: float, application_id: int) -> dict | None:
        """
        Posts a DEBIT entry to the ledger and updates the balance cache.
        Called only when a leave application is fully approved.
        No debit is posted when balance_type is NONE.

        Parameters:
            employee_id (int): The employee whose balance is being deducted.
            leave_type_id (int): The leave type being deducted.
            leave_type_code (str): The leave type code (VL, SL, FL, etc.).
            balance_type (str): SELF, CHARGED_TO_VL, or NONE.
            total_days (float): Number of days to deduct.
            application_id (int): The source leave application ID.

        Returns:
            dict | None: An error dict if debit fails, None on success.
        """
        if balance_type == "NONE":  # no deduction required for this leave type
            return None  # skip ledger posting

        if balance_type == "CHARGED_TO_VL":  # FL is deducted from VL balance
            vl_type = fetch_query(  # get the VL leave type ID for the ledger entry
                "SELECT id FROM leave_types WHERE code = 'VL'", []
            )
            if not vl_type:  # VL type not found in system
                return {"statusCode": 500, "message": "VL leave type not found in the system"}  # return error

            deduct_leave_type_id = vl_type[0]["id"]  # use VL's ID for the deduction
            deduct_code = "VL"  # the balance being deducted is VL
        else:  # SELF — deduct from the leave type's own balance
            deduct_leave_type_id = leave_type_id  # use the original leave type ID
            deduct_code = leave_type_code  # the balance being deducted is the same as the leave type

        balance_row = fetch_query(  # get the current cached balance before deduction
            "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
            [employee_id, deduct_leave_type_id]
        )

        current_balance = float(balance_row[0]["balance"]) if balance_row else 0.0  # cast Decimal to float
        new_balance = round(current_balance - total_days, 2)  # compute balance after deduction
        transaction_number = LeaveApproval._generate_transaction_number()  # generate unique transaction number

        insert_result = query_insert(  # insert the DEBIT record into the ledger
            """INSERT INTO leave_credit_transactions
                   (transaction_number, employee_id, leave_type_id, transaction_type,
                    amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
               VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, %s, %s)""",
            [
                transaction_number,          # generated transaction number
                employee_id,                 # employee being debited
                deduct_leave_type_id,        # leave type being debited (VL for FL, own type for SELF)
                total_days,                  # days being deducted
                application_id,              # source: the approved leave application
                date.today().isoformat(),    # transaction date is today (approval date)
                new_balance,                 # balance snapshot after this deduction
                f"Leave application approved — {deduct_code} deducted",  # auto remarks
            ]
        )

        if insert_result["statusCode"] != 200:  # check if ledger insert failed
            return insert_result  # return the error

        query(  # upsert the employee_leave_balances cache with the new balance
            """INSERT INTO employee_leave_balances (employee_id, leave_type_id, balance)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE balance = %s""",
            [employee_id, deduct_leave_type_id, new_balance, new_balance]
        )

        return None  # debit posted successfully

    # --------------------------
    # Process approval decision
    # --------------------------

    @staticmethod
    def decide(data: dict) -> dict:
        """
        Processes an approver's decision on a leave application.
        - APPROVED: inserts approval record, posts DEBIT to ledger, updates balance, sets application to APPROVED.
        - REJECTED: inserts approval record, sets application to REJECTED.

        Parameters:
            data (dict): Decision fields — leave_application_id, approver_id, level,
                         status (APPROVED or REJECTED), remarks (optional).

        Returns:
            dict: statusCode 200 with the approval record, or an error dict.
        """
        try:
            required_fields = ["leave_application_id", "approver_id", "level", "status"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            if data["status"] not in ("APPROVED", "REJECTED"):  # validate status value
                return {"statusCode": 400, "message": "status must be APPROVED or REJECTED"}  # return 400 if invalid

            application = fetch_query(  # fetch the leave application with its leave type details
                """SELECT la.*, lt.code as leave_type_code, lt.balance_type
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.id = %s""",
                [data["leave_application_id"]]
            )

            if not application:  # leave application not found
                return {"statusCode": 404, "message": "Leave application not found"}  # return 404

            if application[0]["status"] != "PENDING":  # application must be pending to be acted on
                return {  # return 400 if already processed
                    "statusCode": 400,
                    "message": f"Leave application is already {application[0]['status']} and cannot be acted on",
                }

            approver = fetch_query(  # verify the approver employee exists
                "SELECT id FROM employees WHERE id = %s", [data["approver_id"]]
            )

            if not approver:  # approver not found
                return {"statusCode": 404, "message": "Approver not found"}  # return 404

            insert_result = query_insert(  # insert the approval record
                """INSERT INTO leave_approvals
                       (leave_application_id, approver_id, level, status, remarks, approved_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())""",
                [
                    data["leave_application_id"],  # the application being acted on
                    data["approver_id"],           # the approver
                    data["level"],                 # approval level
                    data["status"],                # APPROVED or REJECTED
                    data.get("remarks"),           # optional remarks
                ]
            )

            if insert_result["statusCode"] != 200:  # check if insert failed
                return insert_result  # return the error

            if data["status"] == "APPROVED":  # handle approval path
                app = application[0]  # shorthand for the application row

                debit_error = LeaveApproval._post_debit(  # post debit to ledger and update balance
                    employee_id=app["employee_id"],
                    leave_type_id=app["leave_type_id"],
                    leave_type_code=app["leave_type_code"],
                    balance_type=app["balance_type"],
                    total_days=float(app["total_days"]),  # cast Decimal to float
                    application_id=app["id"],
                )

                if debit_error:  # debit posting failed
                    return debit_error  # return the error

            query(  # update the leave application status to match the decision
                "UPDATE leave_applications SET status = %s WHERE id = %s",
                [data["status"], data["leave_application_id"]]
            )

            approval = fetch_query(  # fetch the full approval record just inserted
                "SELECT * FROM leave_approvals WHERE id = %s", [insert_result["insertId"]]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "message": f"Leave application {data['status'].lower()} successfully",  # confirmation message
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
            application = fetch_query(  # verify the application exists
                "SELECT id FROM leave_applications WHERE id = %s", [application_id]
            )

            if not application:  # application not found
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
