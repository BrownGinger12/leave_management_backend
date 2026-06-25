from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional, List  # import Optional and List for type hints
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
from datetime import date  # import date for date parsing, comparison, and expiry computation
import uuid  # import uuid to generate unique application and transaction numbers


class ServiceCreditApplication(BaseModel):
    """
    Pydantic model representing a Service Credit application (CTO or VSC).

    Attributes:
        employee_id: FK to the employee submitting the application.
        special_order_id: FK to special_orders.id — the Special Order authorizing this credit.
        type: Credit type — CTO (Compensatory Time Off) or VSC (Vacation Service Credits).
        hours_rendered: Total hours the employee rendered during the activity.
        participation_dates: List of individual dates the employee participated.
        date_filed: Date the application was submitted (YYYY-MM-DD).
        date_of_upload: Date the supporting document was uploaded (YYYY-MM-DD).
        uploaded_by: FK to employees.id — the employee who uploaded the supporting document.
    """
    employee_id: int  # FK to employees table
    special_order_id: int  # FK to special_orders.id; the SO authorizing this credit
    hours_rendered: float  # hours the employee rendered during the activity
    participation_dates: List[str]  # individual participation dates as YYYY-MM-DD strings
    date_filed: str  # date the application was submitted
    date_of_upload: Optional[str] = None  # date the supporting document was uploaded
    uploaded_by: Optional[int] = None  # FK to employees.id; the employee who uploaded the document

    # --------------------------
    # Generate application number
    # --------------------------

    @staticmethod
    def _generate_application_number() -> str:
        """
        Generates a unique service credit application number using a UUID-based suffix.

        Returns:
            str: An application number in the format 'SC-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"SC-{suffix}"  # format as SC-XXXXXXXX

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
    # Post credit to ledger on submission
    # --------------------------

    @staticmethod
    def _post_credit(employee_id: int, application_id: int, credit_type: str,
                     balance_earned: float, application_number: str,
                     date_filed: str) -> dict | None:
        """
        Posts a CREDIT to the ledger immediately when a service credit application is submitted.
        The credit is posted for the leave type matching the application type (CTO or VSC).
        Uses recalculate_ledger_snapshots to keep balance_snapshot_after consistent.

        Parameters:
            employee_id (int): The employee receiving the credit.
            application_id (int): The source service credit application ID.
            credit_type (str): 'CTO' or 'VSC' — determines which leave balance is credited.
            balance_earned (float): Number of days to credit.
            application_number (str): The application number for the ledger remarks.
            date_filed (str): Date filed used as the transaction date (YYYY-MM-DD).

        Returns:
            dict | None: An error dict if posting fails, None on success.
        """
        leave_type = fetch_query(  # look up the leave type by code (CTO or VSC)
            "SELECT id FROM leave_types WHERE code = %s AND is_active = 1", [credit_type]
        )

        if not leave_type:  # leave type not found or inactive
            return {"statusCode": 500, "message": f"{credit_type} leave type not found or is inactive"}  # return error

        leave_type_id = leave_type[0]["id"]  # the leave_type_id for CTO or VSC

        result = query_insert(  # insert the CREDIT record into the ledger
            """INSERT INTO leave_credit_transactions
                   (transaction_number, employee_id, leave_type_id, transaction_type,
                    amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
               VALUES (%s, %s, %s, 'CREDIT', %s, 'SPECIAL_ORDER', %s, %s, 0, %s)""",
            [
                ServiceCreditApplication._generate_transaction_number(),  # unique transaction number
                employee_id,           # employee being credited
                leave_type_id,         # CTO or VSC leave type
                balance_earned,        # computed balance days
                application_id,        # source_id: this service credit application
                date_filed,            # transaction date = date filed
                f"{credit_type} credit from application {application_number}",  # auto remarks
            ]
        )

        if result["statusCode"] != 200:  # check if ledger insert failed
            return result  # return the error

        recalculate_ledger_snapshots(employee_id, leave_type_id)  # cascade-recalculate all snapshots for this leave type

        return None  # credit posted successfully

    # --------------------------
    # Attach participation dates to a row
    # --------------------------

    @staticmethod
    def _with_dates(row: dict) -> dict:
        """
        Returns a copy of an application row with its participation dates attached
        as a list under the key 'participation_dates'.

        Parameters:
            row (dict): A service_credit_applications record from the database.

        Returns:
            dict: The application row with 'participation_dates' list included.
        """
        if not row:  # nothing to do if row is empty/None
            return row  # return as-is
        result = dict(row)  # copy the row so the original is not mutated
        dates = fetch_query(  # fetch all participation dates for this application
            """SELECT date FROM service_credit_dates
               WHERE service_credit_application_id = %s
               ORDER BY date ASC""",
            [row["id"]]
        )
        result["participation_dates"] = [str(d["date"]) for d in dates] if dates else []  # attach dates as a string list
        return result  # return the enriched copy

    # --------------------------
    # Submit service credit application
    # --------------------------

    @staticmethod
    def submit(data: dict) -> dict:
        """
        Submits a new CTO or VSC service credit application.
        The credit type (CTO or VSC) is determined automatically from the employee's type:
        TEACHING employees receive VSC; NON_TEACHING employees receive CTO.
        Computes balance_earned from hours_rendered (every 8 hours = 1.5 days).
        valid_until is auto-computed as 1 year from the latest participation date (CTO only).
        Credit is posted to the ledger immediately on submission — no approval step.

        Parameters:
            data (dict): Application fields — employee_id, special_order_id,
                         hours_rendered, participation_dates (list of YYYY-MM-DD strings),
                         date_filed.

        Returns:
            dict: statusCode 201 with the created application data, or an error dict.
        """
        try:
            required_fields = [  # fields that must be present in the request
                "employee_id", "special_order_id", "hours_rendered",
                "participation_dates", "date_filed"
            ]

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            participation_dates = data["participation_dates"]  # extract the dates list

            if not isinstance(participation_dates, list) or len(participation_dates) == 0:  # validate the dates list
                return {"statusCode": 400, "message": "participation_dates must be a non-empty list of date strings"}  # return 400

            hours = float(data["hours_rendered"])  # cast to float for arithmetic

            if hours <= 0:  # validate hours rendered is a positive number
                return {"statusCode": 400, "message": "hours_rendered must be greater than 0"}  # return 400 if invalid

            parsed_dates = []  # list to hold validated date objects
            for d in participation_dates:  # loop through each provided date string
                try:
                    parsed_dates.append(date.fromisoformat(str(d)))  # parse and collect valid date
                except ValueError:  # catch invalid date format
                    return {"statusCode": 400, "message": f"Invalid date format: {d}. Expected YYYY-MM-DD"}  # return 400

            balance_earned = round(hours / 8 * 1.5, 2)  # compute credit: every 8 hours = 1.5 days

            latest_date = max(parsed_dates)  # find the latest participation date for auto expiry

            employee = fetch_query(  # fetch the employee to verify existence and determine credit type
                "SELECT id, employee_type FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            employee_type = employee[0]["employee_type"]  # TEACHING or NON_TEACHING

            # derive credit type from employee classification
            if employee_type == "TEACHING":  # teaching employees earn VSC
                credit_type = "VSC"  # assign VSC for teaching personnel
            elif employee_type == "NON_TEACHING":  # non-teaching employees earn CTO
                credit_type = "CTO"  # assign CTO for non-teaching personnel
            else:  # unrecognised employee type
                return {"statusCode": 400, "message": f"Unrecognised employee_type '{employee_type}'"}  # return 400

            valid_until = None  # VSC has no expiry; CTO expiry is always auto-computed below
            if credit_type == "CTO":  # CTO credits expire 1 year from the latest participation date
                try:
                    valid_until = latest_date.replace(year=latest_date.year + 1).isoformat()  # 1 year from latest date, same month/day
                except ValueError:  # handles Feb 29 edge case when next year is not a leap year
                    valid_until = latest_date.replace(year=latest_date.year + 1, day=28).isoformat()  # fall back to Feb 28

            special_order = fetch_query(  # verify the Special Order exists and get date_of_activity for VSC routing
                "SELECT id, date_of_activity FROM special_orders WHERE id = %s", [data["special_order_id"]]
            )

            if not special_order:  # Special Order not found
                return {"statusCode": 404, "message": "Special Order not found"}  # return 404

            if data.get("uploaded_by") is not None:  # only validate if uploaded_by was provided
                uploader = fetch_query(  # verify the uploader employee exists
                    "SELECT id FROM employees WHERE id = %s", [data["uploaded_by"]]
                )
                if not uploader:  # uploader employee not found
                    return {"statusCode": 404, "message": "Uploader employee not found"}  # return 404

            application_number = ServiceCreditApplication._generate_application_number()  # generate unique application number

            result = query_insert(  # insert the service credit application
                """INSERT INTO service_credit_applications
                       (application_number, employee_id, special_order_id, type,
                        hours_rendered, balance_earned, valid_until,
                        date_filed, date_of_upload, uploaded_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    application_number,              # generated application number
                    data["employee_id"],             # employee submitting the application
                    data["special_order_id"],        # FK to special_orders.id; the SO authorizing this credit
                    credit_type,                     # CTO (NON_TEACHING) or VSC (TEACHING) — auto-derived
                    hours,                           # hours rendered
                    balance_earned,                  # computed balance: hours / 8 * 1.5
                    valid_until,                     # 1 year from latest participation date (CTO only); NULL for VSC
                    data["date_filed"],              # date the application was filed
                    data.get("date_of_upload"),      # date the supporting document was uploaded
                    data.get("uploaded_by"),         # FK to employees.id; the employee who uploaded the document
                ]
            )

            if result["statusCode"] != 200:  # check if the insert failed
                return result  # return the error from the gateway

            application_id = result["insertId"]  # capture the new application's ID

            for d in parsed_dates:  # insert each participation date into the child table
                query_insert(  # insert one row per participation date
                    """INSERT INTO service_credit_dates
                           (service_credit_application_id, date)
                       VALUES (%s, %s)""",
                    [application_id, d.isoformat()]  # link to the parent application
                )

            credit_error = ServiceCreditApplication._post_credit(  # auto-credit the balance immediately on submission
                employee_id=data["employee_id"],
                application_id=application_id,
                credit_type=credit_type,            # CTO or VSC — auto-derived from employee type
                balance_earned=balance_earned,
                application_number=application_number,
                date_filed=data["date_filed"],
            )

            if credit_error:  # credit posting failed
                return credit_error  # return the error

            if credit_type == "CTO":  # CTO credits need per-credit balance tracking for leave deduction
                cto_balance_result = query_insert(  # insert a balance record for this CTO credit
                    """INSERT INTO cto_credit_balances
                           (service_credit_application_id, employee_id, original_balance, remaining_balance, valid_until)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [
                        application_id,          # FK to the service credit application
                        data["employee_id"],      # employee who owns this credit
                        balance_earned,           # original credit amount
                        balance_earned,           # remaining starts equal to original
                        valid_until,             # expiry date auto-computed from latest participation date
                    ]
                )
                if cto_balance_result["statusCode"] != 200:  # check if insert failed
                    return cto_balance_result  # return the error

            if credit_type == "VSC":  # VSC credits are split into two period tables based on date_of_activity
                activity_date = date.fromisoformat(  # parse the special order's activity date for period routing
                    str(special_order[0]["date_of_activity"])
                )
                vsc_table = (  # choose old table for activities before Oct 2024, new table otherwise
                    "vsc_old_credit_balances" if activity_date < date(2024, 10, 1)
                    else "vsc_new_credit_balances"
                )
                vsc_balance_result = query_insert(  # insert a balance record into the appropriate VSC period table
                    f"""INSERT INTO {vsc_table}
                           (service_credit_application_id, employee_id, original_balance, remaining_balance)
                       VALUES (%s, %s, %s, %s)""",
                    [
                        application_id,       # FK to the service credit application
                        data["employee_id"],  # employee who owns this credit
                        balance_earned,       # original credit amount
                        balance_earned,       # remaining starts equal to original
                    ]
                )
                if vsc_balance_result["statusCode"] != 200:  # check if insert failed
                    return vsc_balance_result  # return the error

            rows = fetch_query(  # fetch the full created application record with SO and employee info
                """SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                          e.first_name, e.last_name, e.employee_number
                   FROM service_credit_applications sca
                   JOIN special_orders so ON so.id = sca.special_order_id
                   JOIN employees e ON e.id = sca.employee_id
                   WHERE sca.id = %s""",
                [application_id]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": f"{credit_type} application submitted successfully",  # confirmation message with derived type
                "data": ServiceCreditApplication._with_dates(rows[0]) if rows else None,  # include participation dates
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get service credit application by ID
    # --------------------------

    @staticmethod
    def get_by_id(application_id: int) -> dict:
        """
        Retrieves a single service credit application by its primary key,
        including joined employee info and participation dates.

        Parameters:
            application_id (int): The primary key of the application to fetch.

        Returns:
            dict: statusCode 200 with the application data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the application with joined SO and employee details
                """SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                          e.first_name, e.last_name, e.employee_number
                   FROM service_credit_applications sca
                   JOIN special_orders so ON so.id = sca.special_order_id
                   JOIN employees e ON e.id = sca.employee_id
                   WHERE sca.id = %s""",
                [application_id]
            )

            return {  # return found application
                "statusCode": 200,
                "data": ServiceCreditApplication._with_dates(rows[0]),  # attach participation dates
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"Service credit application {application_id} not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get service credit applications by employee
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int) -> dict:
        """
        Retrieves all service credit applications submitted by a specific employee,
        ordered by creation date descending.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with the list of applications, or 404 if none found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            rows = fetch_query(  # fetch all applications for the employee with SO details
                """SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity
                   FROM service_credit_applications sca
                   JOIN special_orders so ON so.id = sca.special_order_id
                   WHERE sca.employee_id = %s
                   ORDER BY sca.created_at DESC""",
                [employee_id]
            )

            return {  # return results
                "statusCode": 200,
                "count": len(rows),  # number of applications returned
                "data": [ServiceCreditApplication._with_dates(row) for row in rows],  # attach dates to each row
            } if rows else {  # return 404 if none found
                "statusCode": 404,
                "message": "No service credit applications found for this employee",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get service credit application by application number
    # --------------------------

    @staticmethod
    def get_by_application_number(application_number: str) -> dict:
        """
        Retrieves a single service credit application by its unique application number.
        No pagination — application numbers are unique identifiers.

        Parameters:
            application_number (str): The application number (e.g. 'SC-A1B2C3D4').

        Returns:
            dict: statusCode 200 with the application data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the application matching the application number with SO and employee info
                """SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                          e.first_name, e.last_name, e.employee_number
                   FROM service_credit_applications sca
                   JOIN special_orders so ON so.id = sca.special_order_id
                   JOIN employees e ON e.id = sca.employee_id
                   WHERE sca.application_number = %s""",
                [application_number]
            )

            return {  # return found application
                "statusCode": 200,
                "data": ServiceCreditApplication._with_dates(rows[0]),  # attach participation dates
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"Service credit application '{application_number}' not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Search service credit applications (paginated)
    # --------------------------

    @staticmethod
    def search(filters: dict, page: int = 1, limit: int = 10) -> dict:
        """
        Searches service credit applications using optional filters with pagination.
        All filters are optional and combinable. Results ordered by date_filed DESC.
        Supported filters: special_order_id, type (CTO/VSC), year, date_from, date_to.

        Parameters:
            filters (dict): Optional filter keys — special_order_id, type, year, date_from, date_to.
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated results and applied filters, or an error dict.
        """
        try:
            if filters.get("type") and filters["type"] not in ("CTO", "VSC"):  # validate type if provided
                return {"statusCode": 400, "message": "type must be CTO or VSC"}  # return 400 for invalid type

            conditions = []  # list of WHERE clause fragments built from provided filters
            params = []  # bound parameter values matching each placeholder

            if filters.get("special_order_id"):  # filter by Special Order FK
                conditions.append("sca.special_order_id = %s")  # add special_order_id condition
                params.append(filters["special_order_id"])  # bind value

            if filters.get("type"):  # filter by credit type (CTO or VSC)
                conditions.append("sca.type = %s")  # add type condition
                params.append(filters["type"].upper())  # normalise to uppercase

            if filters.get("year"):  # filter by calendar year of date_filed
                conditions.append("YEAR(sca.date_filed) = %s")  # add year condition
                params.append(filters["year"])  # bind year value

            if filters.get("date_from"):  # filter by lower bound of date_filed range
                conditions.append("sca.date_filed >= %s")  # add date_from condition
                params.append(filters["date_from"])  # bind date_from value

            if filters.get("date_to"):  # filter by upper bound of date_filed range
                conditions.append("sca.date_filed <= %s")  # add date_to condition
                params.append(filters["date_to"])  # bind date_to value

            where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""  # assemble WHERE or empty string

            count_row = fetch_query(  # get total matching records for pagination metadata
                f"""SELECT COUNT(*) AS total
                    FROM service_credit_applications sca
                    JOIN special_orders so ON so.id = sca.special_order_id
                    JOIN employees e ON e.id = sca.employee_id
                    {where_clause}""",
                params  # bind filter params only
            )

            total = count_row[0]["total"] if count_row else 0  # extract total count

            offset = (page - 1) * limit  # calculate row offset for the requested page

            rows = fetch_query(  # fetch paginated matching applications
                f"""SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                           e.first_name, e.last_name, e.employee_number
                    FROM service_credit_applications sca
                    JOIN special_orders so ON so.id = sca.special_order_id
                    JOIN employees e ON e.id = sca.employee_id
                    {where_clause}
                    ORDER BY sca.date_filed DESC, sca.id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]  # filter params followed by LIMIT and OFFSET
            )

            active_filters = {k: v for k, v in filters.items() if v is not None}  # strip None values

            return {  # return paginated search results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total matching records across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "filters": active_filters,  # echo back applied filters
                "data": [ServiceCreditApplication._with_dates(row) for row in rows] if rows else [],  # attach participation dates
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Search service credit applications within a Special Order
    # --------------------------

    @staticmethod
    def search_by_special_order(special_order_id: int, query: str, page: int = 1, limit: int = 10) -> dict:
        """
        Searches service credit applications linked to a specific Special Order by
        application number, employee number, first name, or last name using a partial match.
        Results are paginated and ordered by date_filed descending.

        Parameters:
            special_order_id (int): The Special Order's primary key to scope the search.
            query (str): The search keyword matched against application_number,
                         employee_number, first_name, and last_name.
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated matching results, or 400/404 on error.
        """
        try:
            if not query or not query.strip():  # query must not be empty
                return {"statusCode": 400, "message": "query is required"}  # return 400 if blank

            special_order = fetch_query(  # verify the Special Order exists
                "SELECT id, special_order, activity_name FROM special_orders WHERE id = %s",
                [special_order_id]
            )

            if not special_order:  # Special Order not found
                return {"statusCode": 404, "message": f"Special Order {special_order_id} not found"}  # return 404

            keyword = f"%{query.strip()}%"  # wrap keyword in wildcards for partial LIKE match

            base_where = (  # base condition scoping search to this Special Order
                "sca.special_order_id = %s AND "
                "(sca.application_number LIKE %s "
                "OR e.employee_number LIKE %s "
                "OR e.first_name LIKE %s "
                "OR e.last_name LIKE %s)"
            )

            base_params = [special_order_id, keyword, keyword, keyword, keyword]  # params for base_where

            total_row = fetch_query(  # get total matching count for pagination metadata
                f"""SELECT COUNT(*) AS total
                    FROM service_credit_applications sca
                    JOIN special_orders so ON so.id = sca.special_order_id
                    JOIN employees e ON e.id = sca.employee_id
                    WHERE {base_where}""",
                base_params
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            offset = (page - 1) * limit  # calculate row offset for the requested page

            rows = fetch_query(  # fetch paginated matching applications
                f"""SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                           e.first_name, e.last_name, e.employee_number
                    FROM service_credit_applications sca
                    JOIN special_orders so ON so.id = sca.special_order_id
                    JOIN employees e ON e.id = sca.employee_id
                    WHERE {base_where}
                    ORDER BY sca.date_filed DESC, sca.id DESC
                    LIMIT %s OFFSET %s""",
                base_params + [limit, offset]  # filter params followed by LIMIT and OFFSET
            )

            return {  # return paginated search results
                "statusCode": 200,  # success code
                "special_order": dict(special_order[0]),  # include SO context for the caller
                "query": query.strip(),  # echo back the search keyword
                "count": len(rows),  # number of records in this page
                "total": total,  # total matching records across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": [ServiceCreditApplication._with_dates(row) for row in rows] if rows else [],  # attach participation dates
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get service credit applications by Special Order (paginated)
    # --------------------------

    @staticmethod
    def get_by_special_order(special_order_id: int, page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves all service credit applications linked to a specific Special Order,
        paginated and ordered by date_filed descending.

        Parameters:
            special_order_id (int): The Special Order's primary key.
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated results, or 404 if the SO does not exist.
        """
        try:
            special_order = fetch_query(  # verify the Special Order exists
                "SELECT id, special_order, activity_name FROM special_orders WHERE id = %s",
                [special_order_id]
            )

            if not special_order:  # Special Order not found
                return {"statusCode": 404, "message": f"Special Order {special_order_id} not found"}  # return 404

            total_row = fetch_query(  # get total count for pagination metadata
                "SELECT COUNT(*) AS total FROM service_credit_applications WHERE special_order_id = %s",
                [special_order_id]
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            offset = (page - 1) * limit  # calculate row offset for the requested page

            rows = fetch_query(  # fetch paginated applications for this Special Order
                """SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                          e.first_name, e.last_name, e.employee_number
                   FROM service_credit_applications sca
                   JOIN special_orders so ON so.id = sca.special_order_id
                   JOIN employees e ON e.id = sca.employee_id
                   WHERE sca.special_order_id = %s
                   ORDER BY sca.date_filed DESC, sca.id DESC
                   LIMIT %s OFFSET %s""",
                [special_order_id, limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,  # success code
                "special_order": dict(special_order[0]),  # include SO context for the caller
                "count": len(rows),  # number of records in this page
                "total": total,  # total applications under this SO
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": [ServiceCreditApplication._with_dates(row) for row in rows] if rows else [],  # attach participation dates
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get CTO credits with their primary leave applications per employee
    # --------------------------

    @staticmethod
    def get_cto_leave_summary(employee_id: int) -> dict:
        """
        Returns all CTO service credit records for an employee, each carrying the CTO leave
        applications that were primarily charged to it. A leave application is assigned to
        the credit it deducted the most from (MAX amount_deducted in cto_deduction_log).
        Ties are broken by the lowest cto_credit_balance_id so each leave application appears
        under exactly one credit even when it spanned multiple credits.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with a list of CTO credit records each containing a
                  'leave_applications' list, or 404 if the employee is not found.
        """
        try:
            employee = fetch_query(  # verify the employee exists and get basic info for the response
                "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
                [employee_id]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            credits = fetch_query(  # fetch all CTO credit balance records for the employee with credit, SO, and uploader context
                """SELECT ccb.id AS credit_balance_id,
                          ccb.original_balance,
                          ccb.remaining_balance,
                          ccb.valid_until,
                          ccb.created_at AS credit_created_at,
                          sca.id AS service_credit_application_id,
                          sca.application_number AS credit_application_number,
                          sca.hours_rendered,
                          sca.balance_earned,
                          sca.date_filed,
                          sca.date_of_upload,
                          sca.uploaded_by,
                          sca.type,
                          CONCAT(uploader.first_name, ' ', uploader.last_name) AS uploaded_by_name,
                          so.special_order AS special_order_number,
                          so.activity_name,
                          so.date_of_activity
                   FROM cto_credit_balances ccb
                   JOIN service_credit_applications sca ON sca.id = ccb.service_credit_application_id
                   JOIN special_orders so ON so.id = sca.special_order_id
                   LEFT JOIN employees uploader ON uploader.id = sca.uploaded_by
                   WHERE ccb.employee_id = %s
                   ORDER BY (ccb.valid_until IS NULL) ASC, ccb.valid_until ASC, ccb.id ASC""",
                [employee_id]
            )

            if not credits:  # no CTO credits found for this employee
                return {  # return 200 with empty list rather than 404
                    "statusCode": 200,
                    "employee": dict(employee[0]),  # include employee context
                    "count": 0,  # no credits
                    "data": [],  # empty list
                }

            all_logs = fetch_query(  # fetch all deduction log rows for this employee's credits with balance and leave context
                """SELECT cdl.leave_application_id,
                          cdl.cto_credit_balance_id,
                          cdl.amount_deducted,
                          ccb.original_balance,
                          (SELECT COALESCE(SUM(CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END), 0.0)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS total_days
                   FROM cto_deduction_log cdl
                   JOIN cto_credit_balances ccb ON ccb.id = cdl.cto_credit_balance_id
                   JOIN leave_applications la ON la.id = cdl.leave_application_id
                   WHERE ccb.employee_id = %s""",
                [employee_id]
            )

            # group log rows by leave application to resolve the primary credit in Python
            logs_by_app = {}  # map: leave_application_id -> list of log row dicts
            for log in (all_logs or []):  # build the grouping
                lid = log["leave_application_id"]  # shorthand
                logs_by_app.setdefault(lid, []).append(log)  # append to existing list or start a new one

            app_to_credit = {}  # map: leave_application_id -> primary credit_balance_id
            for app_id, log_rows in logs_by_app.items():  # resolve primary credit for each leave application
                total_days = float(log_rows[0]["total_days"])  # total days of this leave application

                # priority: credit whose original_balance covers the full leave (deducting total days won't go negative)
                sufficient = [r for r in log_rows if float(r["original_balance"]) >= total_days]

                if sufficient:  # at least one credit could have covered the full leave on its own
                    primary = max(sufficient, key=lambda r: r["cto_credit_balance_id"])  # last (highest ID) of those
                else:  # no single credit was large enough — fall back to the credit with the largest deduction
                    max_deducted = max(float(r["amount_deducted"]) for r in log_rows)  # largest partial deduction
                    max_rows = [r for r in log_rows if float(r["amount_deducted"]) == max_deducted]  # all tied rows
                    primary = max(max_rows, key=lambda r: r["cto_credit_balance_id"])  # last record breaks the tie

                app_to_credit[app_id] = primary["cto_credit_balance_id"]  # store the resolved primary credit

            # fetch participation dates for each credit from service_credit_dates
            sca_ids = [c["service_credit_application_id"] for c in credits]  # collect all service credit app IDs
            sca_dates_map = {c["service_credit_application_id"]: [] for c in credits}  # init per-SCA dates list
            if sca_ids:  # only query if there are credits
                sca_placeholders = ", ".join(["%s"] * len(sca_ids))  # build IN clause placeholders
                date_rows = fetch_query(  # fetch all participation dates for these service credit applications
                    f"""SELECT service_credit_application_id, date
                        FROM service_credit_dates
                        WHERE service_credit_application_id IN ({sca_placeholders})
                        ORDER BY date ASC""",
                    sca_ids  # bind all SCA IDs
                )
                for dr in (date_rows or []):  # group dates under their parent SCA ID
                    sca_dates_map[dr["service_credit_application_id"]].append(str(dr["date"]))  # store as string

            credit_to_apps = {c["credit_balance_id"]: [] for c in credits}  # init per-credit leave application list
            for app_id, credit_id in app_to_credit.items():  # group leave applications under their primary credit
                if credit_id in credit_to_apps:  # guard against orphaned log entries
                    credit_to_apps[credit_id].append(app_id)  # append app id under the primary credit

            app_details = {}  # map: leave_application_id -> full application row dict
            all_app_ids = list(app_to_credit.keys())  # all leave application IDs to fetch

            if all_app_ids:  # only query if there are any assigned applications
                placeholders = ", ".join(["%s"] * len(all_app_ids))  # build IN clause placeholders
                rows = fetch_query(  # fetch full leave application details including approval info and username
                    f"""SELECT la.*,
                               lt.code AS leave_type_code,
                               lt.name AS leave_type_name,
                               u.username,
                               latest_appr.remarks,
                               latest_appr.approved_at AS date_of_action,
                               CONCAT(approver_emp.first_name, ' ', approver_emp.last_name) AS approver_name,
                               (SELECT MIN(lad.leave_date) FROM leave_application_dates lad WHERE lad.leave_application_id = la.id) AS start_date,
                               (SELECT MAX(lad.leave_date) FROM leave_application_dates lad WHERE lad.leave_application_id = la.id) AS end_date,
                               (SELECT COALESCE(SUM(CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END), 0.0) FROM leave_application_dates lad WHERE lad.leave_application_id = la.id) AS total_days
                        FROM leave_applications la
                        JOIN leave_types lt ON lt.id = la.leave_type_id
                        LEFT JOIN users u ON u.employee_id = la.employee_id
                        LEFT JOIN leave_approvals latest_appr
                            ON latest_appr.id = (
                                SELECT MAX(id) FROM leave_approvals WHERE leave_application_id = la.id
                            )
                        LEFT JOIN employees approver_emp ON approver_emp.id = latest_appr.approver_id
                        WHERE la.id IN ({placeholders})
                        ORDER BY start_date ASC""",
                    all_app_ids  # bind all application IDs
                )
                for row in (rows or []):  # index by application ID for O(1) lookup
                    app_details[row["id"]] = dict(row)  # store the full row dict

            # Build a lookup for the amount each leave application deducted from each specific credit
            deduction_lookup = {}  # key: (leave_application_id, cto_credit_balance_id) -> amount_deducted
            for log in (all_logs or []):  # iterate all deduction log rows
                key = (log["leave_application_id"], log["cto_credit_balance_id"])  # composite key
                deduction_lookup[key] = float(log["amount_deducted"])  # store the deducted amount for this pair

            REVERSED_STATUSES = {"RETURNED", "DISAPPROVED"}  # statuses where the deduction was already restored

            result = []  # list of credit records with nested leave applications
            for credit in credits:  # iterate credits in order (earliest valid_until first)
                credit_row = dict(credit)  # copy the credit row so the original is not mutated
                credit_row["participation_dates"] = sca_dates_map.get(  # attach inclusive activity dates for this credit
                    credit["service_credit_application_id"], []
                )
                assigned_ids = credit_to_apps.get(credit["credit_balance_id"], [])  # get app IDs for this credit

                # collect and sort this credit's leave applications chronologically by leave start date
                apps_for_credit = [  # build the list from the detail map
                    app_details[app_id]
                    for app_id in assigned_ids
                    if app_id in app_details  # guard against missing detail rows
                ]
                apps_for_credit.sort(key=lambda a: str(a.get("start_date") or ""))  # sort ASC so running balance flows forward

                # compute a chronological running balance starting at this credit's original amount
                running_balance = float(credit["original_balance"])  # full credit amount before any deductions
                for app in apps_for_credit:  # walk apps in date order
                    key = (app["id"], credit["credit_balance_id"])  # lookup key for this (app, credit) pair
                    amount_from_credit = deduction_lookup.get(key, 0.0)  # days deducted from THIS credit specifically
                    if app["status"] in REVERSED_STATUSES:  # reversed: balance was already restored, no net deduction
                        app["deduction"] = 0.0  # zero deduction shown on the leave card
                        app["balance_after"] = round(running_balance, 4)  # balance unchanged at this row
                    else:  # active application: apply deduction from this credit
                        running_balance -= amount_from_credit  # reduce the running balance
                        app["deduction"] = -round(amount_from_credit, 4)  # negative = days consumed from this credit
                        app["balance_after"] = round(running_balance, 4)  # snapshot after deduction

                credit_row["leave_applications"] = apps_for_credit  # attach sorted apps with running balance fields

                # detect forfeited days: difference between running balance after all apps and actual remaining_balance
                # this gap is caused by the expiry job zeroing out the credit — it is NOT accounted for by any leave app
                remaining = round(float(credit["remaining_balance"]), 4)  # actual remaining balance from DB
                forfeited = round(running_balance - remaining, 4)  # days lost to expiry (0 if nothing forfeited)
                valid_until = credit["valid_until"]  # expiry date for this credit
                is_expired = bool(valid_until and valid_until < date.today())  # true if past the expiry date

                credit_row["is_expired"] = is_expired  # flag so the frontend can visually mark expired credits
                credit_row["forfeited_days"] = -forfeited if forfeited > 0 else 0.0  # negative = days lost, 0 if none

                result.append(credit_row)  # add the enriched credit record to the output list

            return {  # return summary response
                "statusCode": 200,  # success code
                "employee": dict(employee[0]),  # basic employee info for context
                "count": len(result),  # number of CTO credit records
                "data": result,  # list of credits each with nested leave_applications
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Assign VSC leaves to credits (shared helper for both period summaries)
    # --------------------------

    @staticmethod
    def _assign_vsc_leaves(employee_id: int) -> dict:
        """
        Assigns each VSC leave application for an employee to exactly one VSC service credit
        across both period tables (old and new). Assignment rule: pick the credit whose
        original_balance >= total_days (won't go negative); ties break by highest
        service_credit_application_id (last record). Fallback when no credit is large enough:
        pick the highest service_credit_application_id overall.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: Maps leave_application_id (int) -> service_credit_application_id (int).
        """
        old_credits = fetch_query(  # fetch VSC credits from the old period table
            """SELECT vocb.service_credit_application_id, vocb.original_balance
               FROM vsc_old_credit_balances vocb
               WHERE vocb.employee_id = %s""",
            [employee_id]
        )
        new_credits = fetch_query(  # fetch VSC credits from the new period table
            """SELECT vncb.service_credit_application_id, vncb.original_balance
               FROM vsc_new_credit_balances vncb
               WHERE vncb.employee_id = %s""",
            [employee_id]
        )

        all_credits = list(old_credits or []) + list(new_credits or [])  # combine both period lists

        if not all_credits:  # no VSC credits exist for this employee
            return {}  # nothing to assign

        leaves = fetch_query(  # fetch all VSC leave applications for this employee ordered by start date
            """SELECT la.id AS leave_application_id,
                      (SELECT COALESCE(SUM(CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END), 0.0)
                       FROM leave_application_dates lad
                       WHERE lad.leave_application_id = la.id) AS total_days,
                      (SELECT MIN(lad.leave_date) FROM leave_application_dates lad
                       WHERE lad.leave_application_id = la.id) AS start_date
               FROM leave_applications la
               JOIN leave_types lt ON lt.id = la.leave_type_id
               WHERE la.employee_id = %s AND lt.code = 'VSC'
               ORDER BY start_date ASC""",
            [employee_id]
        )

        assignment = {}  # map: leave_application_id -> service_credit_application_id
        for leave in (leaves or []):  # assign each leave to the best-fit credit
            total_days = float(leave["total_days"])  # days requested in this leave

            sufficient = [  # credits whose original balance could cover the entire leave
                c for c in all_credits if float(c["original_balance"]) >= total_days
            ]

            if sufficient:  # at least one credit can cover the full leave without going negative
                primary = max(sufficient, key=lambda c: c["service_credit_application_id"])  # pick last record
            else:  # no single credit was large enough — fall back to last credit overall
                primary = max(all_credits, key=lambda c: c["service_credit_application_id"])

            assignment[leave["leave_application_id"]] = primary["service_credit_application_id"]  # store assignment

        return assignment  # return the complete leave -> credit mapping

    # --------------------------
    # Build VSC leave summary for one period table
    # --------------------------

    @staticmethod
    def _build_vsc_summary(employee_id: int, balance_table: str) -> dict:
        """
        Internal helper that builds the VSC leave summary for one period table.
        Fetches credits from the given table, resolves leave application assignments
        via _assign_vsc_leaves (which spans both tables so no leave is duplicated),
        and returns only the credits and leaves belonging to this period.

        Parameters:
            employee_id (int): The employee's primary key.
            balance_table (str): Either 'vsc_old_credit_balances' or 'vsc_new_credit_balances'.

        Returns:
            dict: statusCode 200 with credits and nested leave_applications, or error dict.
        """
        employee = fetch_query(  # verify the employee exists and get basic info
            "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
            [employee_id]
        )
        if not employee:  # employee not found
            return {"statusCode": 404, "message": "Employee not found"}  # return 404

        credits = fetch_query(  # fetch all VSC credits for this employee from the specified period table
            f"""SELECT vb.id AS credit_balance_id,
                       vb.original_balance,
                       vb.remaining_balance,
                       sca.id AS service_credit_application_id,
                       sca.application_number AS credit_application_number,
                       sca.hours_rendered,
                       sca.balance_earned,
                       sca.date_filed,
                       sca.date_of_upload,
                       sca.uploaded_by,
                       sca.type,
                       CONCAT(uploader.first_name, ' ', uploader.last_name) AS uploaded_by_name,
                       so.special_order AS special_order_number,
                       so.activity_name,
                       so.date_of_activity
                FROM {balance_table} vb
                JOIN service_credit_applications sca ON sca.id = vb.service_credit_application_id
                JOIN special_orders so ON so.id = sca.special_order_id
                LEFT JOIN employees uploader ON uploader.id = sca.uploaded_by
                WHERE vb.employee_id = %s
                ORDER BY sca.id ASC""",
            [employee_id]
        )

        if not credits:  # no credits in this period for this employee
            return {  # return 200 with empty list
                "statusCode": 200,
                "employee": dict(employee[0]),
                "count": 0,
                "data": [],
            }

        sca_ids = [c["service_credit_application_id"] for c in credits]  # collect all SCA IDs
        sca_dates_map = {sid: [] for sid in sca_ids}  # init per-SCA participation dates map
        sca_placeholders = ", ".join(["%s"] * len(sca_ids))  # build IN clause placeholders
        date_rows = fetch_query(  # fetch all participation dates for these service credit applications
            f"""SELECT service_credit_application_id, date
                FROM service_credit_dates
                WHERE service_credit_application_id IN ({sca_placeholders})
                ORDER BY date ASC""",
            sca_ids
        )
        for dr in (date_rows or []):  # group dates under their parent SCA ID
            sca_dates_map[dr["service_credit_application_id"]].append(str(dr["date"]))

        assignment = ServiceCreditApplication._assign_vsc_leaves(employee_id)  # get combined period assignment

        this_period_sca_ids = set(sca_ids)  # IDs belonging to this period
        period_app_ids = [  # leave application IDs whose primary credit is in this period
            app_id for app_id, sca_id in assignment.items()
            if sca_id in this_period_sca_ids
        ]

        app_details = {}  # map: leave_application_id -> full leave application dict
        if period_app_ids:  # only query if there are assigned applications
            app_placeholders = ", ".join(["%s"] * len(period_app_ids))  # build IN clause
            rows = fetch_query(  # fetch full leave application data with approval info and username
                f"""SELECT la.*,
                           lt.code AS leave_type_code,
                           lt.name AS leave_type_name,
                           u.username,
                           latest_appr.remarks,
                           latest_appr.approved_at AS date_of_action,
                           CONCAT(approver_emp.first_name, ' ', approver_emp.last_name) AS approver_name,
                           (SELECT MIN(lad.leave_date) FROM leave_application_dates lad WHERE lad.leave_application_id = la.id) AS start_date,
                           (SELECT MAX(lad.leave_date) FROM leave_application_dates lad WHERE lad.leave_application_id = la.id) AS end_date,
                           (SELECT COALESCE(SUM(CASE WHEN lad.duration_type = 'HALF_DAY' THEN 0.5 ELSE 1.0 END), 0.0) FROM leave_application_dates lad WHERE lad.leave_application_id = la.id) AS total_days
                    FROM leave_applications la
                    JOIN leave_types lt ON lt.id = la.leave_type_id
                    LEFT JOIN users u ON u.employee_id = la.employee_id
                    LEFT JOIN leave_approvals latest_appr
                        ON latest_appr.id = (
                            SELECT MAX(id) FROM leave_approvals WHERE leave_application_id = la.id
                        )
                    LEFT JOIN employees approver_emp ON approver_emp.id = latest_appr.approver_id
                    WHERE la.id IN ({app_placeholders})
                    ORDER BY start_date ASC""",
                period_app_ids
            )
            for row in (rows or []):  # index by application ID for O(1) lookup
                app_details[row["id"]] = dict(row)

        credit_to_apps = {c["service_credit_application_id"]: [] for c in credits}  # init per-credit app list
        for app_id, sca_id in assignment.items():  # group leave apps under their assigned credit
            if sca_id in credit_to_apps and app_id in app_details:  # only include this period's credits
                credit_to_apps[sca_id].append(app_details[app_id])

        result = []  # list of credit records with nested leave applications
        for credit in credits:  # iterate credits
            credit_row = dict(credit)  # copy the credit row
            credit_row["participation_dates"] = sca_dates_map.get(  # attach participation dates
                credit["service_credit_application_id"], []
            )
            credit_row["leave_applications"] = credit_to_apps.get(  # attach assigned leave applications
                credit["service_credit_application_id"], []
            )
            result.append(credit_row)  # add to output list

        return {  # return summary response
            "statusCode": 200,
            "employee": dict(employee[0]),  # basic employee info for context
            "count": len(result),  # number of VSC credit records in this period
            "data": result,  # credits with nested leave_applications
        }

    # --------------------------
    # Get VSC old period leave summary (activity < 2024-10-01) per employee
    # --------------------------

    @staticmethod
    def get_vsc_old_leave_summary(employee_id: int) -> dict:
        """
        Returns VSC service credit records for activities with date_of_activity < 2024-10-01,
        each with the VSC leave applications primarily charged to it. No valid_until field
        (VSC credits do not expire). Uses _build_vsc_summary with vsc_old_credit_balances.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with old-period VSC credits and nested leave_applications.
        """
        try:
            return ServiceCreditApplication._build_vsc_summary(employee_id, "vsc_old_credit_balances")  # delegate to shared builder
        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get VSC new period leave summary (activity >= 2024-10-01) per employee
    # --------------------------

    @staticmethod
    def get_vsc_new_leave_summary(employee_id: int) -> dict:
        """
        Returns VSC service credit records for activities with date_of_activity >= 2024-10-01,
        each with the VSC leave applications primarily charged to it. No valid_until field
        (VSC credits do not expire). Uses _build_vsc_summary with vsc_new_credit_balances.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with new-period VSC credits and nested leave_applications.
        """
        try:
            return ServiceCreditApplication._build_vsc_summary(employee_id, "vsc_new_credit_balances")  # delegate to shared builder
        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all service credit applications (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all service credit applications across all employees,
        ordered by date filed descending. Joins with employees for context.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated service credit application data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get total count for pagination metadata
                "SELECT COUNT(*) AS total FROM service_credit_applications", []
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated applications with SO and employee info
                """SELECT sca.*, so.special_order, so.activity_name, so.reference, so.date_of_activity,
                          e.first_name, e.last_name, e.employee_number
                   FROM service_credit_applications sca
                   JOIN special_orders so ON so.id = sca.special_order_id
                   JOIN employees e ON e.id = sca.employee_id
                   ORDER BY sca.date_filed DESC, sca.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total number of applications across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": [ServiceCreditApplication._with_dates(row) for row in rows] if rows else [],  # attach dates to each row
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Daily CTO credit expiry job
    # --------------------------

    @staticmethod
    def expire_cto_credits() -> dict:
        """
        Checks for CTO credits whose valid_until date has passed and still carry a
        remaining_balance > 0. For each expired credit, zeroes out remaining_balance,
        posts a DEBIT ledger entry for the forfeited days, and recalculates the
        employee's CTO ledger snapshots. Intended to be called once per day by the
        background scheduler at midnight.

        Parameters:
            None

        Returns:
            dict: statusCode 200 with expired_count and total_days_forfeited,
                  or statusCode 500 on unexpected error.
        """
        try:
            cto_type = fetch_query(  # resolve the CTO leave type ID once for all ledger entries
                "SELECT id FROM leave_types WHERE code = 'CTO' LIMIT 1", []
            )
            if not cto_type:  # CTO leave type not configured in this system
                return {"statusCode": 200, "message": "CTO leave type not found — skipping expiry check", "expired_count": 0}

            cto_leave_type_id = cto_type[0]["id"]  # CTO leave type primary key

            expired_credits = fetch_query(  # find all credits past their expiry date with remaining balance
                """SELECT id, employee_id, remaining_balance, valid_until
                   FROM cto_credit_balances
                   WHERE valid_until < CURDATE()
                     AND remaining_balance > 0
                   ORDER BY employee_id ASC, valid_until ASC""",
                []
            )

            if not expired_credits:  # nothing to expire today
                return {"statusCode": 200, "message": "No expired CTO credits found", "expired_count": 0}

            expired_count = 0  # track how many credits were processed
            total_forfeited = 0.0  # track total days forfeited across all credits

            for credit in expired_credits:  # process each expired credit one by one
                credit_id = credit["id"]  # primary key of this credit record
                employee_id = credit["employee_id"]  # employee who owned this credit
                amount = round(float(credit["remaining_balance"]), 2)  # days being forfeited
                expiry_date = str(credit["valid_until"])  # the date this credit expired

                zero_result = query(  # zero out the remaining balance on the expired credit
                    "UPDATE cto_credit_balances SET remaining_balance = 0 WHERE id = %s",
                    [credit_id]
                )
                if zero_result["statusCode"] != 200:  # skip this credit if the update failed
                    continue

                txn_number = uuid.uuid4().hex[:8].upper()  # generate a unique transaction number
                txn_result = query_insert(  # post a DEBIT ledger entry for the forfeited days
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'DEBIT', %s, 'SYSTEM_ADJUSTMENT', %s, CURDATE(), 0, %s)""",
                    [
                        txn_number,              # unique identifier for this ledger row
                        employee_id,             # employee losing the balance
                        cto_leave_type_id,       # CTO leave type
                        amount,                  # days forfeited
                        credit_id,               # source: the expired cto_credit_balances row
                        f"CTO credit expired on {expiry_date} — {amount} day(s) forfeited",  # audit trail
                    ]
                )
                if txn_result["statusCode"] != 200:  # skip ledger update if insert failed
                    continue

                recalculate_ledger_snapshots(employee_id, cto_leave_type_id)  # update snapshots and cached balance

                expired_count += 1  # increment processed count
                total_forfeited = round(total_forfeited + amount, 2)  # accumulate forfeited days

            return {
                "statusCode": 200,
                "message": f"CTO expiry check complete — {expired_count} credit(s) expired",
                "expired_count": expired_count,
                "total_days_forfeited": total_forfeited,
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
