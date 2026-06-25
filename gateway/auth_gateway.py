# gateway/auth_gateway.py
import os  # used to read environment variables
import jwt  # used to create and verify JWT tokens
import time  # used to compute token expiry timestamps
from functools import wraps  # used to preserve the wrapped function's metadata
from flask import request, jsonify, g  # request for headers, g for storing current user per request
from dotenv import load_dotenv  # loads environment variables from .env

load_dotenv()  # ensure env vars are available even if this module is imported before app.py calls load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret-change-me")  # secret key used to sign tokens
JWT_ALGORITHM = "HS256"  # HMAC-SHA256 signing algorithm
JWT_EXPIRY_SECONDS = 8 * 60 * 60  # tokens expire after 8 hours (one working day)


def create_token(payload: dict) -> str:
    """
    Creates a signed JWT token containing the given payload plus an expiry timestamp.

    Parameters:
        payload (dict): Data to embed in the token (e.g. user_id, role).

    Returns:
        str: The signed JWT string.
    """
    data = dict(payload)  # copy the payload so the original is not mutated
    data["exp"] = int(time.time()) + JWT_EXPIRY_SECONDS  # set the expiry timestamp
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)  # sign and return the token


def verify_token(token: str) -> dict:
    """
    Verifies a JWT token and returns its decoded payload.
    Returns None if the token is invalid or expired.

    Parameters:
        token (str): The JWT string to verify.

    Returns:
        dict: The decoded payload, or None if verification fails.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])  # decode and verify the token
    except jwt.ExpiredSignatureError:  # token has passed its expiry time
        return None  # treat as unauthenticated
    except jwt.InvalidTokenError:  # token is malformed or tampered
        return None  # treat as unauthenticated


def require_auth(f):
    """
    Decorator that enforces authentication on a route handler.
    Reads a Bearer token from the Authorization header, verifies it,
    and stores the decoded payload in Flask's g.current_user.

    Parameters:
        f: The route handler function to protect.

    Returns:
        function: The wrapped handler that checks auth before proceeding.
    """
    @wraps(f)  # preserve the original function's name and docstring
    def decorated(*args, **kwargs):  # replacement function that runs before the original handler
        auth_header = request.headers.get("Authorization", "")  # read the Authorization header

        if not auth_header.startswith("Bearer "):  # check for Bearer token format
            return jsonify({"statusCode": 401, "message": "Authorization header missing or invalid"}), 401  # reject

        token = auth_header[7:]  # strip the 'Bearer ' prefix to get the raw token
        payload = verify_token(token)  # verify the token signature and expiry

        if not payload:  # token is invalid or expired
            return jsonify({"statusCode": 401, "message": "Token is invalid or expired"}), 401  # reject

        g.current_user = payload  # store the decoded payload for use in the handler
        return f(*args, **kwargs)  # call the original handler

    return decorated  # return the wrapped function


def require_role(*roles):
    """
    Decorator factory that enforces both authentication and a specific role on a route handler.
    Stores the decoded token payload in Flask's g.current_user if access is granted.

    Parameters:
        *roles: One or more role strings the authenticated user must have (e.g. 'ADMIN').

    Returns:
        function: A decorator that enforces the role check before calling the handler.
    """
    def decorator(f):  # the actual decorator returned by the factory
        @wraps(f)  # preserve the original function's name and docstring
        def decorated(*args, **kwargs):  # replacement function that runs before the original handler
            auth_header = request.headers.get("Authorization", "")  # read the Authorization header

            if not auth_header.startswith("Bearer "):  # check for Bearer token format
                return jsonify({"statusCode": 401, "message": "Authorization header missing or invalid"}), 401  # reject

            token = auth_header[7:]  # strip the 'Bearer ' prefix to get the raw token
            payload = verify_token(token)  # verify the token signature and expiry

            if not payload:  # token is invalid or expired
                return jsonify({"statusCode": 401, "message": "Token is invalid or expired"}), 401  # reject

            if payload.get("role") not in roles:  # check if the user's role is in the allowed list
                return jsonify({"statusCode": 403, "message": "You do not have permission to perform this action"}), 403  # reject

            g.current_user = payload  # store the decoded payload for use in the handler
            return f(*args, **kwargs)  # call the original handler

        return decorated  # return the wrapped function

    return decorator  # return the decorator
