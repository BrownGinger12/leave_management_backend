from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.cto_application import CtoApplication  # import the CtoApplication model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN", "DIVISION_PERSONNEL")
def submit_cto_application():
    """
    Handles POST /cto-applications — submits a new CTO application.
    ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with the created application and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = CtoApplication.submit(data)  # delegate submission logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def decide_cto_application():
    """
    Handles POST /cto-applications/decide — processes an APPROVED or REJECTED decision.
    ADMIN only. On APPROVED: posts a CREDIT to the ledger and updates the CTO balance cache.

    Returns:
        JSON response with the updated application and HTTP 200, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = CtoApplication.decide(data)  # delegate decision logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_cto_application_by_id(application_id: int):
    """
    Handles GET /cto-applications/<id> — retrieves a single CTO application by ID.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        application_id (int): The CTO application's primary key from the URL.

    Returns:
        JSON response with the application data and HTTP 200, or an error response.
    """
    try:
        result = CtoApplication.get_by_id(application_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_cto_applications_by_employee(employee_id: int):
    """
    Handles GET /cto-applications/employee/<employee_id> — retrieves all CTO applications for an employee.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of applications and HTTP 200, or an error response.
    """
    try:
        result = CtoApplication.get_by_employee(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_cto_applications():
    """
    Handles GET /cto-applications — retrieves a paginated list of all CTO applications.
    ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated CTO application data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = CtoApplication.get_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
