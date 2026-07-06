from pydantic import BaseModel  # import BaseModel as the base for all models
from gateway.mysql_gateway import fetch_query  # import fetch_query for SELECT operations
from datetime import date  # import date for default date handling


class Dashboard(BaseModel):
    """
    Model providing dashboard and analytics data for admin and division personnel.
    All methods are read-only; no data is modified.
    """

    # --------------------------
    # Employees on leave on a specific date
    # --------------------------

    @staticmethod
    def get_on_leave(employee_type: str, query_date: str) -> dict:
        """
        Returns a list of all active employees of the given type who have an
        approved (or pending) leave application that covers the specified date.
        Excludes RETURNED and DISAPPROVED applications.

        Parameters:
            employee_type (str): 'TEACHING' or 'NON_TEACHING'.
            query_date (str): The date to check (YYYY-MM-DD).

        Returns:
            dict: statusCode 200 with employee list, date, type, and count.
        """
        try:
            rows = fetch_query(  # fetch employees with leave covering the given date
                """SELECT e.id AS employee_id,
                          e.first_name, e.last_name, e.employee_number,
                          e.employee_type, e.position,
                          s.name AS school_name,
                          lt.code AS leave_type_code,
                          lt.name AS leave_type_name,
                          la.application_number,
                          la.status,
                          la.date_filed,
                          lad.leave_date,
                          lad.duration_type
                   FROM leave_application_dates lad
                   JOIN leave_applications la ON la.id = lad.leave_application_id
                   JOIN employees e ON e.id = la.employee_id
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   LEFT JOIN schools s ON s.id = e.school_id
                   WHERE lad.leave_date = %s
                     AND la.status NOT IN ('RETURNED', 'DISAPPROVED')
                     AND la.is_deleted = 0
                     AND e.is_active = 1
                     AND e.employee_type = %s
                   ORDER BY e.last_name ASC, e.first_name ASC""",
                [query_date, employee_type]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "date": query_date,  # the date queried
                "employee_type": employee_type,  # the type filtered
                "count": len(rows) if rows else 0,  # number of employees on leave
                "data": rows if rows else [],  # employee list with leave details
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Count of employees on leave + total on a specific date
    # --------------------------

    @staticmethod
    def get_on_leave_count(employee_type: str, query_date: str) -> dict:
        """
        Returns the count of employees currently on leave on the given date
        alongside the total headcount for that employee type.

        Parameters:
            employee_type (str): 'TEACHING' or 'NON_TEACHING'.
            query_date (str): The date to check (YYYY-MM-DD).

        Returns:
            dict: statusCode 200 with on_leave_count, total_employees, and not_on_leave_count.
        """
        try:
            on_leave_row = fetch_query(  # count distinct employees with active leave on this date
                """SELECT COUNT(DISTINCT la.employee_id) AS on_leave_count
                   FROM leave_application_dates lad
                   JOIN leave_applications la ON la.id = lad.leave_application_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE lad.leave_date = %s
                     AND la.status NOT IN ('RETURNED', 'DISAPPROVED')
                     AND la.is_deleted = 0
                     AND e.is_active = 1
                     AND e.employee_type = %s""",
                [query_date, employee_type]
            )

            total_row = fetch_query(  # count total active employees of this type
                "SELECT COUNT(*) AS total FROM employees WHERE employee_type = %s AND is_active = 1",
                [employee_type]
            )

            on_leave = int(on_leave_row[0]["on_leave_count"]) if on_leave_row else 0  # cast to int
            total = int(total_row[0]["total"]) if total_row else 0  # cast to int
            not_on_leave = total - on_leave  # employees present (total minus those on leave)

            return {  # return summary
                "statusCode": 200,  # success code
                "date": query_date,  # the date queried
                "employee_type": employee_type,  # the type filtered
                "total_employees": total,  # total active employees of this type
                "on_leave_count": on_leave,  # employees on leave on this date
                "not_on_leave_count": not_on_leave,  # employees not on leave
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Leave type breakdown per month (with date range)
    # --------------------------

    @staticmethod
    def get_leave_type_breakdown(employee_type: str, date_from: str, date_to: str) -> dict:
        """
        Returns a monthly breakdown of leave application counts and total days
        per leave type for employees of the given type within the specified date range.
        Excludes RETURNED and DISAPPROVED applications.

        Parameters:
            employee_type (str): 'TEACHING' or 'NON_TEACHING'.
            date_from (str): Start of the date range (YYYY-MM-DD).
            date_to (str): End of the date range (YYYY-MM-DD).

        Returns:
            dict: statusCode 200 with monthly grouped leave type counts.
        """
        try:
            rows = fetch_query(  # fetch leave counts grouped by month and leave type
                """SELECT lt.code AS leave_type_code,
                          lt.name AS leave_type_name,
                          YEAR(lad.leave_date) AS year,
                          MONTH(lad.leave_date) AS month,
                          COUNT(DISTINCT la.id) AS application_count,
                          COUNT(DISTINCT la.employee_id) AS employee_count,
                          SUM(CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END) AS total_days
                   FROM leave_application_dates lad
                   JOIN leave_applications la ON la.id = lad.leave_application_id
                   JOIN employees e ON e.id = la.employee_id
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE lad.leave_date BETWEEN %s AND %s
                     AND la.status NOT IN ('RETURNED', 'DISAPPROVED')
                     AND la.is_deleted = 0
                     AND e.is_active = 1
                     AND e.employee_type = %s
                   GROUP BY lt.code, lt.name, YEAR(lad.leave_date), MONTH(lad.leave_date)
                   ORDER BY year ASC, month ASC, lt.code ASC""",
                [date_from, date_to, employee_type]
            )

            MONTH_NAMES = {  # map month numbers to names
                1: "January", 2: "February", 3: "March", 4: "April",
                5: "May", 6: "June", 7: "July", 8: "August",
                9: "September", 10: "October", 11: "November", 12: "December",
            }

            # Group flat rows into month buckets
            month_map = {}  # key: (year, month) -> month entry dict
            for row in (rows or []):  # iterate each leave-type-month row
                key = (int(row["year"]), int(row["month"]))  # composite key

                if key not in month_map:  # init month bucket if not yet seen
                    month_map[key] = {
                        "year": key[0],  # calendar year
                        "month": key[1],  # month number
                        "month_name": MONTH_NAMES[key[1]],  # human-readable month name
                        "breakdown": [],  # per-leave-type entries
                        "total_applications": 0,  # running total applications for the month
                        "total_days": 0.0,  # running total days for the month
                    }

                app_count = int(row["application_count"])  # cast to int
                emp_count = int(row["employee_count"])  # cast to int
                total_days = round(float(row["total_days"]), 2)  # cast and round

                month_map[key]["breakdown"].append({  # add leave-type entry to this month
                    "leave_type_code": row["leave_type_code"],  # e.g. VL, SL
                    "leave_type_name": row["leave_type_name"],  # full name
                    "application_count": app_count,  # number of distinct applications
                    "employee_count": emp_count,  # number of distinct employees
                    "total_days": total_days,  # total leave days for this type this month
                })

                month_map[key]["total_applications"] += app_count  # accumulate month total
                month_map[key]["total_days"] = round(  # accumulate month total days
                    month_map[key]["total_days"] + total_days, 2
                )

            return {  # return grouped monthly breakdown
                "statusCode": 200,  # success code
                "employee_type": employee_type,  # type filter applied
                "date_from": date_from,  # range start
                "date_to": date_to,  # range end
                "count": len(month_map),  # number of months with data
                "data": list(month_map.values()),  # ordered list of month entries
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Latest pending leave applications
    # --------------------------

    @staticmethod
    def get_latest_pending(limit: int = 5) -> dict:
        """
        Returns the most recently filed leave applications that are still
        pending HRMO action, ordered by filing date descending.

        Parameters:
            limit (int): Maximum number of applications to return (default 5).

        Returns:
            dict: statusCode 200 with the latest pending leave applications.
        """
        try:
            rows = fetch_query(  # fetch latest pending applications with employee and leave type info
                """SELECT la.id, la.application_number, la.status,
                          la.date_filed, la.reason, la.created_at,
                          e.id AS employee_id, e.first_name, e.last_name,
                          e.employee_number, e.employee_type,
                          s.name AS school_name,
                          lt.code AS leave_type_code,
                          lt.name AS leave_type_name,
                          (SELECT MIN(lad.leave_date)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS start_date,
                          (SELECT MAX(lad.leave_date)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS end_date,
                          (SELECT COALESCE(SUM(
                               CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END
                           ), 0)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS total_days
                   FROM leave_applications la
                   JOIN employees e ON e.id = la.employee_id
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   LEFT JOIN schools s ON s.id = e.school_id
                   WHERE la.status = 'FOR HRMO ACTION'
                     AND la.is_deleted = 0
                   ORDER BY la.created_at DESC
                   LIMIT %s""",
                [limit]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "count": len(rows) if rows else 0,  # number of results returned
                "data": rows if rows else [],  # latest pending applications
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
