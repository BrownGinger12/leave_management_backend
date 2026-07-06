from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.leave_credit import LeaveCredit  # import the LeaveCredit model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN")
def credit_leave():
    """
    Handles POST /leave-credits — credits leave days to an employee's balance via MANUAL_ADJUSTMENT.
    ADMIN only. Inserts a CREDIT into the ledger and updates the balance cache.

    Returns:
        JSON response with the created transaction and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = LeaveCredit.credit(data)  # delegate credit logic to the LeaveCredit model
        return jsonify(response), response["statusCode"]  # return the model response with its status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def post_forwarded_balance():
    """
    Handles POST /leave-credits/forwarded-balance — posts a FORWARDED_BALANCE CREDIT
    for a specific leave type at the start of a given year. ADMIN only.
    Idempotent: calling again with a different amount updates the existing record.

    Returns:
        JSON response with HTTP 201 (created) or 200 (updated), or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = LeaveCredit.post_forwarded_balance(data)  # delegate forwarded balance logic to model
        return jsonify(response), response["statusCode"]  # return the model response with its status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
