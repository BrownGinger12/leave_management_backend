from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.monthly_leave_credit import MonthlyLeaveCredit  # import the MonthlyLeaveCredit model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN")
def credit_monthly_leave():
    """
    Handles POST /monthly-leave-credits — credits a monthly VL or SL amount to an employee.
    ADMIN only. Rejects duplicates for the same employee, leave type, year, and month.

    Returns:
        JSON response with the created credit record and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        result = MonthlyLeaveCredit.credit(data)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL", "PAYROLL")
def get_monthly_credits_by_employee_and_year(employee_id: int, year: int):
    """
    Handles GET /monthly-leave-credits/employee/<employee_id>/year/<year> — retrieves
    all monthly VL/SL credits for a specific employee in the given calendar year.
    ADMIN, DIVISION_PERSONNEL, and PAYROLL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.
        year (int): The calendar year from the URL (e.g. 2026).

    Returns:
        JSON response with the monthly credit records and HTTP 200, or an error response.
    """
    try:
        result = MonthlyLeaveCredit.get_by_employee_and_year(employee_id, year)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
