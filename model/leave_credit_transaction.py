from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query  # import fetch_query for SELECT operations


class LeaveCreditTransaction(BaseModel):
    """
    Pydantic model representing a leave credit transaction ledger record.

    Attributes:
        id: Primary key.
        transaction_number: System-generated transaction number.
        employee_id: FK to the employee this transaction belongs to.
        leave_type_id: FK to the leave type being credited or debited.
        transaction_type: CREDIT or DEBIT.
        amount: Number of days affected.
        source_type: Origin of the transaction.
        source_id: ID of the source record.
        transaction_date: Date the transaction took effect.
        balance_snapshot_after: Employee balance immediately after this transaction.
        remarks: Optional notes.
    """
    id: int  # primary key
    transaction_number: str  # system-generated transaction number
    employee_id: int  # FK to employees
    leave_type_id: int  # FK to leave_types
    transaction_type: str  # CREDIT or DEBIT
    amount: float  # days affected
    source_type: str  # SPECIAL_ORDER, LEAVE_APPLICATION, MANUAL_ADJUSTMENT, SYSTEM_ADJUSTMENT
    source_id: int  # ID of the source record
    transaction_date: str  # effective date
    balance_snapshot_after: float  # balance after this transaction
    remarks: Optional[str] = None  # optional notes

    # --------------------------
    # Get transactions by employee (paginated)
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int, page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of ledger transactions for a specific employee
        ordered by transaction date descending. Joins with leave_types for context.

        Parameters:
            employee_id (int): The primary key of the employee.
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated transaction data, or 404 if employee not found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
                [employee_id]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get total count for pagination metadata
                "SELECT COUNT(*) as total FROM leave_credit_transactions WHERE employee_id = %s",
                [employee_id]
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch the paginated transactions with leave type details
                """SELECT lct.*,
                          lt.code AS leave_type_code,
                          lt.name AS leave_type_name
                   FROM leave_credit_transactions lct
                   JOIN leave_types lt ON lt.id = lct.leave_type_id
                   WHERE lct.employee_id = %s
                   ORDER BY lct.transaction_date DESC, lct.id DESC
                   LIMIT %s OFFSET %s""",
                [employee_id, limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,  # success code
                "employee": employee[0],  # basic employee info for context
                "count": len(rows),  # number of records in this page
                "total": total,  # total number of transactions across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": rows if rows else [],  # list of transactions, empty if none yet
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
