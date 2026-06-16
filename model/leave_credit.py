from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert  # import gateway functions
import uuid  # import uuid to generate unique transaction numbers


class LeaveCredit(BaseModel):
    """
    Pydantic model representing a leave credit transaction.
    Handles crediting of VL and SL leave balances only.

    Attributes:
        employee_id: FK to the employee being credited.
        leave_type_id: FK to the leave type (must be VL or SL).
        amount: Number of leave days to credit.
        transaction_date: Date the credit takes effect.
        remarks: Optional notes for the credit entry.
    """
    employee_id: int  # FK to employees table
    leave_type_id: int  # FK to leave_types table (VL or SL only)
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
        Credits leave days to an employee's VL or SL balance.
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

            leave_type = fetch_query(  # fetch the leave type to validate it is VL or SL
                "SELECT id, code, is_active FROM leave_types WHERE id = %s", [data["leave_type_id"]]
            )

            if not leave_type:  # leave type not found
                return {"statusCode": 404, "message": "Leave type not found"}  # return 404

            if leave_type[0]["code"] not in ("VL", "SL"):  # only VL and SL are allowed for crediting
                return {"statusCode": 400, "message": "Only Vacation Leave (VL) and Sick Leave (SL) can be credited through this endpoint"}  # return 400 for unsupported types

            if not leave_type[0]["is_active"]:  # check if leave type is still active
                return {"statusCode": 400, "message": "Leave type is inactive"}  # return 400 if disabled

            current_balance_row = fetch_query(  # get the employee's current cached balance for this leave type
                "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                [data["employee_id"], data["leave_type_id"]]
            )

            current_balance = float(current_balance_row[0]["balance"]) if current_balance_row else 0.0  # cast Decimal to float (MySQL DECIMAL returns decimal.Decimal)
            new_balance = round(current_balance + data["amount"], 2)  # compute new balance after credit

            transaction_number = LeaveCredit._generate_transaction_number()  # generate unique transaction number

            insert_result = query_insert(  # insert the CREDIT record into the ledger
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'MANUAL_ADJUSTMENT', %s, %s, %s, %s)""",
                [
                    transaction_number,         # generated transaction number
                    data["employee_id"],        # employee being credited
                    data["leave_type_id"],      # leave type (VL or SL)
                    data["amount"],             # days credited
                    data["employee_id"],        # source_id references the employee for manual adjustments
                    data["transaction_date"],   # effective date of the credit
                    new_balance,                # balance after this credit is applied
                    data.get("remarks"),        # optional remarks
                ]
            )

            if insert_result["statusCode"] != 200:  # check if ledger insert failed
                return insert_result  # return the error from the gateway

            query(  # upsert the employee_leave_balances cache with the new balance
                """INSERT INTO employee_leave_balances (employee_id, leave_type_id, balance)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE balance = %s""",
                [data["employee_id"], data["leave_type_id"], new_balance, new_balance]
            )

            transaction = fetch_query(  # fetch the full transaction record just inserted
                "SELECT * FROM leave_credit_transactions WHERE id = %s",
                [insert_result["insertId"]]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": f"{leave_type[0]['code']} credit of {data['amount']} day(s) applied successfully",  # confirmation message
                "balance_before": current_balance,  # balance before this credit
                "balance_after": new_balance,  # balance after this credit
                "data": transaction[0] if transaction else None,  # the created ledger record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
