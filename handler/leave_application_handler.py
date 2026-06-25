from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.leave_application import LeaveApplication  # import the LeaveApplication model
from gateway.auth_gateway import require_auth  # import auth decorator to protect routes


def submit_leave_application():
    """
    Handles POST /leave-applications — submits a new leave application.
    Validates leave type rules and employee balance before inserting.

    Returns:
        JSON response with the created application and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = LeaveApplication.submit(data)  # delegate submission logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_leave_application_by_id(application_id: int):
    """
    Handles GET /leave-applications/<id> — retrieves a single leave application by ID.

    Parameters:
        application_id (int): The application's primary key from the URL.

    Returns:
        JSON response with the application data and HTTP 200, or an error response.
    """
    try:
        result = LeaveApplication.get_by_id(application_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_leave_applications_by_employee_and_year(employee_id: int, year: int):
    """
    Handles GET /leave-applications/employee/<employee_id>/year/<year> — retrieves all leave
    applications for a specific employee in the given calendar year, each with embedded ledger data.

    Parameters:
        employee_id (int): The employee's primary key from the URL.
        year (int): The calendar year from the URL (e.g. 2026).

    Returns:
        JSON response with the list of applications (with ledger) and HTTP 200, or an error response.
    """
    try:
        result = LeaveApplication.get_by_employee_and_year(employee_id, year)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_leave_applications_by_employee(employee_id: int):
    """
    Handles GET /leave-applications/employee/<employee_id> — retrieves all applications for an employee.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of applications and HTTP 200, or an error response.
    """
    try:
        result = LeaveApplication.get_by_employee(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_leave_application_by_number(application_number: str):
    """
    Handles GET /leave-applications/number/<application_number> — retrieves a single leave
    application by its unique application number. No pagination.

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


def search_leave_applications():
    """
    Handles GET /leave-applications/search — paginated search with optional filters.
    Accepts query params: year, date_from, date_to, status, leave_type_code, page, limit.
    All filters are optional and combinable.

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
        }
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveApplication.search(filters=filters, page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_all_leave_applications():
    """
    Handles GET /leave-applications — retrieves a paginated list of all leave applications,
    excluding CTO and VSC types. Accepts query params: page (default 1), limit (default 10).

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


def get_all_leave_applications_including_cto_vsc():
    """
    Handles GET /leave-applications/all — retrieves a paginated list of ALL leave
    applications across all employees and all leave types including CTO and VSC.
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


def get_all_cto_vsc_leave_applications():
    """
    Handles GET /leave-applications/cto-vsc — retrieves a paginated list of CTO and VSC
    leave applications only. Accepts query params: page (default 1), limit (default 10).

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
    Reverses the old balance debit and posts a new one for the updated total.

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


@require_auth
def delete_leave_application(application_id: int):
    """
    Handles DELETE /leave-applications/<application_id> — soft-deletes a leave application.
    Reverses the balance debit if the application was not already returned or disapproved.
    The record remains in the database with is_deleted = 1 for recovery purposes.

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


def get_cto_vsc_leave_applications_by_employee(employee_id: int):
    """
    Handles GET /leave-applications/cto-vsc/employee/<employee_id> — retrieves all CTO and
    VSC leave applications for a specific employee, ordered by date filed descending.

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
