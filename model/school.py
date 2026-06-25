from gateway.mysql_gateway import fetch_query  # import gateway functions


class School:
    """
    Model for the schools reference table.
    Provides read-only access to the list of schools in the division.
    """

    # --------------------------
    # Get all schools
    # --------------------------

    @staticmethod
    def get_all() -> dict:
        """
        Retrieves all schools in the division ordered alphabetically by name.

        Returns:
            dict: statusCode 200 with the list of school records.
        """
        try:
            rows = fetch_query(  # fetch all schools ordered alphabetically
                "SELECT id, name FROM schools ORDER BY name ASC", []
            )

            return {  # return success response
                "statusCode": 200,  # success code
                "count": len(rows) if rows else 0,  # number of schools returned
                "data": rows if rows else [],  # list of school records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
