from flask import request, jsonify  # import request for HTTP input and jsonify for responses
from model.user import User  # import the User model
from gateway.auth_gateway import require_role  # import the role-enforcement decorator


@require_role("ADMIN")
def create_user():
    """
    Handles POST /users — creates a new user account.
    Restricted to ADMIN accounts only via the require_role decorator.
    Expects a JSON body with employee_id, username, password, and role.

    Returns:
        JSON response with the created user and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = User.create(data)  # delegate creation to the User model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def get_all_users():
    """
    Handles GET /users — retrieves a paginated list of all user accounts.
    Restricted to ADMIN accounts only via the require_role decorator.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated user data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        response = User.get_paginated(page=page, limit=limit)  # delegate to the User model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def get_user_by_id(user_id: int):
    """
    Handles GET /users/<user_id> — retrieves a single user account by ID.
    Restricted to ADMIN accounts only via the require_role decorator.

    Parameters:
        user_id (int): The user's primary key from the URL.

    Returns:
        JSON response with the user data and HTTP 200, or an error response.
    """
    try:
        response = User.get_by_id(user_id)  # delegate to the User model
        return jsonify(response), response["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
