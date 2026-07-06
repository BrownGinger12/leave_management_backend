from flask import request, jsonify, send_from_directory, g  # import request/jsonify for HTTP I/O, g for current user, send_from_directory to serve uploaded files
from model.employee import Employee  # import the Employee model for all CRUD operations
from pydantic import ValidationError  # import ValidationError to catch Pydantic validation failures
from gateway.file_storage_gateway import verify_signed_url  # import signature verification for private photo access
from gateway.auth_gateway import require_role, require_auth, check_school_access  # import role and auth decorators
from gateway.mysql_gateway import fetch_query  # import fetch_query for school_id lookup


@require_role("ADMIN")
def create_employee():
    """
    Handles creating a new employee. ADMIN only.
    Expects a JSON body with employee fields.

    Returns:
        JSON response with the created employee and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = Employee.create(data)  # delegate creation to the Employee model
        return jsonify(response), response["statusCode"]  # return the model response

    except ValidationError as e:  # catch Pydantic validation errors
        return jsonify({"message": str(e)}), 400  # return 400 with validation detail
    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_employees_paginated():
    """
    Handles fetching a paginated list of employees. ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated employee data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        response = Employee.get_paginated(page=page, limit=limit)  # delegate to the Employee model

        if response["statusCode"] != 200:  # check if the model returned an error
            return jsonify({"message": response.get("message", "Error fetching employees")}), response["statusCode"]

        return jsonify(response), 200  # return paginated results

    except ValidationError as e:  # catch Pydantic validation errors
        return jsonify({"message": str(e)}), 400  # return 400 with validation detail
    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_employee_by_id(employee_id: int):
    """
    Handles fetching a single employee by their primary key.
    ADMIN and DIVISION_PERSONNEL have unrestricted access.
    TEACHING_PERSONNEL can only access employees from their own school.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the employee data and HTTP 200, or an error response.
    """
    try:
        denied = check_school_access(employee_id)  # enforce school-level access for TEACHING role
        if denied:  # None means access is permitted; a tuple means forbidden
            return denied  # return 403 if denied

        result = Employee.get_by_id(employee_id)  # delegate to the Employee model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except ValidationError as e:  # catch Pydantic validation errors
        return jsonify({"message": str(e)}), 400  # return 400 with validation detail
    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_total_employee_pages():
    """
    Handles computing total pages based on the limit query param. ADMIN and DIVISION_PERSONNEL only.
    Accepts query param: limit (default 10).

    Returns:
        JSON response with total_employees, limit, and total_pages.
    """
    try:
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string
        limit = max(limit, 1)  # ensure limit is at least 1 to avoid division by zero

        total_employees = Employee.get_total()  # get the total employee count from the model
        total_pages = (total_employees + limit - 1) // limit  # ceiling division to compute total pages

        return jsonify({  # return pagination metadata
            "statusCode": 200,  # success code
            "total_employees": total_employees,  # total number of employees
            "limit": limit,  # page size used for calculation
            "total_pages": total_pages,  # total number of pages
        }), 200

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_employee_count():
    """
    Handles returning the total number of employees. ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with total_employees count and HTTP 200.
    """
    try:
        total_employees = Employee.get_total()  # get total count from the Employee model

        return jsonify({  # return count response
            "statusCode": 200,  # success code
            "total_employees": total_employees,  # total employee count
        }), 200

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def update_employee(employee_id: int):
    """
    Handles updating an existing employee's fields. ADMIN only.
    Expects a JSON body with the fields to update.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the updated employee data and HTTP 200, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = Employee.update(employee_id, data)  # delegate update to the Employee model
        return jsonify(response), response["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def delete_employee(employee_id: int):
    """
    Handles deleting an employee by their primary key. ADMIN only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with a success or error message.
    """
    try:
        result = Employee.delete(employee_id)  # delegate deletion to the Employee model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except ValidationError as e:  # catch Pydantic validation errors
        return jsonify({"message": str(e)}), 400  # return 400 with validation detail
    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def search_employees():
    """
    Handles searching employees by keyword. ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: query (required), page (default 1), limit (default 10).

    Returns:
        JSON response with matching employee records and HTTP 200, or an error response.
    """
    try:
        query_str = request.args.get("query", default="", type=str)  # read search keyword from query string
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        if not query_str or query_str.strip() == "":  # validate that a search keyword was provided
            return jsonify({"message": "Query parameter is required"}), 400  # return 400 if missing

        response = Employee.search(query_str.strip(), page=page, limit=limit)  # delegate to the Employee model

        if response["statusCode"] != 200:  # check if the model returned an error
            return jsonify({"message": response.get("message", "Error searching employees")}), response["statusCode"]

        return jsonify(response), 200  # return matching results

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def upload_employee_photo(employee_id: int):
    """
    Handles POST /employees/<employee_id>/photo — uploads a photo for an employee. ADMIN only.
    Expects a multipart/form-data request with a 'photo' file field.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the updated employee data and HTTP 200, or an error response.
    """
    try:
        file = request.files.get("photo")  # read the uploaded file from the multipart form

        result = Employee.upload_photo(employee_id, file)  # delegate to the Employee model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_employee_photo(filename: str):
    """
    Handles GET /uploads/employee_photos/<filename> — serves a previously uploaded employee photo.
    Requires a valid, non-expired 'expires' and 'signature' query param (see generate_signed_url).
    No auth decorator — access is controlled by the signed URL mechanism.

    Parameters:
        filename (str): The name of the photo file on disk, from the URL.

    Returns:
        The image file, or a 403/404 response if the signature is invalid/expired or the file is missing.
    """
    try:
        path = f"uploads/employee_photos/{filename}"  # reconstruct the relative path that was originally signed
        expires = request.args.get("expires")  # read the expiry timestamp from the query string
        signature = request.args.get("signature")  # read the signature from the query string

        if not verify_signed_url(path, expires, signature):  # check the signature is valid and not expired
            return jsonify({"message": "Invalid or expired photo URL"}), 403  # reject with 403 if verification fails

        return send_from_directory("uploads/employee_photos", filename)  # serve the file from the upload directory

    except Exception as e:  # catch unexpected errors (e.g. file not found)
        return jsonify({"message": str(e)}), 404  # return 404 with error detail


@require_auth
def get_employee_leave_balances(employee_id: int):
    """
    Handles GET /employees/<employee_id>/leave-balances — retrieves all leave balances for an employee.
    ADMIN and DIVISION_PERSONNEL have unrestricted access.
    TEACHING_PERSONNEL can only access employees from their own school.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the employee's leave balances per leave type and HTTP 200, or an error response.
    """
    try:
        denied = check_school_access(employee_id)  # enforce school-level access for TEACHING role
        if denied:  # None means access is permitted; a tuple means forbidden
            return denied  # return 403 if denied

        result = Employee.get_leave_balances(employee_id)  # delegate to the Employee model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_employees_by_school():
    """
    Handles GET /employees/my-school — retrieves a paginated list of employees from the
    current user's school. All authenticated roles can call this endpoint.

    TEACHING_PERSONNEL always sees their own school and cannot override it.
    ADMIN and DIVISION_PERSONNEL can optionally pass ?school_id=<id> to query any school;
    if omitted, their own linked school is used.

    Accepts query params: school_id (optional, ADMIN/DIVISION only), page (default 1), limit (default 10).

    Returns:
        JSON response with paginated employee data for the school and HTTP 200, or an error response.
    """
    try:
        role = g.current_user.get("role")  # read the caller's role from the token
        current_emp_id = g.current_user.get("employee_id")  # linked employee of the logged-in user

        if role == "TEACHING_PERSONNEL":  # TEACHING always uses their own school — no override
            emp_row = fetch_query(  # look up the current user's school from their employee record
                "SELECT school_id FROM employees WHERE id = %s", [current_emp_id]
            )
            if not emp_row or not emp_row[0]["school_id"]:  # employee or school not found
                return jsonify({"statusCode": 400, "message": "No school linked to your account"}), 400
            school_id = emp_row[0]["school_id"]  # use the school from their own employee record
        else:  # ADMIN and DIVISION_PERSONNEL may specify a school via query param
            school_id = request.args.get("school_id", type=int)  # read optional school_id from query string
            if not school_id:  # if not provided, fall back to their own linked school
                emp_row = fetch_query(  # look up their linked employee's school
                    "SELECT school_id FROM employees WHERE id = %s", [current_emp_id]
                )
                school_id = emp_row[0]["school_id"] if emp_row else None  # extract school_id
            if not school_id:  # still no school — cannot determine which school to query
                return jsonify({"statusCode": 400, "message": "school_id is required"}), 400

        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = Employee.get_paginated(page=page, limit=limit, school_id=school_id)  # delegate to model with school filter
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def search_employees_by_school():
    """
    Handles GET /employees/my-school/search — searches employees within the current user's
    school by keyword. All authenticated roles can call this endpoint.

    TEACHING_PERSONNEL always searches within their own school and cannot override it.
    ADMIN and DIVISION_PERSONNEL can optionally pass ?school_id=<id> to search any school;
    if omitted, their own linked school is used.

    Accepts query params: query (required), school_id (optional, ADMIN/DIVISION only),
    page (default 1), limit (default 10).

    Returns:
        JSON response with matching employee records for the school and HTTP 200, or an error response.
    """
    try:
        role = g.current_user.get("role")  # read the caller's role from the token
        current_emp_id = g.current_user.get("employee_id")  # linked employee of the logged-in user

        if role == "TEACHING_PERSONNEL":  # TEACHING always uses their own school — no override
            emp_row = fetch_query(  # look up the current user's school from their employee record
                "SELECT school_id FROM employees WHERE id = %s", [current_emp_id]
            )
            if not emp_row or not emp_row[0]["school_id"]:  # employee or school not found
                return jsonify({"statusCode": 400, "message": "No school linked to your account"}), 400
            school_id = emp_row[0]["school_id"]  # use the school from their own employee record
        else:  # ADMIN and DIVISION_PERSONNEL may specify a school via query param
            school_id = request.args.get("school_id", type=int)  # read optional school_id from query string
            if not school_id:  # if not provided, fall back to their own linked school
                emp_row = fetch_query(  # look up their linked employee's school
                    "SELECT school_id FROM employees WHERE id = %s", [current_emp_id]
                )
                school_id = emp_row[0]["school_id"] if emp_row else None  # extract school_id
            if not school_id:  # still no school — cannot determine which school to query
                return jsonify({"statusCode": 400, "message": "school_id is required"}), 400

        query_str = request.args.get("query", default="", type=str)  # read search keyword from query string
        if not query_str or not query_str.strip():  # validate that a search keyword was provided
            return jsonify({"statusCode": 400, "message": "query parameter is required"}), 400

        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = Employee.search(query_str.strip(), page=page, limit=limit, school_id=school_id)  # delegate to model with school filter
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
