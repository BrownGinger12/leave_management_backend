from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.leave_application import LeaveApplication  # import the LeaveApplication model


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


def get_all_leave_applications():
    """
    Handles GET /leave-applications — retrieves a paginated list of all leave applications.
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
