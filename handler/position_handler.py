from flask import jsonify  # import jsonify to build JSON responses
from model.position import Position  # import the Position model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_positions():
    """
    Handles GET /positions — retrieves all positions, optionally filtered by type.
    ADMIN and DIVISION_PERSONNEL only.

    Accepts optional query parameter:
        type (str): TEACHING or NON_TEACHING — narrows results to that category.

    Returns:
        JSON response with the list of positions and HTTP 200, or an error response.
    """
    try:
        result = Position.get_all()  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
