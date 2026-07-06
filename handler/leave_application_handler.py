from flask import request, jsonify, g  # import request/jsonify for HTTP I/O, g for current user
from model.leave_application import LeaveApplication  # import the LeaveApplication model
from gateway.auth_gateway import require_auth, require_role, check_school_access  # import auth helpers
from gateway.mysql_gateway import fetch_query  # import fetch_query for school_id lookup


@require_auth
def submit_leave_application():
    """
    Handles POST /leave-applications — submits a new leave application.
    All authenticated roles can submit. TEACHING_PERSONNEL must submit for an employee
    from their own school.

    Returns:
        JSON response with the created application and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        employee_id = data.get("employee_id")  # extract the target employee from the body
        if employee_id:  # only check school access if employee_id is present (validation will catch missing later)
            denied = check_school_access(employee_id)  # TEACHING can only submit for their school
            if denied:  # None means allowed; tuple means forbidden
                return denied  # return 403

        response = LeaveApplication.submit(data)  # delegate submission logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_leave_application_by_id(application_id: int):
    """
    Handles GET /leave-applications/<id> — retrieves a single leave application by ID.
    ADMIN and DIVISION_PERSONNEL have unrestricted access.
    TEACHING_PERSONNEL can only access applications belonging to employees from their school.

    Parameters:
        application_id (int): The application's primary key from the URL.

    Returns:
        JSON response with the application data and HTTP 200, or an error response.
    """
    try:
        result = LeaveApplication.get_by_id(application_id)  # fetch application first to get employee_id

        if result["statusCode"] == 200 and g.current_user.get("role") == "TEACHING_PERSONNEL":  # school check for TEACHING
            employee_id = result.get("data", {}).get("employee_id")  # extract employee from the result
            if employee_id:  # only check if employee_id is present on the record
                denied = check_school_access(employee_id)  # enforce same-school restriction
                if denied:  # None means allowed; tuple means forbidden
                    return denied  # return 403

        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_leave_applications_by_employee_and_year(employee_id: int, year: int):
    """
    Handles GET /leave-applications/employee/<employee_id>/year/<year> — retrieves all leave
    applications for a specific employee in the given calendar year, each with running balance data.
    ADMIN and DIVISION_PERSONNEL have unrestricted access.
    TEACHING_PERSONNEL can only access employees from their own school.

    Parameters:
        employee_id (int): The employee's primary key from the URL.
        year (int): The calendar year from the URL (e.g. 2026).

    Returns:
        JSON response with the list of applications (with running balance) and HTTP 200, or an error response.
    """
    try:
        denied = check_school_access(employee_id)  # enforce school-level access for TEACHING role
        if denied:  # None means access is permitted; a tuple means forbidden
            return denied  # return 403

        result = LeaveApplication.get_by_employee_and_year(employee_id, year)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_leave_applications_by_employee(employee_id: int):
    """
    Handles GET /leave-applications/employee/<employee_id> — retrieves all applications for an employee.
    ADMIN and DIVISION_PERSONNEL have unrestricted access.
    TEACHING_PERSONNEL can only access employees from their own school.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of applications and HTTP 200, or an error response.
    """
    try:
        denied = check_school_access(employee_id)  # enforce school-level access for TEACHING role
        if denied:  # None means access is permitted; a tuple means forbidden
            return denied  # return 403

        result = LeaveApplication.get_by_employee(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_leave_application_by_number(application_number: str):
    """
    Handles GET /leave-applications/number/<application_number> — retrieves a single leave
    application by its unique application number. ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        application_number (str): The application number from the URL (e.g. 'LA-A1B2C3D4').

    Returns:
        JSON response with the application data and HTTP 200, or an error response.
    """
    try:
        result = LeaveApplication.get_by_application_number(application_number)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def search_leave_applications():
    """
    Handles GET /leave-applications/search — paginated search with optional filters.
    ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: year, date_from, date_to, status, leave_type_code, school_id, page, limit.

    Returns:
        JSON response with paginated matching leave applications and HTTP 200, or an error response.
    """
    try:
        filters = {  # collect optional filter values from query string
            "year": request.args.get("year", type=int),  # calendar year of date_filed
            "date_from": request.args.get("date_from"),  # lower bound of date_filed range (YYYY-MM-DD)
            "date_to": request.args.get("date_to"),  # upper bound of date_filed range (YYYY-MM-DD)
            "status": request.args.get("status"),  # application status filter
            "leave_type_code": request.args.get("leave_type_code"),  # leave type code filter (e.g. VL, SL)
            "school_id": request.args.get("school_id", type=int),  # school/division filter
        }
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveApplication.search(filters=filters, page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_leave_applications():
    """
    Handles GET /leave-applications — retrieves a paginated list of all leave applications,
    excluding CTO and VSC types. ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated leave application data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveApplication.get_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_leave_applications_including_cto_vsc():
    """
    Handles GET /leave-applications/all — retrieves a paginated list of ALL leave applications
    across all employees and all leave types including CTO and VSC. ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated leave application data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveApplication.get_all_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_cto_vsc_leave_applications():
    """
    Handles GET /leave-applications/cto-vsc — retrieves a paginated list of CTO and VSC
    leave applications only. ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated CTO/VSC leave application data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveApplication.get_cto_vsc_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def update_leave_application(application_id: int):
    """
    Handles PUT /leave-applications/<application_id> — replaces the leave dates on an
    existing application. Only allowed when the application status is 'FOR HRMO ACTION'.
    All authenticated roles can update their own application.

    Parameters:
        application_id (int): The application's primary key from the URL.

    Returns:
        JSON response with the updated application and HTTP 200, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = LeaveApplication.update(application_id, data)  # delegate update logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def delete_leave_application(application_id: int):
    """
    Handles DELETE /leave-applications/<application_id> — soft-deletes a leave application.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        application_id (int): The application's primary key from the URL.

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        response = LeaveApplication.soft_delete(application_id)  # delegate soft-delete logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_cto_vsc_leave_applications_by_employee(employee_id: int):
    """
    Handles GET /leave-applications/cto-vsc/employee/<employee_id> — retrieves all CTO and
    VSC leave applications for a specific employee. ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of CTO/VSC applications and HTTP 200, or an error response.
    """
    try:
        result = LeaveApplication.get_cto_vsc_by_employee(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_leave_applications_by_school():
    """
    Handles GET /leave-applications/my-school — retrieves a paginated list of leave applications
    for all employees belonging to the current user's school. All authenticated roles can call this.

    TEACHING_PERSONNEL always sees their own school and cannot override it.
    ADMIN and DIVISION_PERSONNEL can optionally pass ?school_id=<id> to query any school;
    if omitted, their own linked school is used.

    Accepts query params: school_id (optional, ADMIN/DIVISION only), page (default 1), limit (default 10).

    Returns:
        JSON response with paginated leave application data for the school and HTTP 200, or an error response.
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

        result = LeaveApplication.get_paginated(page=page, limit=limit, school_id=school_id)  # delegate to model with school filter
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
