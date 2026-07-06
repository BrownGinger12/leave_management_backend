from flask import request, jsonify  # import request for HTTP input and jsonify for responses
from model.user import User  # import the User model
from gateway.auth_gateway import require_role  # import the role-enforcement decorator


@require_role("ADMIN")
def create_user():
    """
    Handles POST /users — creates a new user account linked to an employee. ADMIN only.
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
    Handles GET /users — retrieves a paginated list of all user accounts. ADMIN only.
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
    Handles GET /users/<user_id> — retrieves a single user account by ID. ADMIN only.

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


@require_role("ADMIN")
def update_user_role(user_id: int):
    """
    Handles PATCH /users/<user_id>/role — changes the role of a user account. ADMIN only.
    Protected against removing the last ADMIN account from the system.

    Parameters:
        user_id (int): The user's primary key from the URL.

    Body:
        role (str): New role — ADMIN | DIVISION_PERSONNEL | TEACHING_PERSONNEL.

    Returns:
        JSON response with the updated user and HTTP 200, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = User.update_role(user_id, data)  # delegate role update to the User model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def deactivate_user(user_id: int):
    """
    Handles PATCH /users/<user_id>/deactivate — deactivates a user account. ADMIN only.
    The account remains in the database but the user can no longer log in.
    Protected against deactivating the last ADMIN account.

    Parameters:
        user_id (int): The user's primary key from the URL.

    Returns:
        JSON response with the updated user and HTTP 200, or an error response.
    """
    try:
        response = User.set_active(user_id, is_active=False)  # delegate to model with is_active=False
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def activate_user(user_id: int):
    """
    Handles PATCH /users/<user_id>/activate — reactivates a previously deactivated account. ADMIN only.

    Parameters:
        user_id (int): The user's primary key from the URL.

    Returns:
        JSON response with the updated user and HTTP 200, or an error response.
    """
    try:
        response = User.set_active(user_id, is_active=True)  # delegate to model with is_active=True
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def delete_user(user_id: int):
    """
    Handles DELETE /users/<user_id> — permanently deletes a user account. ADMIN only.
    The linked employee record is not affected.
    Protected against deleting the last ADMIN account.

    Parameters:
        user_id (int): The user's primary key from the URL.

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        response = User.delete(user_id)  # delegate deletion to the User model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def reset_user_password(user_id: int):
    """
    Handles PATCH /users/<user_id>/reset-password — resets a user's password. ADMIN only.
    The new password is hashed with bcrypt before storing.

    Parameters:
        user_id (int): The user's primary key from the URL.

    Body:
        new_password (str): The new plain-text password (minimum 8 characters).

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = User.reset_password(user_id, data)  # delegate to the User model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
