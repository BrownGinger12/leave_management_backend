from flask import request, jsonify  # import request/jsonify for HTTP I/O
from model.annual_leave_credit import AnnualLeaveCredit  # import the annual credit model
from gateway.auth_gateway import require_role  # import role decorator
from datetime import date  # import date for default year


@require_role("ADMIN")
def post_annual_credits():
    """
    Handles POST /annual-leave-credits.
    Manually triggers the annual leave credit job for a given year (defaults to current year).
    ADMIN only. The scheduler calls AnnualLeaveCredit.post_annual_credits() automatically on Jan 1;
    this endpoint allows HR to re-run or backfill credits for any year.

    Body (optional JSON):
        year (int): The year to credit. Defaults to the current year.

    Returns:
        JSON response with credited/skipped counts and HTTP status.
    """
    try:
        body = request.get_json(silent=True) or {}  # parse optional JSON body
        year = body.get("year")  # read optional year override

        if year is not None:  # validate if provided
            try:
                year = int(year)  # cast to int
            except (TypeError, ValueError):  # not a valid integer
                return jsonify({"message": "year must be an integer"}), 400

        response = AnnualLeaveCredit.post_annual_credits(year=year)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500
