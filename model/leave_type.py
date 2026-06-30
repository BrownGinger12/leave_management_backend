from pydantic import BaseModel  # import BaseModel as the base for all models
from gateway.mysql_gateway import fetch_query  # import fetch_query for SELECT operations


class LeaveType(BaseModel):
    """
    Pydantic model representing a leave type record.

    Attributes:
        id: Primary key.
        code: Short leave type code (e.g. VL, SL, CTO).
        name: Full descriptive name of the leave type.
        balance_type: How the balance is sourced — SELF, CHARGED_TO_VL, or NONE.
        is_active: Whether this leave type is currently available for applications.
    """
    id: int  # primary key
    code: str  # short leave code
    name: str  # full name
    balance_type: str  # SELF, CHARGED_TO_VL, or NONE
    is_active: int  # 1 = active, 0 = inactive

    # --------------------------
    # Get all leave types
    # --------------------------

    @staticmethod
    def get_all() -> dict:
        """
        Retrieves all leave types ordered by code.

        Returns:
            dict: statusCode 200 with a list of all leave types.
        """
        try:
            rows = fetch_query(  # fetch all leave types ordered alphabetically by code
                "SELECT * FROM leave_types ORDER BY code ASC", []
            )

            return {  # return results
                "statusCode": 200,  # success code
                "count": len(rows),  # total number of leave types
                "data": rows if rows else [],  # list of leave type records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get teaching leave types (excludes SL and PR)
    # --------------------------

    @staticmethod
    def get_teaching(employee_id: int) -> dict:
        """
        Retrieves all leave types available for teaching staff, excluding
        Sick Leave (SL) and Personal Reason (PR) which are funded via VSC credits
        and are handled through separate balance rules. Validates the employee exists.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with a list of leave types excluding SL and PR,
                  or 404 if the employee is not found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            rows = fetch_query(  # fetch all leave types except SL and PR, ordered alphabetically
                "SELECT * FROM leave_types WHERE code NOT IN ('SL', 'PR') ORDER BY code ASC", []
            )

            return {  # return results
                "statusCode": 200,  # success code
                "employee_id": employee_id,  # echo back the employee ID for context
                "count": len(rows) if rows else 0,  # total number of leave types returned
                "data": rows if rows else [],  # list of leave type records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
