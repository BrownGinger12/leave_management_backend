from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
import uuid  # import uuid to generate unique transaction numbers


class LeaveCredit(BaseModel):
    """
    Pydantic model representing a leave credit transaction.
    Handles crediting of leave balances for any active leave type.

    Attributes:
        employee_id: FK to the employee being credited.
        leave_type_id: FK to the leave type.
        amount: Number of leave days to credit.
        transaction_date: Date the credit takes effect.
        remarks: Optional notes for the credit entry.
    """
    employee_id: int  # FK to employees table
    leave_type_id: int  # FK to leave_types table
    amount: float  # number of days to credit
    transaction_date: str  # date the credit takes effect (ISO format YYYY-MM-DD)
    remarks: Optional[str] = None  # optional notes for this credit

    # --------------------------
    # Generate transaction number
    # --------------------------

    @staticmethod
    def _generate_transaction_number() -> str:
        """
        Generates a unique transaction number using a UUID-based suffix.

        Returns:
            str: A transaction number in the format 'TXN-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"TXN-{suffix}"  # format as TXN-XXXXXXXX

    # --------------------------
    # Credit VL or SL balance
    # --------------------------

    @staticmethod
    def credit(data: dict) -> dict:
        """
        Credits leave days to an employee's balance for any active leave type.
        Inserts a CREDIT record into the ledger and updates the balance cache.

        Parameters:
            data (dict): Credit fields — employee_id, leave_type_id, amount,
                         transaction_date, remarks (optional).

        Returns:
            dict: statusCode 201 with the created transaction data, or an error dict.
        """
        try:
            required_fields = ["employee_id", "leave_type_id", "amount", "transaction_date"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            if data["amount"] <= 0:  # validate that amount is a positive number
                return {"statusCode": 400, "message": "amount must be greater than 0"}  # return 400 if invalid

            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            leave_type = fetch_query(  # fetch the leave type to validate it exists
                "SELECT id, code, is_active FROM leave_types WHERE id = %s", [data["leave_type_id"]]
            )

            if not leave_type:  # leave type not found
                return {"statusCode": 404, "message": "Leave type not found"}  # return 404

            if not leave_type[0]["is_active"]:  # check if leave type is still active
                return {"statusCode": 400, "message": "Leave type is inactive"}  # return 400 if disabled

            current_balance_row = fetch_query(  # get the employee's current cached balance for reporting balance_before
                "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                [data["employee_id"], data["leave_type_id"]]
            )

            balance_before = float(current_balance_row[0]["balance"]) if current_balance_row else 0.0  # cast Decimal to float; used in response

            transaction_number = LeaveCredit._generate_transaction_number()  # generate unique transaction number

            insert_result = query_insert(  # insert the CREDIT record (balance_snapshot_after=0, recalculate will fix it)
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'MANUAL_ADJUSTMENT', %s, %s, 0, %s)""",
                [
                    transaction_number,         # generated transaction number
                    data["employee_id"],        # employee being credited
                    data["leave_type_id"],      # leave type being credited
                    data["amount"],             # days credited
                    data["employee_id"],        # source_id references the employee for manual adjustments
                    data["transaction_date"],   # effective date of the credit
                    data.get("remarks"),        # optional remarks
                ]
            )

            if insert_result["statusCode"] != 200:  # check if ledger insert failed
                return insert_result  # return the error from the gateway

            balance_after = recalculate_ledger_snapshots(  # cascade-recalculate all snapshots in transaction_date order; also updates balance cache
                data["employee_id"], data["leave_type_id"]
            )

            transaction = fetch_query(  # fetch the full transaction record just inserted (now with corrected snapshot)
                "SELECT * FROM leave_credit_transactions WHERE id = %s",
                [insert_result["insertId"]]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": f"{leave_type[0]['code']} credit of {data['amount']} day(s) applied successfully",  # confirmation message
                "balance_before": balance_before,  # balance before this credit
                "balance_after": balance_after,  # balance after cascading recalculation
                "data": transaction[0] if transaction else None,  # the created ledger record with corrected snapshot
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Post forwarded balance credit
    # --------------------------

    @staticmethod
    def post_forwarded_balance(data: dict) -> dict:
        """
        Posts a FORWARDED_BALANCE CREDIT for a specific leave type at the start of a given year.
        Idempotent: if a FORWARDED_BALANCE record already exists for the employee, leave type,
        and year, it updates the amount instead of inserting a duplicate.

        Parameters:
            data (dict): Must contain employee_id, leave_type_id, amount, year.
                         Optional: remarks.

        Returns:
            dict: statusCode 201 (created) or 200 (updated) with transaction data, or an error dict.
        """
        try:
            required_fields = ["employee_id", "leave_type_id", "amount", "year"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            if float(data["amount"]) <= 0:  # validate that amount is a positive number
                return {"statusCode": 400, "message": "amount must be greater than 0"}  # return 400 if invalid

            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            leave_type = fetch_query(  # fetch the leave type to validate it exists and is active
                "SELECT id, code, is_active FROM leave_types WHERE id = %s", [data["leave_type_id"]]
            )

            if not leave_type:  # leave type not found
                return {"statusCode": 404, "message": "Leave type not found"}  # return 404

            if not leave_type[0]["is_active"]:  # check if leave type is still active
                return {"statusCode": 400, "message": "Leave type is inactive"}  # return 400 if disabled

            transaction_date = f"{int(data['year'])}-01-01"  # forwarded balance is always posted on Jan 1 of the given year

            existing = fetch_query(  # check for an existing FORWARDED_BALANCE record for idempotency
                """SELECT id, transaction_number FROM leave_credit_transactions
                   WHERE employee_id = %s
                     AND leave_type_id = %s
                     AND source_type = 'FORWARDED_BALANCE'
                     AND YEAR(transaction_date) = %s""",
                [data["employee_id"], data["leave_type_id"], int(data["year"])]
            )

            if existing:  # record already exists — update the amount instead
                update_result = query(  # update the existing forwarded balance amount
                    """UPDATE leave_credit_transactions
                       SET amount = %s, remarks = %s
                       WHERE id = %s""",
                    [float(data["amount"]), data.get("remarks"), existing[0]["id"]]
                )

                if update_result.get("statusCode") not in (None, 200):  # check if update failed
                    return update_result  # return error from gateway

                recalculate_ledger_snapshots(data["employee_id"], data["leave_type_id"])  # recalculate snapshots after update

                transaction = fetch_query(  # fetch the updated record
                    "SELECT * FROM leave_credit_transactions WHERE id = %s", [existing[0]["id"]]
                )

                return {  # return success response for update
                    "statusCode": 200,  # 200 OK — updated existing record
                    "message": f"Forwarded balance for {leave_type[0]['code']} year {data['year']} updated to {data['amount']} day(s)",
                    "data": transaction[0] if transaction else None,  # the updated ledger record
                }

            transaction_number = LeaveCredit._generate_transaction_number()  # generate unique transaction number

            insert_result = query_insert(  # insert the FORWARDED_BALANCE CREDIT record
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'FORWARDED_BALANCE', %s, %s, 0, %s)""",
                [
                    transaction_number,           # generated transaction number
                    data["employee_id"],          # employee being credited
                    data["leave_type_id"],        # leave type being credited
                    float(data["amount"]),        # forwarded balance days
                    data["employee_id"],          # source_id references the employee (no separate source record)
                    transaction_date,             # Jan 1 of the given year
                    data.get("remarks"),          # optional remarks
                ]
            )

            if insert_result["statusCode"] != 200:  # check if ledger insert failed
                return insert_result  # return the error from the gateway

            recalculate_ledger_snapshots(data["employee_id"], data["leave_type_id"])  # cascade-recalculate all snapshots

            transaction = fetch_query(  # fetch the full transaction record just inserted
                "SELECT * FROM leave_credit_transactions WHERE id = %s", [insert_result["insertId"]]
            )

            return {  # return success response for create
                "statusCode": 201,  # 201 Created
                "message": f"Forwarded balance of {data['amount']} day(s) for {leave_type[0]['code']} year {data['year']} posted successfully",
                "data": transaction[0] if transaction else None,  # the created ledger record with corrected snapshot
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
