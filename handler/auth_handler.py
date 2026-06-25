from flask import request, jsonify, g  # import request for HTTP input, jsonify for responses, g for current user
from model.user import User  # import the User model
from gateway.auth_gateway import require_auth  # import the auth decorator


def login():
    """
    Handles POST /auth/login — authenticates a user and returns a JWT token.
    Expects a JSON body with username and password.

    Returns:
        JSON response with the JWT token and user info on success, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = User.login(data)  # delegate to the User model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_me():
    """
    Handles GET /auth/me — returns the currently authenticated user's profile.
    Requires a valid Bearer token in the Authorization header.

    Returns:
        JSON response with the current user's data and HTTP 200, or an error response.
    """
    try:
        user_id = g.current_user["user_id"]  # extract the user ID from the decoded token
        result = User.get_by_id(user_id)  # fetch the user's full profile from the database
        return jsonify(result), result["statusCode"]  # return the result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
