from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.leave_monetization import LeaveMonetization  # import the LeaveMonetization model
from gateway.auth_gateway import require_auth  # import auth decorator to protect routes


@require_auth
def submit_monetization():
    """
    Handles POST /leave-monetizations — submits a new leave monetization request.
    Validates balance and deducts VL and/or SL immediately on submission.

    Returns:
        JSON response with the created record and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = LeaveMonetization.submit(data)  # delegate submission logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_all_monetizations():
    """
    Handles GET /leave-monetizations — retrieves a paginated list of all leave monetizations.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated monetization data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveMonetization.get_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_monetization_by_id(monetization_id: int):
    """
    Handles GET /leave-monetizations/<id> — retrieves a single leave monetization by ID.

    Parameters:
        monetization_id (int): The primary key from the URL.

    Returns:
        JSON response with the record and HTTP 200, or an error response.
    """
    try:
        result = LeaveMonetization.get_by_id(monetization_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_monetizations_by_employee(employee_id: int):
    """
    Handles GET /leave-monetizations/employee/<employee_id> — retrieves all leave
    monetizations for a specific employee.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the list of records and HTTP 200, or an error response.
    """
    try:
        result = LeaveMonetization.get_by_employee(employee_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def delete_monetization(monetization_id: int):
    """
    Handles DELETE /leave-monetizations/<id> — soft-deletes a leave monetization.
    Reverses VL and SL balance deductions unless already RETURNED or DISAPPROVED.

    Parameters:
        monetization_id (int): The primary key from the URL.

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        response = LeaveMonetization.soft_delete(monetization_id)  # delegate to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
