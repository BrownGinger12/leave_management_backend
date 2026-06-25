from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
import uuid  # import uuid to generate unique transaction numbers


class MonthlyLeaveCredit(BaseModel):
    """
    Pydantic model representing a monthly VL/SL credit record.
    Tracks one credit entry per employee per leave type per month.
    Prevents double-crediting via a unique constraint on (employee_id, leave_type_id, year, month).

    Attributes:
        employee_id: FK to the employee being credited.
        leave_type_id: FK to the leave type (must be VL or SL).
        year: Calendar year of the credit (e.g. 2026).
        month: Calendar month of the credit (1–12).
        amount: Number of leave days to credit.
        transaction_date: Effective date of the credit.
        remarks: Optional notes for the ledger entry.
    """
    employee_id: int  # FK to employees table
    leave_type_id: int  # FK to leave_types table (VL or SL only)
    year: int  # calendar year of this credit
    month: int  # calendar month of this credit (1–12)
    amount: float  # number of days to credit
    transaction_date: str  # effective date (YYYY-MM-DD)
    remarks: Optional[str] = None  # optional notes for the ledger entry

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
    # Credit monthly VL or SL
    # --------------------------

    @staticmethod
    def credit(data: dict) -> dict:
        """
        Credits a monthly VL or SL amount for one employee for a given year and month.
        Inserts a CREDIT into the ledger, records in monthly_leave_credits, and updates
        the balance cache. Rejects duplicate credits for the same employee/type/year/month.

        Parameters:
            data (dict): Credit fields — employee_id, leave_type_id, year, month,
                         amount, transaction_date, remarks (optional).

        Returns:
            dict: statusCode 201 with credit details and balance change, or an error dict.
        """
        try:
            required_fields = ["employee_id", "leave_type_id", "year", "month",
                                "amount", "transaction_date"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            if not (1 <= int(data["month"]) <= 12):  # validate month is in valid range
                return {"statusCode": 400, "message": "month must be between 1 and 12"}  # return 400 if out of range

            if float(data["amount"]) <= 0:  # validate that amount is positive
                return {"statusCode": 400, "message": "amount must be greater than 0"}  # return 400 if zero or negative

            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            leave_type = fetch_query(  # fetch leave type and validate it is VL or SL
                "SELECT id, code, name, is_active FROM leave_types WHERE id = %s AND code IN ('VL', 'SL')",
                [data["leave_type_id"]]
            )

            if not leave_type:  # leave type not found or not VL/SL
                return {"statusCode": 400, "message": "Monthly credits are only applicable to VL and SL leave types"}  # return 400

            if not leave_type[0]["is_active"]:  # check the leave type is still active
                return {"statusCode": 400, "message": f"{leave_type[0]['code']} leave type is inactive"}  # return 400 if disabled

            existing = fetch_query(  # check if this employee/type/year/month was already credited
                """SELECT id FROM monthly_leave_credits
                   WHERE employee_id = %s AND leave_type_id = %s
                     AND year = %s AND month = %s""",
                [data["employee_id"], data["leave_type_id"], data["year"], data["month"]]
            )

            if existing:  # duplicate credit detected
                month_label = str(data["month"]).zfill(2)  # zero-pad month for display
                return {  # return 409 Conflict
                    "statusCode": 409,
                    "message": f"{leave_type[0]['code']} has already been credited for {data['year']}-{month_label}",
                }

            current_balance_row = fetch_query(  # get the employee's current cached balance for reporting balance_before
                "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                [data["employee_id"], data["leave_type_id"]]
            )

            balance_before = float(current_balance_row[0]["balance"]) if current_balance_row else 0.0  # cast Decimal to float; used in response

            transaction_number = MonthlyLeaveCredit._generate_transaction_number()  # generate unique transaction number

            txn_result = query_insert(  # insert the CREDIT entry (source_id=0 placeholder, balance_snapshot_after=0, recalculate will fix it)
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'CREDIT', %s, 'SYSTEM_ADJUSTMENT', 0, %s, 0, %s)""",
                [
                    transaction_number,          # unique transaction number
                    data["employee_id"],         # employee being credited
                    data["leave_type_id"],       # leave type (VL or SL)
                    float(data["amount"]),       # days credited
                    data["transaction_date"],    # effective date
                    data.get("remarks"),         # optional remarks
                ]
            )

            if txn_result["statusCode"] != 200:  # check if ledger insert failed
                return txn_result  # return the error from the gateway

            transaction_id = txn_result["insertId"]  # capture the new ledger record ID

            mlc_result = query_insert(  # insert the monthly credit record
                """INSERT INTO monthly_leave_credits
                       (employee_id, leave_type_id, year, month, amount, transaction_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [
                    data["employee_id"],    # employee
                    data["leave_type_id"],  # leave type
                    data["year"],           # credit year
                    data["month"],          # credit month
                    float(data["amount"]),  # days credited
                    transaction_id,         # link to the ledger record
                ]
            )

            if mlc_result["statusCode"] != 200:  # check if monthly credit insert failed
                return mlc_result  # return the error from the gateway

            monthly_credit_id = mlc_result["insertId"]  # capture the new monthly credit ID

            query(  # update ledger source_id to point to the monthly_leave_credits record (now that we have its id)
                "UPDATE leave_credit_transactions SET source_id = %s WHERE id = %s",
                [monthly_credit_id, transaction_id]
            )

            balance_after = recalculate_ledger_snapshots(  # cascade-recalculate all snapshots in transaction_date order; also updates balance cache
                data["employee_id"], data["leave_type_id"]
            )

            rows = fetch_query(  # fetch the created monthly credit with joined details
                """SELECT mlc.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          lct.transaction_number, lct.transaction_type,
                          lct.balance_snapshot_after, lct.transaction_date, lct.remarks AS ledger_remarks
                   FROM monthly_leave_credits mlc
                   JOIN leave_types lt ON lt.id = mlc.leave_type_id
                   JOIN leave_credit_transactions lct ON lct.id = mlc.transaction_id
                   WHERE mlc.id = %s""",
                [monthly_credit_id]
            )

            month_label = str(data["month"]).zfill(2)  # zero-pad month for display message

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": f"{leave_type[0]['code']} credit of {data['amount']} day(s) applied for {data['year']}-{month_label}",  # confirmation message
                "balance_before": balance_before,  # balance before this credit
                "balance_after": balance_after,  # balance after cascading recalculation
                "data": rows[0] if rows else None,  # the created monthly credit with ledger details (corrected snapshot)
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get monthly credits by employee and year (with ledger)
    # --------------------------

    @staticmethod
    def get_by_employee_and_year(employee_id: int, year: int) -> dict:
        """
        Retrieves all monthly VL/SL credit records for a specific employee in a given
        calendar year, each enriched with its linked ledger transaction data.

        Parameters:
            employee_id (int): The employee's primary key.
            year (int): The calendar year to filter by (e.g. 2026).

        Returns:
            dict: statusCode 200 with a list of monthly credits each including ledger data,
                  or 404 if the employee is not found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
                [employee_id]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            rows = fetch_query(  # fetch all monthly credits joined with leave type and ledger data
                """SELECT mlc.*,
                          lt.code AS leave_type_code,
                          lt.name AS leave_type_name,
                          lct.transaction_number,
                          lct.transaction_type,
                          lct.balance_snapshot_after,
                          lct.transaction_date,
                          lct.source_type,
                          lct.remarks AS ledger_remarks
                   FROM monthly_leave_credits mlc
                   JOIN leave_types lt ON lt.id = mlc.leave_type_id
                   JOIN leave_credit_transactions lct ON lct.id = mlc.transaction_id
                   WHERE mlc.employee_id = %s AND mlc.year = %s
                   ORDER BY mlc.month ASC, lt.code ASC""",
                [employee_id, year]
            )

            return {  # return results
                "statusCode": 200,  # success code
                "employee": employee[0],  # basic employee info for context
                "year": year,  # the year filter applied
                "count": len(rows),  # total records returned
                "data": rows if rows else [],  # list of monthly credits with embedded ledger data
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
