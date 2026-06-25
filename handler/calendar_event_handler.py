from flask import request, jsonify  # import request to read input and jsonify to build responses
from gateway.auth_gateway import require_auth, require_role  # import auth decorators
from model.calendar_event import CalendarEvent  # import the CalendarEvent model


@require_auth
def get_events_by_year():
    """
    Handles GET /calendar-events?year=<year> — retrieves all calendar events for a given year.
    Requires a valid token (any role).

    Query Parameters:
        year (int): The calendar year to filter by. Defaults to the current year.

    Returns:
        JSON response with the list of events and HTTP 200, or an error response.
    """
    try:
        from datetime import date as _date  # import date locally to get the current year as default
        year = request.args.get("year", default=_date.today().year, type=int)  # read year, default to current year

        result = CalendarEvent.get_by_year(year)  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_auth
def get_events_current_month():
    """
    Handles GET /calendar-events/current-month — retrieves all calendar events for the current month.
    Requires a valid token (any role).

    Returns:
        JSON response with the list of events for this month and HTTP 200, or an error response.
    """
    try:
        result = CalendarEvent.get_current_month()  # delegate to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def create_calendar_event():
    """
    Handles POST /calendar-events — creates a new calendar event. Admin only.

    Body (JSON):
        date (str, required): YYYY-MM-DD format.
        name (str, required): Display name for the event.
        blocks_leave (int, optional): 1 = holiday (cannot apply leave), 0 = allowed. Default 0.
        is_paid (int, optional): 1 = paid leave day, 0 = no-pay. Default 1.

    Returns:
        JSON response with the new event ID and HTTP 201, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        result = CalendarEvent.create(data)  # delegate creation to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def update_calendar_event(event_id: int):
    """
    Handles PUT /calendar-events/<id> — updates an existing calendar event. Admin only.

    Parameters:
        event_id (int): The primary key of the event to update, from the URL.

    Body (JSON, all fields optional):
        date (str): New date in YYYY-MM-DD format.
        name (str): New display name.
        blocks_leave (int): 1 or 0.
        is_paid (int): 1 or 0.

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        data = request.get_json(silent=True)  # parse JSON body, return None if invalid

        if not data:  # check if body is missing or not valid JSON
            return jsonify({"message": "No data provided"}), 400  # return 400 if empty

        result = CalendarEvent.update(event_id, data)  # delegate update to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail


@require_role("ADMIN")
def delete_calendar_event(event_id: int):
    """
    Handles DELETE /calendar-events/<id> — deletes a calendar event by ID. Admin only.

    Parameters:
        event_id (int): The primary key of the event to delete, from the URL.

    Returns:
        JSON response with HTTP 200 on success, or an error response.
    """
    try:
        result = CalendarEvent.delete(event_id)  # delegate deletion to the model
        return jsonify(result), result["statusCode"]  # return result with its own status code

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500 with error detail
