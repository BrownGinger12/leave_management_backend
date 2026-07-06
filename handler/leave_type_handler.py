from flask import jsonify  # import jsonify to build responses
from model.leave_type import LeaveType  # import the LeaveType model
from gateway.auth_gateway import require_auth  # import auth decorator


@require_auth
def get_all_leave_types():
    """
    Handles GET /leave-types — retrieves all leave types.
    Requires authentication (any role).

    Returns:
        JSON response with all leave types and HTTP 200, or an error response.
    """
    try:
        result = LeaveType.get_all()  # delegate to the LeaveType model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_teaching_leave_types(employee_id: int):
    """
    Handles GET /leave-types/teaching/<employee_id> — retrieves all leave types
    available for teaching staff, excluding SL (Sick Leave) and PR (Personal Reason).
    Requires authentication (any role).

    Parameters:
        employee_id (int): The employee's primary key from the URL path.

    Returns:
        JSON response with filtered leave types and HTTP 200, or an error response.
    """
    try:
        result = LeaveType.get_teaching(employee_id)  # delegate to the LeaveType model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
