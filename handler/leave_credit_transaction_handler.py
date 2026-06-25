from flask import request, jsonify  # import request to read query params and jsonify to build responses
from model.leave_credit_transaction import LeaveCreditTransaction  # import the model


def get_transactions_by_employee(employee_id: int):
    """
    Handles GET /leave-credit-transactions/employee/<employee_id> — retrieves paginated
    ledger transactions for a specific employee.
    Accepts query params: page (default 1), limit (default 10).

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with paginated transaction data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = LeaveCreditTransaction.get_by_employee(  # delegate to the model
            employee_id, page=page, limit=limit
        )
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


def get_transactions_by_employee_and_year(employee_id: int, year: int):
    """
    Handles GET /leave-credit-transactions/employee/<employee_id>/year/<year> — retrieves
    all ledger transactions for a specific employee in the given calendar year.

    Parameters:
        employee_id (int): The employee's primary key from the URL.
        year (int): The calendar year from the URL (e.g. 2026).

    Returns:
        JSON response with transaction data for that year and HTTP 200, or an error response.
    """
    try:
        result = LeaveCreditTransaction.get_by_employee_and_year(  # delegate to the model
            employee_id, year
        )
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
