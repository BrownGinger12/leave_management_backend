from flask import request, jsonify  # import request to read HTTP input and jsonify to build responses
from model.special_order import SpecialOrder  # import the SpecialOrder model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN")
def create_special_order():
    """
    Handles POST /special-orders — creates a new Special Order. ADMIN only.
    Returns 409 if the Special Order number already exists.

    Returns:
        JSON response with the created record and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        response = SpecialOrder.create(data)  # delegate creation logic to the model
        return jsonify(response), response["statusCode"]  # return the model response

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_special_order_by_id(special_order_id: int):
    """
    Handles GET /special-orders/<id> — retrieves a single Special Order by ID.
    ADMIN and DIVISION_PERSONNEL only.

    Parameters:
        special_order_id (int): The Special Order's primary key from the URL.

    Returns:
        JSON response with the record and HTTP 200, or an error response.
    """
    try:
        result = SpecialOrder.get_by_id(special_order_id)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def search_special_orders():
    """
    Handles GET /special-orders/search?q=<keyword> — searches Special Orders by
    special_order number or activity_name using a partial match. Paginated.
    ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with paginated matching Special Orders and HTTP 200, or an error response.
    """
    try:
        query = request.args.get("q", default="", type=str)  # read search keyword from query string
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = SpecialOrder.search(query=query, page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def filter_special_orders():
    """
    Handles GET /special-orders/filter — filters Special Orders by optional year and/or
    date range on date_of_activity. ADMIN and DIVISION_PERSONNEL only.

    Returns:
        JSON response with paginated filtered Special Orders and HTTP 200, or an error response.
    """
    try:
        filters = {  # build filters dict from query string params
            "year": request.args.get("year", type=int),  # filter by calendar year of date_of_activity
            "date_from": request.args.get("date_from", type=str),  # lower bound of date_of_activity range
            "date_to": request.args.get("date_to", type=str),  # upper bound of date_of_activity range
        }

        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = SpecialOrder.filter(filters=filters, page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN", "DIVISION_PERSONNEL")
def get_all_special_orders():
    """
    Handles GET /special-orders — retrieves a paginated list of all Special Orders.
    ADMIN and DIVISION_PERSONNEL only.
    Accepts query params: page (default 1), limit (default 10).

    Returns:
        JSON response with paginated data and HTTP 200, or an error response.
    """
    try:
        page = request.args.get("page", default=1, type=int)  # read page number from query string
        limit = request.args.get("limit", default=10, type=int)  # read page size from query string

        result = SpecialOrder.get_paginated(page=page, limit=limit)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
