import uuid  # import uuid to generate unique application numbers
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions


class UndertimeTardiness:

    # --------------------------
    # Generate application number
    # --------------------------

    @staticmethod
    def _generate_application_number() -> str:
        """
        Generates a unique undertime/tardiness deduction number using a UUID-based suffix.

        Returns:
            str: An application number in the format 'UTD-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"UTD-{suffix}"  # format as UTD-XXXXXXXX

    # --------------------------
    # Generate transaction number
    # --------------------------

    @staticmethod
    def _generate_transaction_number() -> str:
        """
        Generates a unique ledger transaction number using a UUID-based suffix.

        Returns:
            str: A transaction number in the format 'TXN-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"TXN-{suffix}"  # format as TXN-XXXXXXXX

    # --------------------------
    # Normalise a raw DB row
    # --------------------------

    @staticmethod
    def _normalise(row: dict) -> dict:
        """
        Casts DECIMAL fields to float so they serialise cleanly to JSON.

        Parameters:
            row (dict): Raw row from fetch_query.

        Returns:
            dict: Same row with numeric fields cast to float.
        """
        return {  # return a copy with decimal fields cast to float
            **row,
            "undertime_points": float(row["undertime_points"]),  # cast DECIMAL to float
            "tardiness_points": float(row["tardiness_points"]),  # cast DECIMAL to float
            "total_points": float(row["total_points"]),  # cast DECIMAL to float
            "vl_deducted": float(row["vl_deducted"]),  # cast DECIMAL to float
        }

    # --------------------------
    # Create deduction
    # --------------------------

    @staticmethod
    def create(data: dict) -> dict:
        """
        Creates a new undertime/tardiness VL deduction for a NON_TEACHING employee.
        Validates the employee type, inserts the deduction record, posts a DEBIT to the
        VL ledger, and recalculates ledger snapshots.

        Parameters:
            data (dict): Required keys — employee_id, undertime_points, tardiness_points,
                         deduction_date. Optional — remarks.

        Returns:
            dict: statusCode 201 with the created record, or an error dict.
        """
        try:
            employee_id = data.get("employee_id")  # target employee
            undertime_points = data.get("undertime_points")  # undertime days accumulated
            tardiness_points = data.get("tardiness_points")  # tardiness days accumulated
            deduction_date = data.get("deduction_date")  # effective date of the deduction

            if not employee_id:  # validate required fields
                return {"statusCode": 400, "message": "employee_id is required"}
            if undertime_points is None:  # undertime must be explicitly provided
                return {"statusCode": 400, "message": "undertime_points is required"}
            if tardiness_points is None:  # tardiness must be explicitly provided
                return {"statusCode": 400, "message": "tardiness_points is required"}
            if not deduction_date:  # date is required
                return {"statusCode": 400, "message": "deduction_date is required"}

            try:
                undertime_points = float(undertime_points)  # coerce to float
                tardiness_points = float(tardiness_points)  # coerce to float
            except (ValueError, TypeError):  # catch non-numeric input
                return {"statusCode": 400, "message": "undertime_points and tardiness_points must be numeric"}

            if undertime_points < 0 or tardiness_points < 0:  # points cannot be negative
                return {"statusCode": 400, "message": "undertime_points and tardiness_points must be non-negative"}

            employee = fetch_query(  # verify the employee exists and is active
                "SELECT id, first_name, last_name, employee_number, employee_type FROM employees WHERE id = %s AND is_active = 1",
                [employee_id]
            )
            if not employee:  # employee not found or inactive
                return {"statusCode": 404, "message": "Employee not found or inactive"}

            if employee[0]["employee_type"] != "NON_TEACHING":  # enforce NON_TEACHING restriction
                return {"statusCode": 400, "message": "Undertime/tardiness deductions are only applicable to NON_TEACHING employees"}

            vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # look up VL leave type
            if not vl_type:  # VL type must exist in the system
                return {"statusCode": 500, "message": "VL leave type not found in the system"}
            vl_type_id = vl_type[0]["id"]  # VL leave type primary key

            total_points = round(undertime_points + tardiness_points, 4)  # total days to deduct
            remarks = data.get("remarks", "").strip() if data.get("remarks") else None  # optional notes
            application_number = UndertimeTardiness._generate_application_number()  # unique UTD number

            insert_result = query_insert(  # insert the deduction record
                """INSERT INTO undertime_tardiness_deductions
                       (application_number, employee_id, undertime_points, tardiness_points,
                        total_points, vl_deducted, deduction_date, remarks)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [application_number, employee_id, undertime_points, tardiness_points,
                 total_points, total_points, deduction_date, remarks]
            )
            if insert_result.get("statusCode") != 200:  # check insert succeeded
                return {"statusCode": 500, "message": "Failed to create deduction record"}

            deduction_id = insert_result["insertId"]  # primary key of the new record

            txn_result = query_insert(  # post DEBIT to VL ledger
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'DEBIT', %s, 'UNDERTIME_TARDINESS', %s, %s, 0, %s)""",
                [
                    UndertimeTardiness._generate_transaction_number(),  # unique transaction number
                    employee_id,          # employee being debited
                    vl_type_id,           # VL leave type
                    total_points,         # days deducted
                    deduction_id,         # source record ID for audit trail
                    deduction_date,       # effective date
                    f"Undertime/tardiness deduction — {application_number}",  # audit remarks
                ]
            )
            if txn_result.get("statusCode") != 200:  # check ledger insert succeeded
                return {"statusCode": 500, "message": "Failed to post VL debit to ledger"}

            recalculate_ledger_snapshots(employee_id, vl_type_id)  # cascade-update all VL balance snapshots

            rows = fetch_query(  # fetch the newly created record for the response
                """SELECT utd.*, e.first_name, e.last_name, e.employee_number
                   FROM undertime_tardiness_deductions utd
                   JOIN employees e ON e.id = utd.employee_id
                   WHERE utd.id = %s""",
                [deduction_id]
            )
            return {  # return the created record
                "statusCode": 201,  # created
                "message": "Undertime/tardiness deduction created and VL balance updated",
                "data": UndertimeTardiness._normalise(rows[0]),  # normalised record
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get by ID
    # --------------------------

    @staticmethod
    def get_by_id(deduction_id: int) -> dict:
        """
        Retrieves a single undertime/tardiness deduction by primary key.

        Parameters:
            deduction_id (int): The record's primary key.

        Returns:
            dict: statusCode 200 with the deduction data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the record joined with employee info
                """SELECT utd.*, e.first_name, e.last_name, e.employee_number
                   FROM undertime_tardiness_deductions utd
                   JOIN employees e ON e.id = utd.employee_id
                   WHERE utd.id = %s AND utd.is_deleted = 0""",
                [deduction_id]
            )
            if not rows:  # record not found or already deleted
                return {"statusCode": 404, "message": "Deduction record not found"}

            return {"statusCode": 200, "data": UndertimeTardiness._normalise(rows[0])}  # return normalised record

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get paginated list
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all non-deleted undertime/tardiness deductions,
        ordered by deduction_date descending.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated deduction records.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # count non-deleted records
                "SELECT COUNT(*) AS total FROM undertime_tardiness_deductions WHERE is_deleted = 0",
                []
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated records joined with employee info
                """SELECT utd.*, e.first_name, e.last_name, e.employee_number
                   FROM undertime_tardiness_deductions utd
                   JOIN employees e ON e.id = utd.employee_id
                   WHERE utd.is_deleted = 0
                   ORDER BY utd.deduction_date DESC, utd.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            return {  # return paginated response
                "statusCode": 200,  # success code
                "count": len(rows or []),  # records in this page
                "total": total,  # total non-deleted deductions
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": [UndertimeTardiness._normalise(r) for r in (rows or [])],  # normalised records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Search by application number or employee
    # --------------------------

    @staticmethod
    def search(query_str: str, page: int = 1, limit: int = 10) -> dict:
        """
        Searches undertime/tardiness deductions by application number, employee name, or employee number.

        Parameters:
            query_str (str): The search keyword.
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with matching records, or 404 if none found.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for pagination
            like = f"%{query_str}%"  # wrap search term with wildcards for LIKE matching

            total_row = fetch_query(  # count matching non-deleted records
                """SELECT COUNT(*) AS total
                   FROM undertime_tardiness_deductions utd
                   JOIN employees e ON e.id = utd.employee_id
                   WHERE utd.is_deleted = 0
                     AND (utd.application_number LIKE %s
                          OR e.first_name LIKE %s OR e.last_name LIKE %s
                          OR e.employee_number LIKE %s)""",
                [like, like, like, like]
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch matching records
                """SELECT utd.*, e.first_name, e.last_name, e.employee_number
                   FROM undertime_tardiness_deductions utd
                   JOIN employees e ON e.id = utd.employee_id
                   WHERE utd.is_deleted = 0
                     AND (utd.application_number LIKE %s
                          OR e.first_name LIKE %s OR e.last_name LIKE %s
                          OR e.employee_number LIKE %s)
                   ORDER BY utd.deduction_date DESC, utd.id DESC
                   LIMIT %s OFFSET %s""",
                [like, like, like, like, limit, offset]
            )

            if not rows:  # no matching records
                return {"statusCode": 404, "message": "No records found matching the query"}

            return {  # return matching records
                "statusCode": 200,  # success code
                "count": len(rows),  # records in this page
                "total": total,  # total matching records
                "page": page,  # current page number
                "limit": limit,  # records per page
                "data": [UndertimeTardiness._normalise(r) for r in rows],  # normalised records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Filter by date range / year / employee
    # --------------------------

    @staticmethod
    def filter(filters: dict, page: int = 1, limit: int = 10) -> dict:
        """
        Filters undertime/tardiness deductions using optional criteria.
        Supported filters: year, date_from, date_to, employee_id.
        All filters are optional and combinable.

        Parameters:
            filters (dict): Optional keys — year, date_from, date_to, employee_id.
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated matching records.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            conditions = ["utd.is_deleted = 0"]  # always exclude soft-deleted records
            params = []  # bound parameter values

            if filters.get("year"):  # filter by calendar year of deduction_date
                conditions.append("YEAR(utd.deduction_date) = %s")
                params.append(filters["year"])

            if filters.get("date_from"):  # lower bound of deduction_date range
                conditions.append("utd.deduction_date >= %s")
                params.append(filters["date_from"])

            if filters.get("date_to"):  # upper bound of deduction_date range
                conditions.append("utd.deduction_date <= %s")
                params.append(filters["date_to"])

            if filters.get("employee_id"):  # filter by specific employee
                conditions.append("utd.employee_id = %s")
                params.append(filters["employee_id"])

            where_clause = "WHERE " + " AND ".join(conditions)  # build WHERE clause from conditions

            total_row = fetch_query(  # count matching records for pagination metadata
                f"""SELECT COUNT(*) AS total
                    FROM undertime_tardiness_deductions utd
                    JOIN employees e ON e.id = utd.employee_id
                    {where_clause}""",
                params
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated matching records
                f"""SELECT utd.*, e.first_name, e.last_name, e.employee_number
                    FROM undertime_tardiness_deductions utd
                    JOIN employees e ON e.id = utd.employee_id
                    {where_clause}
                    ORDER BY utd.deduction_date DESC, utd.id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]
            )

            return {  # return filtered results
                "statusCode": 200,  # success code
                "count": len(rows or []),  # records in this page
                "total": total,  # total matching records
                "page": page,  # current page number
                "limit": limit,  # records per page
                "filters": {k: v for k, v in filters.items() if v is not None},  # applied filters for context
                "data": [UndertimeTardiness._normalise(r) for r in (rows or [])],  # normalised records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Soft delete (reverses VL debit)
    # --------------------------

    @staticmethod
    def soft_delete(deduction_id: int) -> dict:
        """
        Soft-deletes an undertime/tardiness deduction and reverses the VL ledger entry.
        Sets is_deleted = 1 on the record, removes the corresponding DEBIT from
        leave_credit_transactions, and recalculates VL balance snapshots.

        Parameters:
            deduction_id (int): Primary key of the deduction to delete.

        Returns:
            dict: statusCode 200 on success, or an error dict.
        """
        try:
            rows = fetch_query(  # fetch the record regardless of is_deleted to distinguish not-found vs already-deleted
                "SELECT * FROM undertime_tardiness_deductions WHERE id = %s",
                [deduction_id]
            )
            if not rows:  # record does not exist
                return {"statusCode": 404, "message": "Deduction not found"}

            rec = rows[0]  # the target record
            if rec["is_deleted"]:  # already soft-deleted
                return {"statusCode": 409, "message": "Deduction has already been deleted"}

            employee_id = rec["employee_id"]  # employee whose VL must be restored

            vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # look up VL type for recalculation
            if not vl_type:  # VL type must exist
                return {"statusCode": 500, "message": "VL leave type not found"}
            vl_type_id = vl_type[0]["id"]  # VL leave type primary key

            query(  # remove the DEBIT ledger entry to restore the VL balance
                """DELETE FROM leave_credit_transactions
                   WHERE source_type = 'UNDERTIME_TARDINESS'
                     AND source_id = %s
                     AND transaction_type = 'DEBIT'""",
                [deduction_id]
            )

            query(  # mark the deduction record as deleted
                "UPDATE undertime_tardiness_deductions SET is_deleted = 1 WHERE id = %s",
                [deduction_id]
            )

            recalculate_ledger_snapshots(employee_id, vl_type_id)  # cascade-update VL snapshots after removing DEBIT

            return {  # return success
                "statusCode": 200,
                "message": "Deduction deleted and VL balance restored",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}
