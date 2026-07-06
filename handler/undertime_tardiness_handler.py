from flask import request, jsonify  # import request/jsonify for HTTP I/O
from model.undertime_tardiness import UndertimeTardiness  # import the model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN")
def create_undertime_tardiness():
    """
    Handles POST /undertime-tardiness — creates a new undertime/tardiness VL deduction.
    ADMIN only. Only applicable to NON_TEACHING employees.
    Accepts: employee_id, undertime_points, tardiness_points, deduction_date, remarks (optional).

    Returns:
        JSON response with the created deduction and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400

        result = UndertimeTardiness.create(data)  # delegate creation to the model
        return jsonify(result), result["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_undertime_tardiness():
    """
    Handles GET /undertime-tardiness — retrieves a paginated list of all deductions.
    ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated deduction records and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = UndertimeTardiness.get_paginated(page=page, limit=limit)  # delegate to model
        return jsonify(result), result["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_undertime_tardiness_by_id(deduction_id: int):
    """
    Handles GET /undertime-tardiness/<id> — retrieves a single deduction by primary key.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        deduction_id (int): The deduction's primary key from the URL.

    Returns:
        JSON response with the deduction data and HTTP 200, or an error response.
    """
    try:
        result = UndertimeTardiness.get_by_id(deduction_id)  # delegate to model
        return jsonify(result), result["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500


@require_role("ADMIN", "DIVISION_PERSONNEL")
def search_undertime_tardiness():
    """
    Handles GET /undertime-tardiness/search — searches deductions by application number,
    employee name, or employee number. ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: query (required), page (default 1), limit (default 10).

    Returns:
        JSON response with matching records and HTTP 200, or an error response.
    """
    try:
        query_str = request.args.get("query", default="", type=str)  # read search keyword from query string
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        if not query_str or not query_str.strip():  # validate that a search keyword was provided
            return jsonify({"statusCode": 400, "message": "query parameter is required"}), 400

        result = UndertimeTardiness.search(query_str.strip(), page=page, limit=limit)  # delegate to model
        return jsonify(result), result["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500


@require_role("ADMIN", "DIVISION_PERSONNEL")
def filter_undertime_tardiness():
    """
    Handles GET /undertime-tardiness/filter — filters deductions by date range, year, or employee.
    ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: year, date_from, date_to, employee_id, page (default 1), limit (default 10).

    Returns:
        JSON response with filtered records and HTTP 200, or an error response.
    """
    try:
        filters = {  # collect optional filter values from query string
            "year": request.args.get("year", type=int),  # calendar year of deduction_date
            "date_from": request.args.get("date_from"),  # lower bound of deduction_date (YYYY-MM-DD)
            "date_to": request.args.get("date_to"),  # upper bound of deduction_date (YYYY-MM-DD)
            "employee_id": request.args.get("employee_id", type=int),  # filter by specific employee
        }
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = UndertimeTardiness.filter(filters=filters, page=page, limit=limit)  # delegate to model
        return jsonify(result), result["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500


@require_role("ADMIN")
def delete_undertime_tardiness(deduction_id: int):
    """
    Handles DELETE /undertime-tardiness/<id> — soft-deletes a deduction and reverses the VL debit.
    ADMIN only. Sets is_deleted = 1 and removes the corresponding DEBIT from the ledger.

    Parameters:
        deduction_id (int): The deduction's primary key from the URL.

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        result = UndertimeTardiness.soft_delete(deduction_id)  # delegate soft-delete to model
        return jsonify(result), result["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500
