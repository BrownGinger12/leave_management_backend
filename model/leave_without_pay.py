from pydantic import BaseModel  # import BaseModel as the base for all models
from gateway.mysql_gateway import fetch_query  # import fetch_query for SELECT operations
from datetime import date  # import date for default year range


class LeaveWithoutPay(BaseModel):
    """
    Model for querying leave without pay (LWOP) records.
    LWOP dates are leave_application_dates rows where is_paid = 0.
    Excludes RETURNED and DISAPPROVED applications.
    """

    @staticmethod
    def get_paginated(employee_type: str, date_from: str, date_to: str,
                      page: int = 1, limit: int = 10) -> dict:
        """
        Returns a paginated list of leave-without-pay dates for employees of
        the given type within the specified date range.
        Each row represents one LWOP date tied to a leave application.

        Parameters:
            employee_type (str): 'TEACHING' or 'NON_TEACHING'.
            date_from (str): Start of the date range (YYYY-MM-DD).
            date_to (str): End of the date range (YYYY-MM-DD).
            page (int): Page number (1-indexed, default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated LWOP records, or an error dict.
        """
        try:
            page = max(page, 1)  # ensure page is at least 1
            limit = max(limit, 1)  # ensure limit is at least 1
            offset = (page - 1) * limit  # compute SQL offset from page number

            base_where = """
                FROM leave_application_dates lad
                JOIN leave_applications la ON la.id = lad.leave_application_id
                JOIN employees e ON e.id = la.employee_id
                JOIN leave_types lt ON lt.id = la.leave_type_id
                LEFT JOIN schools s ON s.id = e.school_id
                WHERE lad.is_paid = 0
                  AND la.status NOT IN ('RETURNED', 'DISAPPROVED')
                  AND la.is_deleted = 0
                  AND e.is_active = 1
                  AND e.employee_type = %s
                  AND lad.leave_date BETWEEN %s AND %s
            """  # shared WHERE clause reused for both count and data queries

            params = [employee_type, date_from, date_to]  # shared query parameters

            total_row = fetch_query(  # count total matching LWOP date rows
                f"SELECT COUNT(*) AS total {base_where}",
                params
            )
            total = int(total_row[0]["total"]) if total_row else 0  # cast to int

            rows = fetch_query(  # fetch paginated LWOP records
                f"""SELECT e.id AS employee_id,
                           e.first_name, e.last_name, e.employee_number,
                           e.employee_type, e.position,
                           s.name AS school_name,
                           la.id AS application_id,
                           la.application_number,
                           la.status,
                           la.date_filed,
                           lt.code AS leave_type_code,
                           lt.name AS leave_type_name,
                           lad.id AS leave_date_id,
                           lad.leave_date,
                           lad.duration_type,
                           lad.half_day_period,
                           CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END AS days_without_pay
                    {base_where}
                    ORDER BY lad.leave_date DESC, e.last_name ASC, e.first_name ASC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]
            )

            total_pages = (total + limit - 1) // limit if total > 0 else 1  # ceiling division for total pages

            return {  # return paginated response
                "statusCode": 200,  # success code
                "employee_type": employee_type,  # type filter applied
                "date_from": date_from,  # range start
                "date_to": date_to,  # range end
                "page": page,  # current page number
                "limit": limit,  # records per page
                "total": total,  # total matching LWOP date rows
                "total_pages": total_pages,  # total number of pages
                "count": len(rows) if rows else 0,  # records on this page
                "data": rows if rows else [],  # LWOP date records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
