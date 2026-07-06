from flask import request, jsonify  # import request/jsonify for HTTP I/O
from model.employee_type_conversion import EmployeeTypeConversion  # import the conversion model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN")
def convert_employee_type(employee_id: int):
    """
    Handles POST /employees/<employee_id>/convert-type.
    Converts the employee's type between TEACHING and NON_TEACHING,
    applying the DepEd leave credit conversion formula and posting
    all required ledger transactions. ADMIN only.

    Expects a JSON body with:
        conversion_date (str, required): Effective date (YYYY-MM-DD).
        remarks        (str, optional): Notes about the conversion.
        created_by     (int, optional): FK to users.id for audit.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with conversion summary and HTTP 200, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body; return None if invalid

        if not data:  # check if body is missing or unparseable
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = EmployeeTypeConversion.convert(employee_id, data)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result with model's status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_conversion_history(employee_id: int):
    """
    Handles GET /employees/<employee_id>/conversion-history.
    Returns all personnel type conversion records for the given employee,
    newest first. ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        employee_id (int): The employee's primary key from the URL.

    Returns:
        JSON response with conversion history list and HTTP 200, or an error response.
    """
    try:
        response = EmployeeTypeConversion.get_by_employee(employee_id)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result with model's status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
