from gateway.mysql_gateway import fetch_query, query, query_insert  # import DB helpers
from flask import g  # import g to read the authenticated user set by the auth decorator
from datetime import date  # import date for current month/year resolution


class CalendarEvent:
    """Model for managing calendar events — holidays and special pay/no-pay dates."""

    @staticmethod
    def get_by_year(year: int) -> dict:
        """
        Retrieves all calendar events for a given year, ordered by date ascending.

        Parameters:
            year (int): The calendar year to filter by.

        Returns:
            dict with statusCode, count, and data list.
        """
        rows = fetch_query(  # run the filtered SELECT
            """SELECT id, date, name, blocks_leave, period, created_by, created_at
               FROM calendar_events
               WHERE YEAR(date) = %s
               ORDER BY date ASC""",
            [year]  # bind the year parameter
        )

        return {  # build the response dict
            "statusCode": 200,  # HTTP 200 OK
            "count": len(rows) if rows else 0,  # total records for the year
            "data": rows if rows else [],  # event rows or empty list
        }

    @staticmethod
    def get_current_month() -> dict:
        """
        Retrieves all calendar events for the current calendar month, ordered by date ascending.

        Parameters:
            None

        Returns:
            dict with statusCode, count, year, month, and data list.
        """
        today = date.today()  # get today's date to determine current year and month

        rows = fetch_query(  # run the month-scoped SELECT
            """SELECT id, date, name, blocks_leave, period, created_by, created_at
               FROM calendar_events
               WHERE YEAR(date) = %s AND MONTH(date) = %s
               ORDER BY date ASC""",
            [today.year, today.month]  # bind current year and month
        )

        return {  # build the response dict
            "statusCode": 200,  # HTTP 200 OK
            "year": today.year,  # include resolved year for client convenience
            "month": today.month,  # include resolved month for client convenience
            "count": len(rows) if rows else 0,  # total events this month
            "data": rows if rows else [],  # event rows or empty list
        }

    @staticmethod
    def create(data: dict) -> dict:
        """
        Creates a new calendar event. Admin only (enforced at the handler level).

        Parameters:
            data (dict): Must contain: date (YYYY-MM-DD), name (str).
                         Optional: blocks_leave (0|1, default 0), period ('FULL'|'AM'|'PM', default 'FULL').

        Returns:
            dict with statusCode, message, and insertId on success.
        """
        event_date = data.get("date", "").strip()  # read and trim the date string
        name = data.get("name", "").strip()  # read and trim the event name

        if not event_date or not name:  # validate required fields
            return {"statusCode": 400, "message": "date and name are required"}  # reject missing fields

        blocks_leave = int(bool(data.get("blocks_leave", 0)))  # cast to 0 or 1, default 0
        period = data.get("period", "FULL").strip().upper()  # read period, default FULL

        if period not in ("FULL", "AM", "PM"):  # validate period value
            return {"statusCode": 400, "message": "period must be FULL, AM, or PM"}  # reject invalid value

        created_by = g.current_user.get("user_id")  # read the authenticated admin's user ID

        result = query_insert(  # execute the INSERT
            """INSERT INTO calendar_events (date, name, blocks_leave, period, created_by)
               VALUES (%s, %s, %s, %s, %s)""",
            [event_date, name, blocks_leave, period, created_by]  # bind all values
        )

        if result.get("statusCode") != 200:  # check for duplicate date or DB error
            return {"statusCode": 409, "message": "A calendar event already exists for this date"}  # conflict

        return {  # build success response
            "statusCode": 201,  # HTTP 201 Created
            "message": "Calendar event created successfully",  # confirmation message
            "id": result["insertId"],  # return the new record's ID
        }

    @staticmethod
    def update(event_id: int, data: dict) -> dict:
        """
        Updates an existing calendar event by ID. Admin only (enforced at the handler level).

        Parameters:
            event_id (int): The primary key of the event to update.
            data (dict): Any combination of: date, name, blocks_leave, period.

        Returns:
            dict with statusCode and message.
        """
        existing = fetch_query(  # check the event exists before attempting update
            "SELECT id FROM calendar_events WHERE id = %s",
            [event_id]
        )

        if not existing:  # event not found
            return {"statusCode": 404, "message": "Calendar event not found"}  # 404 not found

        fields = []  # collect SET clauses dynamically
        values = []  # collect bound values in matching order

        if "date" in data:  # only update date if provided
            fields.append("date = %s")  # add SET clause
            values.append(data["date"].strip())  # bind value

        if "name" in data:  # only update name if provided
            fields.append("name = %s")  # add SET clause
            values.append(data["name"].strip())  # bind value

        if "blocks_leave" in data:  # only update blocks_leave if provided
            fields.append("blocks_leave = %s")  # add SET clause
            values.append(int(bool(data["blocks_leave"])))  # cast to 0 or 1

        if "period" in data:  # only update period if provided
            period = data["period"].strip().upper()  # normalise to uppercase
            if period not in ("FULL", "AM", "PM"):  # validate against allowed values
                return {"statusCode": 400, "message": "period must be FULL, AM, or PM"}  # reject invalid value
            fields.append("period = %s")  # add SET clause
            values.append(period)  # bind normalised value

        if not fields:  # no updatable fields were provided
            return {"statusCode": 400, "message": "No fields provided to update"}  # reject empty body

        values.append(event_id)  # append event_id for the WHERE clause

        query(  # execute the UPDATE
            f"UPDATE calendar_events SET {', '.join(fields)} WHERE id = %s",
            values  # bind all values including the WHERE id
        )

        return {  # build success response
            "statusCode": 200,  # HTTP 200 OK
            "message": "Calendar event updated successfully",  # confirmation message
        }

    @staticmethod
    def delete(event_id: int) -> dict:
        """
        Deletes a calendar event by ID. Admin only (enforced at the handler level).

        Parameters:
            event_id (int): The primary key of the event to delete.

        Returns:
            dict with statusCode and message.
        """
        existing = fetch_query(  # check the event exists before deleting
            "SELECT id FROM calendar_events WHERE id = %s",
            [event_id]
        )

        if not existing:  # event not found
            return {"statusCode": 404, "message": "Calendar event not found"}  # 404 not found

        query(  # execute the DELETE
            "DELETE FROM calendar_events WHERE id = %s",
            [event_id]  # bind the event ID
        )

        return {  # build success response
            "statusCode": 200,  # HTTP 200 OK
            "message": "Calendar event deleted successfully",  # confirmation message
        }
