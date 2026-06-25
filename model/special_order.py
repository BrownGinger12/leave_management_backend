from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query_insert  # import gateway functions
from datetime import date  # import date for date format validation


class SpecialOrder(BaseModel):
    """
    Pydantic model representing a Special Order record.
    Special Orders authorize CTO and VSC service credits for hours rendered.

    Attributes:
        special_order: The Special Order number or code (e.g. SO-2026-001).
        activity_name: Name or description of the activity covered by this SO.
        reference: Reference document identifier (optional).
        date_of_activity: Date the activity took place (YYYY-MM-DD).
    """
    special_order: str  # SO number or code
    activity_name: str  # name or description of the activity
    reference: Optional[str] = None  # optional reference document identifier
    date_of_activity: str  # date the activity took place (YYYY-MM-DD)

    # --------------------------
    # Create special order
    # --------------------------

    @staticmethod
    def create(data: dict) -> dict:
        """
        Creates a new Special Order record.
        Returns 409 if a Special Order with the same number already exists.

        Parameters:
            data (dict): Fields — special_order, activity_name, date_of_activity,
                         reference (optional).

        Returns:
            dict: statusCode 201 with the created record, or an error dict.
        """
        try:
            required_fields = ["special_order", "activity_name", "date_of_activity"]  # fields that must be present

            for field in required_fields:  # loop through required fields
                if not data.get(field):  # check if field is missing or empty
                    return {"statusCode": 400, "message": f"{field} is required"}  # return 400 if missing

            try:  # validate date_of_activity format before hitting the database
                date.fromisoformat(data["date_of_activity"])  # attempt to parse the date string
            except ValueError:  # catch invalid format
                return {"statusCode": 400, "message": "Invalid date_of_activity format. Expected YYYY-MM-DD"}  # return 400

            existing = fetch_query(  # check if a Special Order with the same number already exists
                "SELECT id FROM special_orders WHERE special_order = %s",
                [data["special_order"]]
            )

            if existing:  # duplicate SO number found
                return {  # return 409 Conflict
                    "statusCode": 409,
                    "message": f"Special Order '{data['special_order']}' already exists",
                }

            result = query_insert(  # insert the new Special Order record
                """INSERT INTO special_orders
                       (special_order, activity_name, reference, date_of_activity)
                   VALUES (%s, %s, %s, %s)""",
                [
                    data["special_order"],       # the SO number or code
                    data["activity_name"],        # name of the activity
                    data.get("reference"),        # optional reference document identifier
                    data["date_of_activity"],     # date the activity took place
                ]
            )

            if result["statusCode"] != 200:  # check if insert failed
                return result  # return the error from the gateway

            rows = fetch_query(  # fetch the full created record
                "SELECT * FROM special_orders WHERE id = %s",
                [result["insertId"]]
            )

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": "Special Order created successfully",  # confirmation message
                "data": rows[0] if rows else None,  # the created Special Order record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get special order by ID
    # --------------------------

    @staticmethod
    def get_by_id(special_order_id: int) -> dict:
        """
        Retrieves a single Special Order by its primary key.

        Parameters:
            special_order_id (int): The Special Order's primary key.

        Returns:
            dict: statusCode 200 with the record, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the Special Order by ID
                "SELECT * FROM special_orders WHERE id = %s",
                [special_order_id]
            )

            return {  # return found record
                "statusCode": 200,
                "data": rows[0],
            } if rows else {  # return 404 if not found
                "statusCode": 404,
                "message": f"Special Order {special_order_id} not found",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Search special orders
    # --------------------------

    @staticmethod
    def search(query: str, page: int = 1, limit: int = 10) -> dict:
        """
        Searches Special Orders by special_order number or activity_name using a partial match.
        Results are paginated and ordered by date_of_activity descending.

        Parameters:
            query (str): The search keyword to match against special_order and activity_name.
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated matching Special Orders, or 400 if query is missing.
        """
        try:
            if not query or not query.strip():  # query must not be empty
                return {"statusCode": 400, "message": "query is required"}  # return 400 if blank

            keyword = f"%{query.strip()}%"  # wrap keyword in wildcards for partial LIKE match

            total_row = fetch_query(  # get total matching count for pagination metadata
                """SELECT COUNT(*) AS total FROM special_orders
                   WHERE special_order LIKE %s OR activity_name LIKE %s""",
                [keyword, keyword]
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            offset = (page - 1) * limit  # calculate row offset for the requested page

            rows = fetch_query(  # fetch paginated matching Special Orders
                """SELECT * FROM special_orders
                   WHERE special_order LIKE %s OR activity_name LIKE %s
                   ORDER BY date_of_activity DESC, id DESC
                   LIMIT %s OFFSET %s""",
                [keyword, keyword, limit, offset]
            )

            return {  # return paginated search results
                "statusCode": 200,  # success code
                "query": query.strip(),  # echo back the search keyword
                "count": len(rows),  # number of records in this page
                "total": total,  # total matching records across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": rows if rows else [],  # list of matching Special Orders
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Filter special orders by year / date range
    # --------------------------

    @staticmethod
    def filter(filters: dict, page: int = 1, limit: int = 10) -> dict:
        """
        Filters Special Orders by optional year and/or date range on date_of_activity.
        All filters are optional and combinable. Results are paginated and ordered
        by date_of_activity descending.

        Parameters:
            filters (dict): Optional keys — year (int), date_from (str YYYY-MM-DD),
                            date_to (str YYYY-MM-DD).
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated results and applied filters, or an error dict.
        """
        try:
            conditions = []  # list of WHERE clause fragments
            params = []  # bound parameter values matching each placeholder

            if filters.get("year"):  # filter by calendar year of date_of_activity
                conditions.append("YEAR(date_of_activity) = %s")  # add year condition
                params.append(filters["year"])  # bind year value

            if filters.get("date_from"):  # filter by lower bound of date_of_activity
                conditions.append("date_of_activity >= %s")  # add date_from condition
                params.append(filters["date_from"])  # bind date_from value

            if filters.get("date_to"):  # filter by upper bound of date_of_activity
                conditions.append("date_of_activity <= %s")  # add date_to condition
                params.append(filters["date_to"])  # bind date_to value

            where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""  # assemble WHERE or empty string

            total_row = fetch_query(  # get total matching count for pagination metadata
                f"SELECT COUNT(*) AS total FROM special_orders {where_clause}",
                params  # bind filter params only
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            offset = (page - 1) * limit  # calculate row offset for the requested page

            rows = fetch_query(  # fetch paginated filtered Special Orders
                f"""SELECT * FROM special_orders
                    {where_clause}
                    ORDER BY date_of_activity DESC, id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]  # filter params followed by LIMIT and OFFSET
            )

            active_filters = {k: v for k, v in filters.items() if v is not None}  # strip None values

            return {  # return paginated filter results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total matching records across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "filters": active_filters,  # echo back applied filters
                "data": rows if rows else [],  # list of matching Special Orders
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get all special orders (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all Special Orders, ordered by date_of_activity descending.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated Special Order data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get total count for pagination metadata
                "SELECT COUNT(*) AS total FROM special_orders", []
            )

            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated Special Orders
                """SELECT * FROM special_orders
                   ORDER BY date_of_activity DESC, id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            return {  # return paginated results
                "statusCode": 200,  # success code
                "count": len(rows),  # number of records in this page
                "total": total,  # total Special Orders across all pages
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": rows if rows else [],  # list of Special Orders
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
