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
