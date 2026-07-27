from flask import request, jsonify  # import request/jsonify for HTTP I/O
from model.balance_deduction import BalanceDeduction  # import the BalanceDeduction model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN")
def create_balance_deduction():
    """
    Handles POST /balance-deductions — manually deducts days from an employee's leave balance.
    ADMIN only.

    Body (JSON):
        employee_id   (int):   Target employee.
        leave_type_id (int):   Leave type to deduct from.
        amount        (float): Days to deduct (must be > 0).
        deduction_date (str):  Effective date (YYYY-MM-DD).
        remarks       (str):   Optional notes.

    Returns:
        JSON response with the created deduction record and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = BalanceDeduction.create(data)  # delegate to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def get_balance_deduction_history():
    """
    Handles GET /balance-deductions/history — retrieves a filterable, searchable,
    paginated history of manual balance deductions. ADMIN only.

    Query params:
        query         (str): Keyword to search employee name, employee number, or deduction number.
        date_from     (str): Earliest deduction date to include (YYYY-MM-DD).
        date_to       (str): Latest deduction date to include (YYYY-MM-DD).
        year          (int): Calendar year filter (ignored when date_from or date_to is set).
        employee_id   (int): Filter to a specific employee.
        leave_type_id (int): Filter to a specific leave type.
        page          (int): Page number (default 1).
        limit         (int): Records per page (default 10).

    Returns:
        JSON response with paginated history records and applied filters, or an error response.
    """
    try:
        query_str     = request.args.get("query",         default=None, type=str)   # keyword search
        date_from     = request.args.get("date_from",     default=None, type=str)   # lower date bound
        date_to       = request.args.get("date_to",       default=None, type=str)   # upper date bound
        year          = request.args.get("year",          default=None, type=int)   # calendar year filter
        employee_id   = request.args.get("employee_id",   default=None, type=int)   # employee filter
        leave_type_id = request.args.get("leave_type_id", default=None, type=int)   # leave type filter
        page          = request.args.get("page",          default=1,    type=int)   # page number
        limit         = request.args.get("limit",         default=10,   type=int)   # page size

        response = BalanceDeduction.get_history(  # delegate to the model
            page=page, limit=limit, query_str=query_str,
            date_from=date_from, date_to=date_to, year=year,
            employee_id=employee_id, leave_type_id=leave_type_id,
        )
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def get_all_balance_deductions():
    """
    Handles GET /balance-deductions — retrieves a paginated list of manual balance deductions.
    ADMIN only.

    Query params:
        page        (int): Page number (default 1).
        limit       (int): Records per page (default 10).
        employee_id (int): Optional — filter to a specific employee.

    Returns:
        JSON response with paginated deduction records and HTTP 200, or an error response.
    """
    try:
        page        = request.args.get("page",        default=1,    type=int)  # read page number
        limit       = request.args.get("limit",       default=10,   type=int)  # read page size
        employee_id = request.args.get("employee_id", default=None, type=int)  # optional employee filter

        response = BalanceDeduction.get_paginated(page=page, limit=limit, employee_id=employee_id)  # delegate to model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def get_balance_deduction_by_id(deduction_id: int):
    """
    Handles GET /balance-deductions/<deduction_id> — retrieves a single manual balance deduction by ID.
    ADMIN only.

    Parameters:
        deduction_id (int): The deduction's primary key from the URL.

    Returns:
        JSON response with the deduction record and HTTP 200, or an error response.
    """
    try:
        response = BalanceDeduction.get_by_id(deduction_id)  # delegate to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def delete_balance_deduction(deduction_id: int):
    """
    Handles DELETE /balance-deductions/<deduction_id> — soft-deletes a deduction and reverses the DEBIT.
    ADMIN only.

    Parameters:
        deduction_id (int): The deduction's primary key from the URL.

    Returns:
        JSON response with a success message and the restored balance, or an error response.
    """
    try:
        response = BalanceDeduction.soft_delete(deduction_id)  # delegate to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
