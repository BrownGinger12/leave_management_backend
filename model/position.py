from gateway.mysql_gateway import fetch_query  # import fetch_query helper for SELECT operations
from flask import request  # import request to read query parameters


class Position:
    """Model for retrieving positions (Teaching / Non-Teaching reference data)."""

    @staticmethod
    def get_all() -> dict:
        """
        Retrieves all positions from the positions table.

        Supports an optional 'type' query parameter to filter by TEACHING or NON_TEACHING.
        Results are ordered alphabetically within each type.

        Parameters:
            None (reads request.args internally for the optional 'type' filter)

        Returns:
            dict with keys:
                statusCode (int): 200 on success.
                count (int): number of records returned.
                data (list[dict]): list of position records with id, name, and type.
        """
        position_type = request.args.get("type", "").strip().upper()  # read optional type filter from query string

        if position_type in ("TEACHING", "NON_TEACHING"):  # if a valid type is supplied, apply the filter
            rows = fetch_query(  # execute filtered query
                "SELECT id, name, type FROM positions WHERE type = %s ORDER BY name ASC",
                [position_type]  # bind the type parameter
            )
        else:  # no filter — return all positions
            rows = fetch_query(  # execute unfiltered query returning all rows
                "SELECT id, name, type FROM positions ORDER BY type ASC, name ASC",
                []
            )

        return {  # build and return the response dict
            "statusCode": 200,  # HTTP 200 OK
            "count": len(rows) if rows else 0,  # total records returned
            "data": rows if rows else [],  # position rows or empty list on no data
        }
