from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query_insert  # import gateway functions
from datetime import date  # import date to compute total leave days
import uuid  # import uuid to generate unique application numbers


class LeaveApplication(BaseModel):
    """
    Pydantic model representing a leave application record.

    Attributes:
        employee_id: FK to the employee submitting the application.
        leave_type_id: FK to the requested leave type.
        date_filed: Date the application was submitted (YYYY-MM-DD).
        start_date: First day of the leave period (YYYY-MM-DD).
        end_date: Last day of the leave period (YYYY-MM-DD).
        reason: Employee's stated reason for the leave.
        other_leave_description: Extra description when leave type is Others (optional).
        with_pay: Whether the leave is with pay (True) or without pay (False). Defaults to True.
    """
    employee_id: int  # FK to employees table
    leave_type_id: int  # FK to leave_types table
    date_filed: str  # date the application was filed
    start_date: str  # first day of the leave
    end_date: str  # last day of the leave
    reason: str  # reason for the leave
    other_leave_description: Optional[str] = None  # extra description for Others leave type
    with_pay: bool = True  # True = leave with pay, False = leave without pay (defaults to with pay)

    # --------------------------
    # Generate application number
    # --------------------------

    @staticmethod
    def _generate_application_number() -> str:
        """
        Generates a unique leave application number using a UUID-based suffix.

        Returns:
            str: An application number in the format 'LA-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"LA-{suffix}"  # format as LA-XXXXXXXX

    # --------------------------
    # Calculate total leave days
    # --------------------------

    @staticmethod
    def _calculate_total_days(start_date: str, end_date: str) -> float:
        """
        Calculates the total number of calendar days between start and end dates inclusive.

        Parameters:
            start_date (str): Start date in YYYY-MM-DD format.
            end_date (str): End date in YYYY-MM-DD format.

        Returns:
            float: Total number of leave days.
        """
        start = date.fromisoformat(start_date)  # parse start date string to date object
        end = date.fromisoformat(end_date)  # parse end date string to date object
        return float((end - start).days + 1)  # inclusive day count

    # --------------------------
    # Fetch a single balance
    # --------------------------

    @staticmethod
    def _get_balance(employee_id: int, leave_code: str) -> float:
        """
        Returns the employee's current cached balance for a leave type by its code.

        Parameters:
            employee_id (int): The employee's primary key.
            leave_code (str): The leave type code to look up (e.g. 'VL', 'SL', 'FL').

        Returns:
            float: Current balance in days, or 0.0 if no record exists.
        """
        row = fetch_query(  # query balance joined with leave_types for code lookup
            """SELECT elb.balance
               FROM employee_leave_balances elb
               JOIN leave_types lt ON lt.id = elb.leave_type_id
               WHERE elb.employee_id = %s AND lt.code = %s""",
            [employee_id, leave_code]
        )
        return float(row[0]["balance"]) if row else 0.0  # cast Decimal to float (MySQL DECIMAL returns decimal.Decimal)

    # --------------------------
    # Check employee balance
    # --------------------------

    @staticmethod
    def _check_balance(employee_id: int, leave_type: dict, total_days: float) -> dict | None:
        """
        Validates the employee has sufficient balance for the requested leave.
        Rules by balance_type:
          - SELF         : employee must have enough of their own leave type balance
          - CHARGED_TO_VL: employee must have enough FL entitlement AND enough VL balance
          - NONE         : no balance check required

        Parameters:
            employee_id (int): The employee's primary key.
            leave_type (dict): The leave_type row — id, code, name, balance_type.
            total_days (float): Number of leave days being requested.

        Returns:
            dict | None: An error dict with balance details if insufficient, None if sufficient.
        """
        balance_type = leave_type["balance_type"]  # determine which check rule applies
        code = leave_type["code"]  # leave type code (VL, SL, FL, etc.)

        if balance_type == "NONE":  # no balance required for this leave type
            return None  # pass without checking

        if balance_type == "SELF":  # check the employee's own balance for this leave type
            available = LeaveApplication._get_balance(employee_id, code)  # fetch own balance

            if available < total_days:  # employee does not have enough
                return {  # return structured insufficiency error
                    "statusCode": 400,
                    "message": f"Insufficient {code} balance",
                    "leave_type_checked": code,  # which balance was evaluated
                    "required_days": total_days,  # days requested
                    "available_days": available,  # days currently available
                    "shortfall_days": round(total_days - available, 2),  # gap to cover
                }

        elif balance_type == "CHARGED_TO_VL":  # FL case: check both FL entitlement and VL balance
            fl_available = LeaveApplication._get_balance(employee_id, code)  # employee's FL entitlement
            vl_available = LeaveApplication._get_balance(employee_id, "VL")  # employee's VL balance

            errors = []  # collect all insufficiency details

            if fl_available < total_days:  # FL entitlement is not enough
                errors.append({  # add FL insufficiency detail
                    "leave_type_checked": code,
                    "required_days": total_days,
                    "available_days": fl_available,
                    "shortfall_days": round(total_days - fl_available, 2),
                })

            if vl_available < total_days:  # VL balance is not enough to cover FL charge
                errors.append({  # add VL insufficiency detail
                    "leave_type_checked": "VL",
                    "required_days": total_days,
                    "available_days": vl_available,
                    "shortfall_days": round(total_days - vl_available, 2),
                })

            if errors:  # at least one check failed
                return {  # return combined insufficiency error
                    "statusCode": 400,
                    "message": f"Insufficient balance for {code} application. {code} is charged against VL — both {code} entitlement and VL balance must be sufficient.",
                    "insufficient_balances": errors,  # list of which balances failed
                }

        return None  # all checks passed

    # --------------------------
    # Submit leave application
    # --------------------------

    @staticmethod
    def submit(data: dict) -> dict:
        """
        Submits a new leave application after validating dates, leave type rules, and balance.
        Application is created with PENDING status — balance is NOT deducted at this stage.

        Parameters:
            data (dict): Application fields — employee_id, leave_type_id, date_filed,
                         start_date, end_date, reason, other_leave_description (optional).

        Returns:
            dict: statusCode 201 with the created application data, or an error dict.
        """
        try:
            required_fields = ["employee_id", "leave_type_id", "date_filed",
                                "start_date", "end_date", "reason"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if not data.get(field):  # check if field is missing or empty
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            start = date.fromisoformat(data["start_date"])  # parse start date
            end = date.fromisoformat(data["end_date"])  # parse end date

            if end < start:  # validate that end is not before start
                return {"statusCode": 400, "message": "end_date cannot be before start_date"}  # return 400 if invalid

            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            leave_type = fetch_query(  # fetch the leave type to read its rules
                "SELECT id, code, name, balance_type, is_active FROM leave_types WHERE id = %s",
                [data["leave_type_id"]]
            )

            if not leave_type:  # leave type not found
                return {"statusCode": 404, "message": "Leave type not found"}  # return 404

            if not leave_type[0]["is_active"]:  # check if leave type is still active
                return {"statusCode": 400, "message": f"{leave_type[0]['name']} is no longer active"}  # return 400 if disabled

            total_days = LeaveApplication._calculate_total_days(  # compute leave day count
                data["start_date"], data["end_date"]
            )

            balance_error = LeaveApplication._check_balance(  # check if employee has enough balance
                data["employee_id"], leave_type[0], total_days
            )

            if balance_error:  # balance check failed — return the error with balance details
                return balance_error

            application_number = LeaveApplication._generate_application_number()  # generate unique application number

            result = query_insert(  # insert the leave application as PENDING
                """INSERT INTO leave_applications
                       (application_number, employee_id, leave_type_id, date_filed,
                        start_date, end_date, total_days, reason, other_leave_description, status, with_pay)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', %s)""",
                [
                    application_number,                   # generated application number
                    data["employee_id"],                  # employee submitting the application
                    data["leave_type_id"],                # leave type requested
                    data["date_filed"],                   # date filed
                    data["start_date"],                   # leave start date
                    data["end_date"],                     # leave end date
                    total_days,                           # computed number of days
                    data["reason"],                       # reason for leave
                    data.get("other_leave_description"),  # extra description for Others type
                    1 if data.get("with_pay", True) else 0,  # convert bool to tinyint (1=with pay, 0=without pay)
                ]
            )

            if result["statusCode"] != 200:  # check if insert failed
                return result  # return the error from the gateway

            application = fetch_query(  # fetch the full created application record
                """SELECT la.*, lt.code as leave_type_code, lt.name as leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s""",
                [result["insertId"]]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": "Leave application submitted successfully",  # confirmation message
                "data": application[0] if application else None,  # the created application with joined details
            }

        except ValueError as e:  # catch invalid date format errors
            return {"statusCode": 400, "message": f"Invalid date format: {str(e)}"}  # return 400 with detail
        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get leave application by ID
    # --------------------------

    @staticmethod
    def get_by_id(application_id: int) -> dict:
        """
        Retrieves a single leave application by its primary key with joined employee and leave type info.

        Parameters:
            application_id (int): The primary key of the application to fetch.

        Returns:
            dict: statusCode 200 with the application data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the application with joined details
                """SELECT la.*, lt.code as leave_type_code, lt.name as leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s""",
                [application_id]
            )

            return {  # return found application
                "statusCode": 200,
                "data": rows[0],
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"Leave application {application_id} not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all leave applications by employee
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int) -> dict:
        """
        Retrieves all leave applications submitted by a specific employee ordered by date filed.

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

            rows = fetch_query(  # fetch all applications for the employee
                """SELECT la.*, lt.code as leave_type_code, lt.name as leave_type_name
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.employee_id = %s
                   ORDER BY la.date_filed DESC""",
                [employee_id]
            )

            return {  # return results
                "statusCode": 200,
                "count": len(rows),  # number of applications returned
                "data": rows,
            } if rows else {  # return 404 if no applications found
                "statusCode": 404,
                "message": "No leave applications found for this employee",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all leave applications (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all leave applications across all employees,
        ordered by date filed descending. Joins with employees and leave_types for context.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated leave application data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get total count for pagination metadata
                "SELECT COUNT(*) AS total FROM leave_applications", []
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated applications with employee and leave type info
                """SELECT la.*,
                          lt.code AS leave_type_code,
                          lt.name AS leave_type_name,
                          e.first_name,
                          e.last_name,
                          e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   ORDER BY la.date_filed DESC, la.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total number of applications across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": rows if rows else [],  # list of applications, empty if none
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
