from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.leave_credit import LeaveCredit  # import the LeaveCredit model


def credit_leave():
    """
    Handles POST /leave-credits — credits VL or SL days to an employee's balance.
    Inserts a CREDIT into the ledger and updates the balance cache.

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
