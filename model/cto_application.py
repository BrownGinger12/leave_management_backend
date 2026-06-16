from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert  # import gateway functions
from datetime import date  # import date for date parsing and today's date
import uuid  # import uuid to generate unique numbers


class CtoApplication(BaseModel):
    """
    Pydantic model representing a CTO (Compensatory Time Off) application.
    Documents an activity/event rendered by an employee as basis for CTO credits.

    Attributes:
        employee_id: FK to the employee submitting the application.
        activity_name: Name of the activity or event participated in.
        activity_start_date: Date the activity started (YYYY-MM-DD).
        activity_end_date: Date the activity ended (YYYY-MM-DD).
        participation_start_date: First day the employee participated (YYYY-MM-DD).
        participation_end_date: Last day the employee participated (YYYY-MM-DD).
        days_rendered: Number of CTO days earned from participation.
        special_order_number: Special order reference number (optional).
    """
    employee_id: int  # FK to employees table
    activity_name: str  # name of the activity or event
    activity_start_date: str  # start date of the activity
    activity_end_date: str  # end date of the activity
    participation_start_date: str  # first day employee participated
    participation_end_date: str  # last day employee participated
    days_rendered: float  # CTO days earned from participation
    special_order_number: Optional[str] = None  # special order reference, optional
    date_filed: str  # date the application was submitted (YYYY-MM-DD)

    # --------------------------
    # Generate application number
    # --------------------------

    @staticmethod
    def _generate_application_number() -> str:
        """
        Generates a unique CTO application number using a UUID-based suffix.

        Returns:
            str: An application number in the format 'CTO-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"CTO-{suffix}"  # format as CTO-XXXXXXXX

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
    # Submit CTO application
    # --------------------------

    @staticmethod
    def submit(data: dict) -> dict:
        """
        Submits a new CTO application after validating employee, dates, and days rendered.
        Application is created with PENDING status — CTO credit is NOT posted at this stage.

        Parameters:
            data (dict): Application fields — employee_id, activity_name,
                         activity_start_date, activity_end_date,
                         participation_start_date, participation_end_date,
                         days_rendered, special_order_number (optional).

        Returns:
            dict: statusCode 201 with the created application data, or an error dict.
        """
        try:
            required_fields = [  # fields that must be present
                "employee_id", "activity_name",
                "activity_start_date", "activity_end_date",
                "participation_start_date", "participation_end_date",
                "days_rendered", "date_filed"
            ]

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            if data["days_rendered"] <= 0:  # validate days rendered is a positive number
                return {"statusCode": 400, "message": "days_rendered must be greater than 0"}  # return 400 if invalid

            activity_start = date.fromisoformat(data["activity_start_date"])  # parse activity start date
            activity_end = date.fromisoformat(data["activity_end_date"])  # parse activity end date
            participation_start = date.fromisoformat(data["participation_start_date"])  # parse participation start date
            participation_end = date.fromisoformat(data["participation_end_date"])  # parse participation end date

            if activity_end < activity_start:  # validate activity date range
                return {"statusCode": 400, "message": "activity_end_date cannot be before activity_start_date"}  # return 400

            if participation_end < participation_start:  # validate participation date range
                return {"statusCode": 400, "message": "participation_end_date cannot be before participation_start_date"}  # return 400

            if participation_start < activity_start or participation_end > activity_end:  # participation must fall within activity dates
                return {"statusCode": 400, "message": "Participation dates must be within the activity date range"}  # return 400

            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            application_number = CtoApplication._generate_application_number()  # generate unique application number

            result = query_insert(  # insert the CTO application as PENDING
                """INSERT INTO cto_applications
                       (application_number, employee_id, activity_name,
                        activity_start_date, activity_end_date,
                        participation_start_date, participation_end_date,
                        days_rendered, special_order_number, date_filed, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')""",
                [
                    application_number,                          # generated application number
                    data["employee_id"],                         # employee submitting the application
                    data["activity_name"],                       # name of the activity
                    data["activity_start_date"],                 # activity start date
                    data["activity_end_date"],                   # activity end date
                    data["participation_start_date"],            # participation start date
                    data["participation_end_date"],              # participation end date
                    data["days_rendered"],                       # CTO days earned
                    data.get("special_order_number"),            # special order number, may be None
                    data["date_filed"],                          # date the application was filed
                ]
            )

            if result["statusCode"] != 200:  # check if insert failed
                return result  # return the error from the gateway

            application = fetch_query(  # fetch the full created application record
                """SELECT ca.*, e.first_name, e.last_name, e.employee_number
                   FROM cto_applications ca
                   JOIN employees e ON e.id = ca.employee_id
                   WHERE ca.id = %s""",
                [result["insertId"]]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": "CTO application submitted successfully",  # confirmation message
                "data": application[0] if application else None,  # the created application record
            }

        except ValueError as e:  # catch invalid date format errors
            return {"statusCode": 400, "message": f"Invalid date format: {str(e)}"}  # return 400 with detail
        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Decide on CTO application
    # --------------------------

    @staticmethod
    def decide(data: dict) -> dict:
        """
        Processes an approver's APPROVED or REJECTED decision on a CTO application.
        - APPROVED: credits the employee's CTO balance via the ledger and updates the balance cache.
        - REJECTED: records the rejection on the application.

        Parameters:
            data (dict): Decision fields — cto_application_id, approver_id,
                         status (APPROVED or REJECTED), remarks (optional).

        Returns:
            dict: statusCode 200 with the updated application data, or an error dict.
        """
        try:
            required_fields = ["cto_application_id", "approver_id", "status"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if data.get(field) is None:  # check if field is missing
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            if data["status"] not in ("APPROVED", "REJECTED"):  # validate status value
                return {"statusCode": 400, "message": "status must be APPROVED or REJECTED"}  # return 400 if invalid

            application = fetch_query(  # fetch the CTO application
                "SELECT * FROM cto_applications WHERE id = %s", [data["cto_application_id"]]
            )

            if not application:  # application not found
                return {"statusCode": 404, "message": "CTO application not found"}  # return 404

            if application[0]["status"] != "PENDING":  # application must be pending to be acted on
                return {  # return 400 if already processed
                    "statusCode": 400,
                    "message": f"CTO application is already {application[0]['status']} and cannot be acted on",
                }

            approver = fetch_query(  # verify the approver employee exists
                "SELECT id FROM employees WHERE id = %s", [data["approver_id"]]
            )

            if not approver:  # approver not found
                return {"statusCode": 404, "message": "Approver not found"}  # return 404

            if data["status"] == "APPROVED":  # handle the approval path
                app = application[0]  # shorthand for the application row

                cto_type = fetch_query(  # get the CTO leave type ID from leave_types
                    "SELECT id FROM leave_types WHERE code = 'CTO' AND is_active = 1", []
                )

                if not cto_type:  # CTO leave type not found or inactive
                    return {"statusCode": 500, "message": "CTO leave type not found or is inactive"}  # return error

                cto_leave_type_id = cto_type[0]["id"]  # the leave_type_id for CTO
                days_rendered = float(app["days_rendered"])  # cast Decimal to float

                balance_row = fetch_query(  # get the employee's current CTO balance
                    "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                    [app["employee_id"], cto_leave_type_id]
                )

                current_balance = float(balance_row[0]["balance"]) if balance_row else 0.0  # cast Decimal to float, default 0
                new_balance = round(current_balance + days_rendered, 2)  # compute balance after credit
                transaction_number = CtoApplication._generate_transaction_number()  # generate unique transaction number

                ledger_result = query_insert(  # insert the CREDIT record into the ledger
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'CREDIT', %s, 'SPECIAL_ORDER', %s, %s, %s, %s)""",
                    [
                        transaction_number,              # generated transaction number
                        app["employee_id"],              # employee being credited
                        cto_leave_type_id,              # CTO leave type
                        days_rendered,                  # days credited
                        app["id"],                      # source_id: this CTO application
                        date.today().isoformat(),        # transaction date is today (approval date)
                        new_balance,                    # balance after this credit
                        f"CTO credit from approved application {app['application_number']}",  # auto remarks
                    ]
                )

                if ledger_result["statusCode"] != 200:  # check if ledger insert failed
                    return ledger_result  # return the error

                query(  # upsert the employee_leave_balances cache with the new CTO balance
                    """INSERT INTO employee_leave_balances (employee_id, leave_type_id, balance)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE balance = %s""",
                    [app["employee_id"], cto_leave_type_id, new_balance, new_balance]
                )

            query(  # update the CTO application with the decision
                """UPDATE cto_applications
                   SET status = %s, approved_by = %s, approved_at = NOW(), remarks = %s
                   WHERE id = %s""",
                [
                    data["status"],              # APPROVED or REJECTED
                    data["approver_id"],         # the approver
                    data.get("remarks"),         # optional remarks
                    data["cto_application_id"],  # the application being updated
                ]
            )

            updated = fetch_query(  # fetch the updated CTO application record
                """SELECT ca.*, e.first_name, e.last_name, e.employee_number
                   FROM cto_applications ca
                   JOIN employees e ON e.id = ca.employee_id
                   WHERE ca.id = %s""",
                [data["cto_application_id"]]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "message": f"CTO application {data['status'].lower()} successfully",  # confirmation message
                "data": updated[0] if updated else None,  # the updated application record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get CTO application by ID
    # --------------------------

    @staticmethod
    def get_by_id(application_id: int) -> dict:
        """
        Retrieves a single CTO application by its primary key with joined employee info.

        Parameters:
            application_id (int): The primary key of the CTO application to fetch.

        Returns:
            dict: statusCode 200 with the application data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the application with joined employee details
                """SELECT ca.*, e.first_name, e.last_name, e.employee_number
                   FROM cto_applications ca
                   JOIN employees e ON e.id = ca.employee_id
                   WHERE ca.id = %s""",
                [application_id]
            )

            return {  # return found application
                "statusCode": 200,
                "data": rows[0],
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"CTO application {application_id} not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get CTO applications by employee
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int) -> dict:
        """
        Retrieves all CTO applications submitted by a specific employee.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with a list of applications, or 404 if none found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            rows = fetch_query(  # fetch all CTO applications for the employee
                """SELECT * FROM cto_applications
                   WHERE employee_id = %s
                   ORDER BY created_at DESC""",
                [employee_id]
            )

            return {  # return results
                "statusCode": 200,
                "count": len(rows),  # number of applications returned
                "data": rows,
            } if rows else {  # return 404 if none found
                "statusCode": 404,
                "message": "No CTO applications found for this employee",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all CTO applications (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all CTO applications across all employees,
        ordered by date filed descending. Joins with employees for context.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated CTO application data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get total count for pagination metadata
                "SELECT COUNT(*) AS total FROM cto_applications", []
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated CTO applications with employee info
                """SELECT ca.*,
                          e.first_name,
                          e.last_name,
                          e.employee_number
                   FROM cto_applications ca
                   JOIN employees e ON e.id = ca.employee_id
                   ORDER BY ca.date_filed DESC, ca.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total number of applications across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": rows if rows else [],  # list of CTO applications, empty if none
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
