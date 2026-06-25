from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
import bcrypt  # import bcrypt for secure password hashing
from gateway.mysql_gateway import fetch_query, query, query_insert  # import gateway functions
from gateway.auth_gateway import create_token  # import token creation helper


class User(BaseModel):
    """
    Pydantic model representing a system user account linked to an employee.

    Attributes:
        employee_id: FK to the employee this account belongs to.
        username: Unique login username.
        password: Plain-text password (only used on input; never stored).
        role: Access level — ADMIN, DIVISION_PERSONNEL, or TEACHING_PERSONNEL.
    """
    employee_id: int  # FK to employees table
    username: str  # unique login username
    password: str  # plain-text password on input; hashed before storing
    role: str  # ADMIN, DIVISION_PERSONNEL, or TEACHING_PERSONNEL

    # --------------------------
    # Hash password
    # --------------------------

    @staticmethod
    def _hash_password(plain: str) -> str:
        """
        Hashes a plain-text password using bcrypt with an auto-generated salt.

        Parameters:
            plain (str): The plain-text password to hash.

        Returns:
            str: The bcrypt hash string.
        """
        salt = bcrypt.gensalt()  # generate a random salt (includes cost factor)
        return bcrypt.hashpw(plain.encode(), salt).decode()  # hash and return as a string

    @staticmethod
    def _check_password(plain: str, hashed: str) -> bool:
        """
        Verifies a plain-text password against a stored bcrypt hash.

        Parameters:
            plain (str): The plain-text password to verify.
            hashed (str): The stored bcrypt hash to compare against.

        Returns:
            bool: True if the password matches, False otherwise.
        """
        return bcrypt.checkpw(plain.encode(), hashed.encode())  # constant-time comparison

    # --------------------------
    # Create user account
    # --------------------------

    @staticmethod
    def create(data: dict) -> dict:
        """
        Creates a new user account. Only callable by an ADMIN.
        Hashes the password before storing. Rejects duplicate usernames
        and employees who already have an account.

        Parameters:
            data (dict): Account fields — employee_id, username, password, role.

        Returns:
            dict: statusCode 201 with the created user data (no password hash), or an error dict.
        """
        try:
            required_fields = ["employee_id", "username", "password", "role"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if not data.get(field):  # check if field is missing or empty
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            valid_roles = ("ADMIN", "DIVISION_PERSONNEL", "TEACHING_PERSONNEL")  # allowed role values
            if data["role"] not in valid_roles:  # validate the role
                return {  # return 400 with the allowed values
                    "statusCode": 400,
                    "message": f"role must be one of: {', '.join(valid_roles)}",
                }

            employee = fetch_query(  # verify the linked employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )

            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            existing_username = fetch_query(  # check if the username is already taken
                "SELECT id FROM users WHERE username = %s", [data["username"]]
            )

            if existing_username:  # username conflict
                return {"statusCode": 409, "message": f"Username '{data['username']}' is already taken"}  # return 409

            existing_employee = fetch_query(  # check if this employee already has an account
                "SELECT id FROM users WHERE employee_id = %s", [data["employee_id"]]
            )

            if existing_employee:  # duplicate account for the same employee
                return {"statusCode": 409, "message": "This employee already has a user account"}  # return 409

            password_hash = User._hash_password(data["password"])  # hash the password before storing

            result = query_insert(  # insert the new user account
                """INSERT INTO users (employee_id, username, password_hash, role)
                   VALUES (%s, %s, %s, %s)""",
                [
                    data["employee_id"],  # FK to the employee
                    data["username"],     # unique username
                    password_hash,        # bcrypt hash of the password
                    data["role"],         # access role
                ]
            )

            if result["statusCode"] != 200:  # check if the insert failed
                return result  # return the error from the gateway

            rows = fetch_query(  # fetch the created account with joined employee info
                """SELECT u.id, u.employee_id, u.username, u.role, u.is_active,
                          u.last_login_at, u.created_at,
                          e.first_name, e.last_name, e.employee_number
                   FROM users u
                   JOIN employees e ON e.id = u.employee_id
                   WHERE u.id = %s""",
                [result["insertId"]]
            )

            return {  # return success response (password hash is never returned)
                "statusCode": 201,  # 201 Created
                "message": "User account created",  # confirmation message
                "data": rows[0] if rows else None,  # the created user record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Login
    # --------------------------

    @staticmethod
    def login(data: dict) -> dict:
        """
        Authenticates a user by username and password.
        On success, updates last_login_at and returns a signed JWT token.

        Parameters:
            data (dict): Login credentials — username, password.

        Returns:
            dict: statusCode 200 with the JWT token and user info, or an error dict.
        """
        try:
            if not data.get("username") or not data.get("password"):  # validate required fields
                return {"statusCode": 400, "message": "username and password are required"}  # return 400

            rows = fetch_query(  # fetch the user by username with joined employee info
                """SELECT u.*, e.first_name, e.last_name, e.employee_number
                   FROM users u
                   JOIN employees e ON e.id = u.employee_id
                   WHERE u.username = %s""",
                [data["username"]]
            )

            if not rows:  # user not found — use a generic message to prevent username enumeration
                return {"statusCode": 401, "message": "Invalid username or password"}  # return 401

            user = rows[0]  # shorthand for the matched user record

            if not user["is_active"]:  # account has been deactivated
                return {"statusCode": 403, "message": "This account has been deactivated"}  # return 403

            if not User._check_password(data["password"], user["password_hash"]):  # verify password
                return {"statusCode": 401, "message": "Invalid username or password"}  # return 401

            query(  # update the last login timestamp
                "UPDATE users SET last_login_at = NOW() WHERE id = %s", [user["id"]]
            )

            token = create_token({  # generate a signed JWT with the user's identity and role
                "user_id": user["id"],          # user primary key
                "employee_id": user["employee_id"],  # linked employee
                "role": user["role"],           # role for permission checks
                "username": user["username"],   # for display/audit purposes
            })

            return {  # return success response with the token
                "statusCode": 200,  # success code
                "message": "Login successful",  # confirmation message
                "token": token,  # JWT token — include as 'Authorization: Bearer <token>' in subsequent requests
                "user": {  # user info for the client to display (no password hash)
                    "id": user["id"],
                    "employee_id": user["employee_id"],
                    "username": user["username"],
                    "role": user["role"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "employee_number": user["employee_number"],
                },
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all users (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all user accounts with joined employee info.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated user data, or 404 if none found.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query("SELECT COUNT(*) AS total FROM users", [])  # get total count
            total = total_row[0]["total"] if total_row else 0  # extract count

            rows = fetch_query(  # fetch paginated users with joined employee info
                """SELECT u.id, u.employee_id, u.username, u.role, u.is_active,
                          u.last_login_at, u.created_at,
                          e.first_name, e.last_name, e.employee_number
                   FROM users u
                   JOIN employees e ON e.id = u.employee_id
                   ORDER BY u.created_at DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,
                "count": len(rows),  # number of records in this page
                "total": total,  # total number of users in the database
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": rows if rows else [],  # user records without password hashes
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get user by ID
    # --------------------------

    @staticmethod
    def get_by_id(user_id: int) -> dict:
        """
        Retrieves a single user account by its primary key with joined employee info.

        Parameters:
            user_id (int): The primary key of the user to fetch.

        Returns:
            dict: statusCode 200 with the user data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the user with joined employee details
                """SELECT u.id, u.employee_id, u.username, u.role, u.is_active,
                          u.last_login_at, u.created_at,
                          e.first_name, e.last_name, e.employee_number
                   FROM users u
                   JOIN employees e ON e.id = u.employee_id
                   WHERE u.id = %s""",
                [user_id]
            )

            return {  # return found user
                "statusCode": 200,
                "data": rows[0],
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"User {user_id} not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
