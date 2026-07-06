from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.leave_approval import LeaveApproval  # import the LeaveApproval model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN", "DIVISION_PERSONNEL")
def decide_leave_application():
    """
    Handles POST /leave-approvals — processes an approver's APPROVED or REJECTED decision.
    ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with the approval record and HTTP 200, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = LeaveApproval.decide(data)  # delegate decision logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_approvals_by_application(application_id: int):
    """
    Handles GET /leave-approvals/application/<application_id> — retrieves all approval records for an application.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        application_id (int): The leave application's primary key from the URL.

    Returns:
        JSON response with the list of approval records and HTTP 200, or an error response.
    """
    try:
        result = LeaveApproval.get_by_application(application_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
