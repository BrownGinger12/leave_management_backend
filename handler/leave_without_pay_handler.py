from flask import request, jsonify  # import request/jsonify for HTTP I/O
from datetime import date  # import date for default year range
from model.leave_without_pay import LeaveWithoutPay  # import the LWOP model
from gateway.auth_gateway import require_role  # import role decorator


def _current_year_range():
    """Returns (Jan 1, Dec 31) of the current year as YYYY-MM-DD strings."""
    year = date.today().year  # current calendar year
    return f"{year}-01-01", f"{year}-12-31"  # full year range


@require_role("PAYROLL")
def get_teaching_leave_without_pay():
    """
    Handles GET /leave-without-pay/teaching.
    Returns a paginated list of leave-without-pay dates for TEACHING employees.
    PAYROLL only.

    Query params:
        date_from (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.
        page      (int): Page number. Default 1.
        limit     (int): Records per page. Default 10.

    Returns:
        JSON response with paginated LWOP records and HTTP 200, or an error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # read start date
        date_to   = request.args.get("date_to",   default=default_to,   type=str)  # read end date
        page      = request.args.get("page",       default=1,            type=int)  # read page number
        limit     = request.args.get("limit",      default=10,           type=int)  # read page size

        response = LeaveWithoutPay.get_paginated("TEACHING", date_from, date_to, page, limit)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


@require_role("PAYROLL")
def get_non_teaching_leave_without_pay():
    """
    Handles GET /leave-without-pay/non-teaching.
    Returns a paginated list of leave-without-pay dates for NON_TEACHING employees.
    PAYROLL only.

    Query params:
        date_from (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.
        page      (int): Page number. Default 1.
        limit     (int): Records per page. Default 10.

    Returns:
        JSON response with paginated LWOP records and HTTP 200, or an error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # read start date
        date_to   = request.args.get("date_to",   default=default_to,   type=str)  # read end date
        page      = request.args.get("page",       default=1,            type=int)  # read page number
        limit     = request.args.get("limit",      default=10,           type=int)  # read page size

        response = LeaveWithoutPay.get_paginated("NON_TEACHING", date_from, date_to, page, limit)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500
