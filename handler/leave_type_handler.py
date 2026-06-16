from flask import jsonify  # import jsonify to build responses
from model.leave_type import LeaveType  # import the LeaveType model


def get_all_leave_types():
    """
    Handles GET /leave-types — retrieves all leave types.

    Returns:
        JSON response with all leave types and HTTP 200, or an error response.
    """
    try:
        result = LeaveType.get_all()  # delegate to the LeaveType model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
