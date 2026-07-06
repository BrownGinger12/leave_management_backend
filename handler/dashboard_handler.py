from flask import request, jsonify  # import request/jsonify for HTTP I/O
from datetime import date  # import date for default date fallback
from model.dashboard import Dashboard  # import the Dashboard model
from gateway.auth_gateway import require_role  # import role decorator


def _today() -> str:
    """Returns today's date as a YYYY-MM-DD string."""
    return date.today().isoformat()  # ISO format date string


def _current_year_range():
    """Returns (Jan 1, Dec 31) of the current year as a tuple of YYYY-MM-DD strings."""
    year = date.today().year  # current calendar year
    return f"{year}-01-01", f"{year}-12-31"  # first and last day of the year


# --------------------------
# Teaching — employees on leave on a specific date
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_teaching_on_leave():
    """
    Handles GET /dashboard/teaching/on-leave.
    Returns all TEACHING employees who have an active leave application
    covering the given date. ADMIN and DIVISION_PERSONNEL only.

    Query params:
        date (str): The date to check (YYYY-MM-DD). Defaults to today.

    Returns:
        JSON response with employee list and HTTP 200, or an error response.
    """
    try:
        query_date = request.args.get("date", default=_today(), type=str)  # read date from query string; default today
        response = Dashboard.get_on_leave("TEACHING", query_date)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


# --------------------------
# Non-Teaching — employees on leave on a specific date
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_non_teaching_on_leave():
    """
    Handles GET /dashboard/non-teaching/on-leave.
    Returns all NON_TEACHING employees who have an active leave application
    covering the given date. ADMIN and DIVISION_PERSONNEL only.

    Query params:
        date (str): The date to check (YYYY-MM-DD). Defaults to today.

    Returns:
        JSON response with employee list and HTTP 200, or an error response.
    """
    try:
        query_date = request.args.get("date", default=_today(), type=str)  # read date from query string; default today
        response = Dashboard.get_on_leave("NON_TEACHING", query_date)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


# --------------------------
# Teaching — count on leave + total on a specific date
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_teaching_on_leave_count():
    """
    Handles GET /dashboard/teaching/on-leave/count.
    Returns the number of TEACHING employees on leave on the given date
    alongside the total TEACHING headcount. ADMIN and DIVISION_PERSONNEL only.

    Query params:
        date (str): The date to check (YYYY-MM-DD). Defaults to today.

    Returns:
        JSON response with counts and HTTP 200, or an error response.
    """
    try:
        query_date = request.args.get("date", default=_today(), type=str)  # read date from query string; default today
        response = Dashboard.get_on_leave_count("TEACHING", query_date)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


# --------------------------
# Non-Teaching — count on leave + total on a specific date
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_non_teaching_on_leave_count():
    """
    Handles GET /dashboard/non-teaching/on-leave/count.
    Returns the number of NON_TEACHING employees on leave on the given date
    alongside the total NON_TEACHING headcount. ADMIN and DIVISION_PERSONNEL only.

    Query params:
        date (str): The date to check (YYYY-MM-DD). Defaults to today.

    Returns:
        JSON response with counts and HTTP 200, or an error response.
    """
    try:
        query_date = request.args.get("date", default=_today(), type=str)  # read date from query string; default today
        response = Dashboard.get_on_leave_count("NON_TEACHING", query_date)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


# --------------------------
# Teaching — leave type breakdown per month
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_teaching_leave_type_breakdown():
    """
    Handles GET /dashboard/teaching/leave-type-breakdown.
    Returns a monthly breakdown of leave application counts and days per leave
    type for TEACHING employees within the given date range.
    ADMIN and DIVISION_PERSONNEL only.

    Query params:
        date_from (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.

    Returns:
        JSON response with monthly breakdown and HTTP 200, or an error response.
    """
    try:
        default_from, default_to = _current_year_range()  # defaults: full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # read start date
        date_to = request.args.get("date_to", default=default_to, type=str)  # read end date
        response = Dashboard.get_leave_type_breakdown("TEACHING", date_from, date_to)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


# --------------------------
# Non-Teaching — leave type breakdown per month
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_non_teaching_leave_type_breakdown():
    """
    Handles GET /dashboard/non-teaching/leave-type-breakdown.
    Returns a monthly breakdown of leave application counts and days per leave
    type for NON_TEACHING employees within the given date range.
    ADMIN and DIVISION_PERSONNEL only.

    Query params:
        date_from (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.

    Returns:
        JSON response with monthly breakdown and HTTP 200, or an error response.
    """
    try:
        default_from, default_to = _current_year_range()  # defaults: full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # read start date
        date_to = request.args.get("date_to", default=default_to, type=str)  # read end date
        response = Dashboard.get_leave_type_breakdown("NON_TEACHING", date_from, date_to)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


# --------------------------
# Latest pending leave applications
# --------------------------

@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_latest_pending_applications():
    """
    Handles GET /dashboard/pending-applications.
    Returns the 5 most recently filed leave applications still awaiting
    HRMO action, across all employee types. ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with up to 5 pending applications and HTTP 200, or an error response.
    """
    try:
        response = Dashboard.get_latest_pending(limit=5)  # delegate to model with fixed limit of 5
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500
