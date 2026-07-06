from flask import jsonify  # import jsonify to build responses
from model.school import School  # import the School model
from gateway.auth_gateway import require_auth  # import auth decorator


@require_auth
def get_all_schools():
    """
    Handles GET /schools — retrieves all schools in the division ordered alphabetically.
    Requires authentication (any role).

    Returns:
        JSON response with the list of schools and HTTP 200, or an error response.
    """
    try:
        result = School.get_all()  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
