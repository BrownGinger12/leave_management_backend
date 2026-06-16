from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.employee import Employee  # import the Employee model for all CRUD operations
from pydantic import ValidationError  # import ValidationError to catch Pydantic validation failures


def create_employee():
    """
    Handles creating a new employee.
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


def get_employees_paginated():
    """
    Handles fetching a paginated list of employees.
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


def get_employee_by_id(employee_id: int):
    """
    Handles fetching a single employee by their primary key.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the employee data and HTTP 200, or an error response.
    """
    try:
        result = Employee.get_by_id(employee_id)  # delegate to the Employee model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except ValidationError as e:  # catch Pydantic validation errors
        return jsonify({"message": str(e)}), 400  # return 400 with validation detail
    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_total_employee_pages():
    """
    Handles computing total pages based on the limit query param.
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


def get_employee_count():
    """
    Handles returning the total number of employees.

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


def update_employee(employee_id: int):
    """
    Handles updating an existing employee's fields.
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


def delete_employee(employee_id: int):
    """
    Handles deleting an employee by their primary key.

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


def search_employees():
    """
    Handles searching employees by keyword across name, employee number, and email.
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


def get_employee_leave_balances(employee_id: int):
    """
    Handles GET /employees/<employee_id>/leave-balances — retrieves all leave balances for an employee.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with the employee's leave balances per leave type and HTTP 200, or an error response.
    """
    try:
        result = Employee.get_leave_balances(employee_id)  # delegate to the Employee model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
