from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from enum import Enum  # import Enum for fixed-value fields
from gateway.mysql_gateway import fetch_query, query, query_insert  # import gateway functions
from gateway.file_storage_gateway import is_allowed_file, save_file, delete_file, generate_signed_url  # import file storage gateway functions
import uuid  # import uuid to generate unique leave card numbers


class EmployeeType(str, Enum):
    """Enum representing the classification of a DepEd employee."""
    TEACHING = "TEACHING"  # teaching staff (e.g. classroom teachers)
    NON_TEACHING = "NON_TEACHING"  # non-teaching staff (e.g. administrative)


class Employee(BaseModel):
    """
    Pydantic model representing an employee record in the leave management system.

    Attributes:
        id: Auto-incremented primary key.
        leave_card_number: System-generated unique leave card number.
        employee_number: DepEd-assigned employee number.
        first_name: Employee's first name.
        last_name: Employee's last name.
        middle_name: Employee's middle name (optional).
        email: Employee's email address.
        employee_type: TEACHING or NON_TEACHING.
        employment_status: Employment status (e.g. PERMANENT, TEMPORARY).
        school_id: Foreign key reference to the school/office.
        division: Division name (optional).
        original_appointment: Date of original appointment (optional).
        latest_appointment: Date of latest appointment (optional).
        position: Job position/title (optional).
        salary: Monthly salary (optional).
        contact_number: Employee's contact number (optional).
        is_active: Whether the employee is active (False = soft-deleted).
        photo: Path/URL to the employee's photo (optional).
    """
    id: Optional[int] = None  # primary key, set by the database
    leave_card_number: Optional[str] = None  # system-generated, set on create
    employee_number: str  # DepEd-assigned employee number
    first_name: str  # employee's first name
    last_name: str  # employee's last name
    middle_name: Optional[str] = None  # middle name, optional
    email: str  # employee's email address
    employee_type: str  # TEACHING or NON_TEACHING
    employment_status: str  # e.g. PERMANENT, TEMPORARY, CASUAL
    school_id: int  # foreign key to the school/office
    division: Optional[str] = None  # division name, optional
    original_appointment: Optional[str] = None  # date of original appointment (YYYY-MM-DD), optional
    latest_appointment: Optional[str] = None  # date of latest appointment (YYYY-MM-DD), optional
    position: Optional[str] = None  # job position or title, optional
    salary: Optional[float] = None  # monthly salary, optional
    contact_number: Optional[str] = None  # employee contact number, optional
    is_active: Optional[bool] = True  # True = active, False = soft-deleted
    photo: Optional[str] = None  # path/URL to the employee's photo, optional

    # --------------------------
    # Sign employee photo path
    # --------------------------

    @staticmethod
    def _with_signed_photo(row: dict) -> dict:
        """
        Returns a copy of an employee row with its 'photo' field replaced by a
        signed, expiring URL so the raw filesystem path is never exposed.

        Parameters:
            row (dict): An employee record as returned from the database.

        Returns:
            dict: The employee record with 'photo' replaced by a signed URL (if set).
        """
        if not row:  # nothing to do if row is empty/None
            return row  # return as-is
        result = dict(row)  # copy the row so the original is not mutated
        if result.get("photo"):  # only sign if a photo path is actually set
            result["photo"] = generate_signed_url(result["photo"])  # replace raw path with signed URL
        return result  # return the (possibly modified) copy

    # --------------------------
    # Generate leave card number
    # --------------------------

    @staticmethod
    def _generate_leave_card_number() -> str:
        """
        Generates a unique leave card number using a UUID-based suffix.

        Returns:
            str: A leave card number in the format 'LC-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take the first 8 chars of a UUID hex string
        return f"LC-{suffix}"  # format as LC-XXXXXXXX

    # --------------------------
    # Create employee
    # --------------------------

    @staticmethod
    def create(data: dict) -> dict:
        """
        Inserts a new employee record into the database.
        Leave card number is used from the request if provided, otherwise auto-generated.

        Parameters:
            data (dict): Employee fields — employee_number, first_name, last_name,
                         middle_name, email, employee_type, employment_status, school_id,
                         leave_card_number (optional).

        Returns:
            dict: statusCode 201 with the created employee data, or an error dict.
        """
        try:
            required_fields = ["employee_number", "first_name", "last_name", "email",
                                "employee_type", "employment_status", "school_id"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if not data.get(field):  # check if field is missing or empty
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            existing = fetch_query(  # check if an employee with the same employee_number already exists
                "SELECT id FROM employees WHERE employee_number = %s", [data["employee_number"]]
            )

            if existing:  # if a match is found, reject the request
                return {"statusCode": 409, "message": f"Employee with employee number '{data['employee_number']}' already exists"}  # return 409 Conflict

            leave_card_number = data.get("leave_card_number") or Employee._generate_leave_card_number()  # use provided leave card number or auto-generate one

            result = query_insert(  # execute INSERT and return the new row ID
                """INSERT INTO employees
                       (leave_card_number, employee_number, first_name, last_name,
                        middle_name, email, employee_type, employment_status, school_id,
                        division, original_appointment, latest_appointment,
                        position, salary, contact_number, is_active, photo)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    leave_card_number,                   # generated leave card number
                    data["employee_number"],             # DepEd employee number
                    data["first_name"],                  # first name
                    data["last_name"],                   # last name
                    data.get("middle_name"),             # middle name, may be None
                    data["email"],                       # email address
                    data["employee_type"],               # TEACHING or NON_TEACHING
                    data["employment_status"],           # employment status
                    data["school_id"],                   # school/office ID
                    data.get("division"),                # division name, may be None
                    data.get("original_appointment"),    # date of original appointment, may be None
                    data.get("latest_appointment"),      # date of latest appointment, may be None
                    data.get("position"),                # job position or title, may be None
                    data.get("salary"),                  # monthly salary, may be None
                    data.get("contact_number"),          # contact number, may be None
                    data.get("is_active", True),         # active status, defaults to True
                    data.get("photo"),                   # photo path/URL, may be None
                ]
            )

            if result["statusCode"] != 200:  # check if insert failed
                return result  # return the error response from the gateway

            rows = fetch_query(  # fetch the newly created employee by its insert ID
                "SELECT * FROM employees WHERE id = %s", [result["insertId"]]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": "Employee created",  # confirmation message
                "data": Employee._with_signed_photo(rows[0]) if rows else None,  # the created employee record, with signed photo URL
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all employees (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of employees ordered by ID.

        Parameters:
            page (int): The page number to retrieve (default 1).
            limit (int): The number of records per page (default 10).

        Returns:
            dict: statusCode 200 with data list and pagination info, or 404 if no records found.
        """
        try:
            offset = (page - 1) * limit  # calculate the row offset for the current page

            rows = fetch_query(  # fetch employees for the requested page
                "SELECT * FROM employees ORDER BY id LIMIT %s OFFSET %s",
                [limit, offset]
            )

            if not rows:  # check if any employees were returned
                return {"statusCode": 404, "message": "No employees found"}  # return 404 if empty

            total = Employee.get_total()  # get total employee count for pagination metadata

            return {  # return paginated response
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total number of employees in the database
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": [Employee._with_signed_photo(row) for row in rows],  # the employee records, with signed photo URLs
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get employee by ID
    # --------------------------

    @staticmethod
    def get_by_id(employee_id: int) -> dict:
        """
        Retrieves a single employee record by its primary key.

        Parameters:
            employee_id (int): The primary key of the employee to fetch.

        Returns:
            dict: statusCode 200 with the employee data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the employee by ID
                "SELECT * FROM employees WHERE id = %s", [employee_id]
            )

            return {  # return found employee
                "statusCode": 200,  # success code
                "data": Employee._with_signed_photo(rows[0]),  # the single employee record, with signed photo URL
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"Employee {employee_id} not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get total employee count
    # --------------------------

    @staticmethod
    def get_total() -> int:
        """
        Returns the total number of employees in the database.

        Returns:
            int: Total employee count, or 0 on failure.
        """
        try:
            rows = fetch_query("SELECT COUNT(*) as total FROM employees")  # run count query
            return rows[0]["total"] if rows else 0  # return the count or 0 if empty
        except Exception:  # catch unexpected errors silently
            return 0  # return 0 as a safe fallback

    # --------------------------
    # Update employee
    # --------------------------

    @staticmethod
    def update(employee_id: int, data: dict) -> dict:
        """
        Updates an existing employee record with only the provided fields.

        Parameters:
            employee_id (int): The primary key of the employee to update.
            data (dict): A dict of fields to update (only known, non-None values are applied).

        Returns:
            dict: statusCode 200 with the updated employee data, or an error dict.
        """
        try:
            allowed_fields = [  # fields that are permitted to be updated
                "first_name", "last_name", "middle_name",
                "email", "employee_type", "employment_status", "school_id",
                "division", "original_appointment", "latest_appointment",
                "position", "salary", "contact_number", "is_active", "photo"
            ]

            fields = {  # filter to only allowed, non-None fields
                k: v for k, v in data.items() if k in allowed_fields and v is not None
            }

            if not fields:  # check if there is anything to update
                return {"statusCode": 400, "message": "No valid fields to update"}  # return 400 if empty

            check = fetch_query(  # verify the employee exists before updating
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )

            if not check:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            set_clause = ", ".join(f"{col} = %s" for col in fields)  # build SET col = %s pairs
            values = list(fields.values()) + [employee_id]  # values for SET fields + WHERE id

            result = query(  # execute the UPDATE
                f"UPDATE employees SET {set_clause} WHERE id = %s", values
            )

            if result["statusCode"] != 200:  # check if update failed
                return result  # return the error response

            rows = fetch_query(  # fetch the updated employee record
                "SELECT * FROM employees WHERE id = %s", [employee_id]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "message": "Employee updated",  # confirmation message
                "data": Employee._with_signed_photo(rows[0]) if rows else None,  # the updated record, with signed photo URL
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Delete employee
    # --------------------------

    @staticmethod
    def delete(employee_id: int) -> dict:
        """
        Deletes an employee record from the database by its primary key.

        Parameters:
            employee_id (int): The primary key of the employee to delete.

        Returns:
            dict: statusCode 200 with a success message, or an error dict.
        """
        try:
            check = fetch_query(  # verify the employee exists before deleting
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )

            if not check:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            result = query(  # execute the DELETE
                "DELETE FROM employees WHERE id = %s", [employee_id]
            )

            if result["statusCode"] == 200:  # check if delete succeeded
                result["message"] = "Employee deleted"  # attach confirmation message

            return result  # return the gateway result

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Search employees
    # --------------------------

    @staticmethod
    def search(query_str: str, page: int = 1, limit: int = 10) -> dict:
        """
        Searches employees by first name, last name, employee number, or email.

        Parameters:
            query_str (str): The search keyword to match against.
            page (int): The page number to retrieve (default 1).
            limit (int): The number of results per page (default 10).

        Returns:
            dict: statusCode 200 with matching employee records, or 404 if none found.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for pagination
            like = f"%{query_str}%"  # wrap the search term with wildcards for LIKE matching

            rows = fetch_query(  # search employees across name, numbers, and email fields
                """SELECT * FROM employees
                   WHERE first_name LIKE %s OR last_name LIKE %s
                      OR employee_number LIKE %s OR leave_card_number LIKE %s
                      OR email LIKE %s
                   ORDER BY id LIMIT %s OFFSET %s""",
                [like, like, like, like, like, limit, offset]
            )

            return {  # return matching results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of results returned
                "data": [Employee._with_signed_photo(row) for row in rows],  # the matching employee records, with signed photo URLs
            } if rows else {  # return 404 if no matches
                "statusCode": 404,
                "message": "No employees found matching the query",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Upload employee photo
    # --------------------------

    @staticmethod
    def upload_photo(employee_id: int, file) -> dict:
        """
        Uploads and saves a new photo for an employee to the server's local filesystem,
        replacing any previously uploaded photo.

        Parameters:
            employee_id (int): The primary key of the employee.
            file (FileStorage): The uploaded photo file from the request.

        Returns:
            dict: statusCode 200 with the updated employee data, or an error dict.
        """
        try:
            if not file or file.filename == "":  # check a file was actually provided
                return {"statusCode": 400, "message": "No photo file provided"}  # return 400 if missing

            if not is_allowed_file(file.filename):  # validate the file extension
                return {"statusCode": 400, "message": "Unsupported file type. Allowed: png, jpg, jpeg, gif"}  # return 400 if disallowed

            existing = fetch_query(  # verify the employee exists and get the current photo path
                "SELECT id, photo FROM employees WHERE id = %s", [employee_id]
            )

            if not existing:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            extension = file.filename.rsplit(".", 1)[1].lower()  # extract the file extension
            unique_filename = f"{uuid.uuid4().hex}.{extension}"  # generate a unique filename to avoid collisions

            save_result = save_file(file, unique_filename)  # save the file to disk via the storage gateway

            if save_result["statusCode"] != 200:  # check if saving the file failed
                return save_result  # return the error from the gateway

            old_photo = existing[0]["photo"]  # capture the old photo path for cleanup after update

            result = query(  # update the employee's photo column with the new path
                "UPDATE employees SET photo = %s WHERE id = %s",
                [save_result["path"], employee_id]
            )

            if result["statusCode"] != 200:  # check if the update failed
                return result  # return the error from the gateway

            if old_photo:  # an old photo existed before this upload
                delete_file(old_photo)  # remove the old photo file from disk

            rows = fetch_query(  # fetch the updated employee record
                "SELECT * FROM employees WHERE id = %s", [employee_id]
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "message": "Employee photo uploaded successfully",  # confirmation message
                "data": Employee._with_signed_photo(rows[0]) if rows else None,  # the updated employee record, with signed photo URL
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get leave balances by employee
    # --------------------------

    @staticmethod
    def get_leave_balances(employee_id: int) -> dict:
        """
        Retrieves all leave balances for a specific employee joined with leave type details.

        Parameters:
            employee_id (int): The primary key of the employee.

        Returns:
            dict: statusCode 200 with a list of leave balances, or 404 if employee not found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
                [employee_id]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            rows = fetch_query(  # fetch all leave balances joined with leave type info
                """SELECT elb.id, elb.balance,
                          lt.id as leave_type_id, lt.code, lt.name, lt.balance_type
                   FROM employee_leave_balances elb
                   JOIN leave_types lt ON lt.id = elb.leave_type_id
                   WHERE elb.employee_id = %s
                   ORDER BY lt.code ASC""",
                [employee_id]
            )

            return {  # return results
                "statusCode": 200,  # success code
                "employee": employee[0],  # basic employee info for context
                "data": rows if rows else [],  # list of leave balances, empty list if none yet
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
