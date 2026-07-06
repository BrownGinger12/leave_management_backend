from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.service_credit_application import ServiceCreditApplication  # import the ServiceCreditApplication model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN", "DIVISION_PERSONNEL")
def submit_service_credit_application():
    """
    Handles POST /service-credit-applications — submits a new CTO or VSC service credit application.
    ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with the created application and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = ServiceCreditApplication.submit(data)  # delegate submission logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_service_credit_application_by_id(application_id: int):
    """
    Handles GET /service-credit-applications/<id> — retrieves a single application by ID.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        application_id (int): The application's primary key from the URL.

    Returns:
        JSON response with the application data and HTTP 200, or an error response.
    """
    try:
        result = ServiceCreditApplication.get_by_id(application_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_service_credit_applications_by_employee(employee_id: int):
    """
    Handles GET /service-credit-applications/employee/<employee_id> — retrieves all
    service credit applications submitted by a specific employee.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of applications and HTTP 200, or an error response.
    """
    try:
        result = ServiceCreditApplication.get_by_employee(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_service_credit_applications():
    """
    Handles GET /service-credit-applications — retrieves a paginated list of all applications.
    ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated service credit application data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = ServiceCreditApplication.get_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def search_service_credit_applications_by_special_order(special_order_id: int):
    """
    Handles GET /service-credit-applications/special-order/<special_order_id>/search —
    searches service credit applications within a specific Special Order.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        special_order_id (int): The Special Order's primary key from the URL.

    Returns:
        JSON response with paginated matching results and HTTP 200, or an error response.
    """
    try:
        query = request.args.get("q", default="", type=str)  # read search keyword from query string
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = ServiceCreditApplication.search_by_special_order(  # delegate to the model
            special_order_id=special_order_id, query=query, page=page, limit=limit
        )
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_service_credit_applications_by_special_order(special_order_id: int):
    """
    Handles GET /service-credit-applications/special-order/<special_order_id> —
    returns a paginated list of all service credit applications linked to a Special Order.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        special_order_id (int): The Special Order's primary key from the URL.

    Returns:
        JSON response with paginated application data and HTTP 200, or 404 if the SO does not exist.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = ServiceCreditApplication.get_by_special_order(  # delegate to the model
            special_order_id=special_order_id, page=page, limit=limit
        )
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_service_credit_application_by_number(application_number: str):
    """
    Handles GET /service-credit-applications/number/<application_number> — retrieves a
    single service credit application by its unique application number.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        application_number (str): The application number from the URL (e.g. 'SC-A1B2C3D4').

    Returns:
        JSON response with the application data and HTTP 200, or 404 if not found.
    """
    try:
        result = ServiceCreditApplication.get_by_application_number(application_number)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def search_service_credit_applications():
    """
    Handles GET /service-credit-applications/search — paginated service credit applications
    filtered by optional query params: special_order_id, type, year, date_from, date_to.
    ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with paginated filtered results and HTTP 200, or an error response.
    """
    try:
        filters = {  # build filters dict from query string params
            "special_order_id": request.args.get("special_order_id", type=int),  # filter by Special Order FK
            "type": request.args.get("type", type=str),  # filter by CTO or VSC
            "year": request.args.get("year", type=int),  # filter by calendar year of date_filed
            "date_from": request.args.get("date_from", type=str),  # lower bound of date_filed range
            "date_to": request.args.get("date_to", type=str),  # upper bound of date_filed range
        }

        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = ServiceCreditApplication.search(filters=filters, page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_vsc_old_leave_summary_by_employee(employee_id: int):
    """
    Handles GET /service-credit-applications/employee/<employee_id>/vsc-old-leave-summary —
    returns all VSC service credits earned from activities before 2024-10-01.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with old-period VSC credits and nested leave_applications, or error response.
    """
    try:
        result = ServiceCreditApplication.get_vsc_old_leave_summary(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_vsc_new_leave_summary_by_employee(employee_id: int):
    """
    Handles GET /service-credit-applications/employee/<employee_id>/vsc-new-leave-summary —
    returns all VSC service credits earned from activities on or after 2024-10-01.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with new-period VSC credits and nested leave_applications, or error response.
    """
    try:
        result = ServiceCreditApplication.get_vsc_new_leave_summary(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_cto_leave_summary_by_employee(employee_id: int):
    """
    Handles GET /service-credit-applications/employee/<employee_id>/cto-leave-summary —
    returns all CTO service credit records for the employee with nested leave applications.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of CTO credits with nested leave_applications and HTTP 200,
        or 404 if the employee is not found.
    """
    try:
        result = ServiceCreditApplication.get_cto_leave_summary(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
