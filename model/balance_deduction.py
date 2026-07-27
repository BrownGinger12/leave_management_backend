import uuid  # import uuid to generate unique deduction numbers
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots, get_next_sequence  # import gateway functions
from datetime import date as _today_date  # import date for application number year


class BalanceDeduction:
    """
    Model for manual leave balance deductions.
    Records are stored in manual_balance_deductions and always paired with a
    DEBIT entry in leave_credit_transactions (source_type = MANUAL_DEDUCTION).
    Soft-deleting a record reverses the DEBIT and recalculates the ledger.
    """

    # --------------------------
    # Generate deduction number
    # --------------------------

    @staticmethod
    def _generate_deduction_number() -> str:
        """
        Generates a unique deduction number in YY-NNNNNN format using the
        shared application_number_sequences table (seq_type = 'DEDUCT').

        Returns:
            str: Deduction number, e.g. '26-000001'.
        """
        year = _today_date.today().year  # current calendar year
        yy = str(year)[-2:]  # last two digits of the year
        seq = get_next_sequence(year, "DEDUCT")  # atomic per-year counter
        return f"{yy}-{seq:06d}"  # format as YY-NNNNNN

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
    # Create deduction
    # --------------------------

    @staticmethod
    def create(data: dict) -> dict:
        """
        Creates a manual balance adjustment (DEBIT or CREDIT) for VL or SL of a NON_TEACHING employee.
        Inserts a record in manual_balance_deductions, posts the corresponding transaction to the
        leave_credit_transactions ledger, and recalculates all balance snapshots.

        Parameters:
            data (dict): Required — employee_id, leave_type_id, amount, deduction_date, transaction_type.
                         transaction_type must be 'DEBIT' (deduction) or 'CREDIT' (crediting).
                         Optional — remarks.

        Returns:
            dict: statusCode 201 with the created record, or an error dict.
        """
        try:
            employee_id      = data.get("employee_id")       # target employee
            leave_type_id    = data.get("leave_type_id")     # leave type to adjust (VL or SL only)
            amount           = data.get("amount")             # days to credit or deduct
            deduction_date   = data.get("deduction_date")    # effective date of the adjustment
            transaction_type = data.get("transaction_type")  # 'DEBIT' or 'CREDIT'

            if not employee_id:  # validate employee_id
                return {"statusCode": 400, "message": "employee_id is required"}
            if not leave_type_id:  # validate leave_type_id
                return {"statusCode": 400, "message": "leave_type_id is required"}
            if amount is None:  # validate amount is explicitly provided
                return {"statusCode": 400, "message": "amount is required"}
            if not deduction_date:  # validate deduction_date
                return {"statusCode": 400, "message": "deduction_date is required"}
            if not transaction_type:  # validate transaction_type is provided
                return {"statusCode": 400, "message": "transaction_type is required"}

            transaction_type = transaction_type.upper()  # normalise to uppercase
            if transaction_type not in ("DEBIT", "CREDIT"):  # only DEBIT and CREDIT are valid
                return {"statusCode": 400, "message": "transaction_type must be 'DEBIT' or 'CREDIT'"}

            try:
                amount = float(amount)  # coerce amount to float
            except (ValueError, TypeError):  # catch non-numeric input
                return {"statusCode": 400, "message": "amount must be numeric"}

            if amount <= 0:  # amount must be positive
                return {"statusCode": 400, "message": "amount must be greater than 0"}

            employee = fetch_query(  # verify employee exists, is active, and is NON_TEACHING
                "SELECT id, first_name, last_name, employee_number, employee_type FROM employees WHERE id = %s AND is_active = 1",
                [employee_id]
            )
            if not employee:  # employee not found or inactive
                return {"statusCode": 404, "message": "Employee not found or inactive"}
            if employee[0]["employee_type"] != "NON_TEACHING":  # only NON_TEACHING employees are eligible
                return {"statusCode": 400, "message": "Manual balance adjustments are only applicable to NON_TEACHING employees"}

            leave_type = fetch_query(  # verify leave type exists, is active, and is VL or SL
                "SELECT id, code, name, is_active FROM leave_types WHERE id = %s",
                [leave_type_id]
            )
            if not leave_type:  # leave type not found
                return {"statusCode": 404, "message": "Leave type not found"}
            if not leave_type[0]["is_active"]:  # leave type must be active
                return {"statusCode": 400, "message": "Leave type is inactive"}
            if leave_type[0]["code"] not in ("VL", "SL"):  # only VL and SL may be manually adjusted
                return {"statusCode": 400, "message": "Only Vacation Leave (VL) and Sick Leave (SL) can be manually adjusted"}

            current_balance_row = fetch_query(  # get current cached balance for before/after reporting
                "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                [employee_id, leave_type_id]
            )
            balance_before = float(current_balance_row[0]["balance"]) if current_balance_row else 0.0  # cast Decimal to float

            remarks = data.get("remarks", "").strip() if data.get("remarks") else None  # optional notes
            deduction_number = BalanceDeduction._generate_deduction_number()  # unique record number

            action_label = "deduction" if transaction_type == "DEBIT" else "credit"  # human-readable label for remarks and messages

            insert_result = query_insert(  # insert the adjustment record
                """INSERT INTO manual_balance_deductions
                       (deduction_number, employee_id, leave_type_id, transaction_type, amount, deduction_date, remarks)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [deduction_number, employee_id, leave_type_id, transaction_type, amount, deduction_date, remarks]
            )
            if insert_result.get("statusCode") != 200:  # check insert succeeded
                return {"statusCode": 500, "message": "Failed to create adjustment record"}

            deduction_id = insert_result["insertId"]  # primary key of the new record

            txn_result = query_insert(  # post the transaction to the leave_credit_transactions ledger
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, %s, %s, 'MANUAL_DEDUCTION', %s, %s, 0, %s)""",
                [
                    BalanceDeduction._generate_transaction_number(),  # unique transaction number
                    employee_id,                                       # employee being adjusted
                    leave_type_id,                                     # leave type being adjusted
                    transaction_type,                                  # DEBIT or CREDIT
                    amount,                                            # days adjusted
                    deduction_id,                                      # source record ID for audit trail
                    deduction_date,                                    # effective date
                    f"Manual {action_label} — {deduction_number}" + (f" | {remarks}" if remarks else ""),  # audit remarks
                ]
            )
            if txn_result.get("statusCode") != 200:  # check ledger insert succeeded
                return {"statusCode": 500, "message": "Failed to post transaction to ledger"}

            balance_after = recalculate_ledger_snapshots(employee_id, leave_type_id)  # cascade-update all snapshots

            rows = fetch_query(  # fetch the newly created record with employee and leave type info
                """SELECT d.*, e.first_name, e.last_name, e.employee_number,
                          lt.code AS leave_type_code, lt.name AS leave_type_name
                   FROM manual_balance_deductions d
                   JOIN employees e  ON e.id  = d.employee_id
                   JOIN leave_types lt ON lt.id = d.leave_type_id
                   WHERE d.id = %s""",
                [deduction_id]
            )

            row = rows[0] if rows else {}  # the created record

            return {  # return success response
                "statusCode": 201,  # 201 Created
                "message": f"{leave_type[0]['code']} {action_label} of {amount} day(s) applied successfully",  # confirmation message
                "balance_before": balance_before,  # balance before this adjustment
                "balance_after": balance_after,    # balance after recalculation
                "data": {**row, "amount": float(row["amount"])} if row else None,  # normalise Decimal to float
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # History (search + filter)
    # --------------------------

    @staticmethod
    def get_history(page: int = 1, limit: int = 10, query_str: str = None,
                    date_from: str = None, date_to: str = None,
                    year: int = None, employee_id: int = None,
                    leave_type_id: int = None) -> dict:
        """
        Returns a paginated, filterable history of manual balance deductions.
        All filters are optional and combinable.

        Parameters:
            page          (int): Page number (default 1).
            limit         (int): Records per page (default 10).
            query_str     (str): Keyword — matches employee first name, last name,
                                 employee number, or deduction number.
            date_from     (str): Earliest deduction_date to include (YYYY-MM-DD).
            date_to       (str): Latest deduction_date to include (YYYY-MM-DD).
            year          (int): Filter to a specific calendar year of deduction_date.
                                 Ignored when date_from or date_to is provided.
            employee_id   (int): Filter to a specific employee.
            leave_type_id (int): Filter to a specific leave type.

        Returns:
            dict: statusCode 200 with paginated records and applied filters, or an error dict.
        """
        try:
            page  = max(page, 1)   # ensure page is at least 1
            limit = max(limit, 1)  # ensure limit is at least 1
            offset = (page - 1) * limit  # calculate row offset

            conditions = ["d.is_deleted = 0", "lt.code IN ('VL', 'SL')"]  # always exclude soft-deleted records and non-VL/SL leave types
            params = []  # bound parameter values

            if query_str and query_str.strip():  # keyword search across employee and deduction number fields
                like = f"%{query_str.strip()}%"  # wrap with wildcards for LIKE matching
                conditions.append(  # match on any of the searchable text fields
                    "(e.first_name LIKE %s OR e.last_name LIKE %s "
                    "OR e.employee_number LIKE %s OR d.deduction_number LIKE %s)"
                )
                params.extend([like, like, like, like])  # four bindings for the four LIKE clauses

            if employee_id is not None:  # restrict to a specific employee
                conditions.append("d.employee_id = %s")
                params.append(employee_id)

            if leave_type_id is not None:  # restrict to a specific leave type
                conditions.append("d.leave_type_id = %s")
                params.append(leave_type_id)

            if date_from:  # lower bound on deduction_date
                conditions.append("d.deduction_date >= %s")
                params.append(date_from)

            if date_to:  # upper bound on deduction_date
                conditions.append("d.deduction_date <= %s")
                params.append(date_to)

            if year and not date_from and not date_to:  # year filter only when no explicit range is given
                conditions.append("YEAR(d.deduction_date) = %s")
                params.append(year)

            where = "WHERE " + " AND ".join(conditions)  # build the full WHERE clause

            total_row = fetch_query(  # count total matching records for pagination metadata
                f"""SELECT COUNT(*) AS total
                    FROM manual_balance_deductions d
                    JOIN employees e  ON e.id  = d.employee_id
                    JOIN leave_types lt ON lt.id = d.leave_type_id
                    {where}""",
                params
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated records with joined employee and leave type info
                f"""SELECT d.*, e.first_name, e.last_name, e.employee_number,
                           lt.code AS leave_type_code, lt.name AS leave_type_name
                    FROM manual_balance_deductions d
                    JOIN employees e  ON e.id  = d.employee_id
                    JOIN leave_types lt ON lt.id = d.leave_type_id
                    {where}
                    ORDER BY d.deduction_date DESC, d.id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]
            )

            total_pages = (total + limit - 1) // limit if total > 0 else 1  # ceiling division for total pages

            return {  # return paginated history response
                "statusCode": 200,
                "count": len(rows or []),  # records on this page
                "total": total,            # total matching records
                "page": page,              # current page
                "limit": limit,            # records per page
                "total_pages": total_pages,  # total number of pages
                "filters": {  # echo back applied filters so the frontend can reconstruct state
                    "query":         query_str or None,
                    "date_from":     date_from or None,
                    "date_to":       date_to or None,
                    "year":          year if (year and not date_from and not date_to) else None,
                    "employee_id":   employee_id,
                    "leave_type_id": leave_type_id,
                },
                "data": [{**r, "amount": float(r["amount"])} for r in (rows or [])],  # normalise Decimal to float
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get by ID
    # --------------------------

    @staticmethod
    def get_by_id(deduction_id: int) -> dict:
        """
        Retrieves a single manual balance deduction by primary key.

        Parameters:
            deduction_id (int): The record's primary key.

        Returns:
            dict: statusCode 200 with the deduction data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the record joined with employee and leave type info
                """SELECT d.*, e.first_name, e.last_name, e.employee_number,
                          lt.code AS leave_type_code, lt.name AS leave_type_name
                   FROM manual_balance_deductions d
                   JOIN employees e  ON e.id  = d.employee_id
                   JOIN leave_types lt ON lt.id = d.leave_type_id
                   WHERE d.id = %s AND d.is_deleted = 0""",
                [deduction_id]
            )
            if not rows:  # record not found or already deleted
                return {"statusCode": 404, "message": "Deduction record not found"}

            row = rows[0]  # the matched record
            return {  # return the record
                "statusCode": 200,
                "data": {**row, "amount": float(row["amount"])},  # normalise Decimal to float
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get paginated list
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10, employee_id: int = None) -> dict:
        """
        Retrieves a paginated list of manual balance deductions ordered by deduction_date descending.
        Optionally filters by employee_id.

        Parameters:
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).
            employee_id (int): Optional — filter to a specific employee.

        Returns:
            dict: statusCode 200 with paginated records.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            conditions = ["d.is_deleted = 0", "lt.code IN ('VL', 'SL')"]  # always exclude soft-deleted records and non-VL/SL leave types
            params = []  # bound parameter values

            if employee_id is not None:  # filter by employee when provided
                conditions.append("d.employee_id = %s")  # add employee condition
                params.append(employee_id)  # bind employee_id

            where = "WHERE " + " AND ".join(conditions)  # build WHERE clause

            total_row = fetch_query(  # count matching records
                f"""SELECT COUNT(*) AS total
                    FROM manual_balance_deductions d
                    JOIN employees e  ON e.id  = d.employee_id
                    JOIN leave_types lt ON lt.id = d.leave_type_id
                    {where}""",
                params
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated records with joined info
                f"""SELECT d.*, e.first_name, e.last_name, e.employee_number,
                           lt.code AS leave_type_code, lt.name AS leave_type_name
                    FROM manual_balance_deductions d
                    JOIN employees e  ON e.id  = d.employee_id
                    JOIN leave_types lt ON lt.id = d.leave_type_id
                    {where}
                    ORDER BY d.deduction_date DESC, d.id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]
            )

            data = [{**r, "amount": float(r["amount"])} for r in (rows or [])]  # normalise Decimal to float for each row

            return {  # return paginated response
                "statusCode": 200,
                "count": len(data),      # records in this page
                "total": total,          # total non-deleted deductions
                "page": page,            # current page number
                "limit": limit,          # records per page
                "data": data,            # normalised records
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Soft delete (reverses DEBIT)
    # --------------------------

    @staticmethod
    def soft_delete(deduction_id: int) -> dict:
        """
        Soft-deletes a manual balance deduction and reverses the DEBIT ledger entry.
        Sets is_deleted = 1, removes the MANUAL_DEDUCTION DEBIT from leave_credit_transactions,
        and recalculates all balance snapshots for the affected employee and leave type.

        Parameters:
            deduction_id (int): Primary key of the deduction to delete.

        Returns:
            dict: statusCode 200 on success, or an error dict.
        """
        try:
            rows = fetch_query(  # fetch the record regardless of is_deleted to distinguish not-found vs already-deleted
                "SELECT * FROM manual_balance_deductions WHERE id = %s",
                [deduction_id]
            )
            if not rows:  # record does not exist at all
                return {"statusCode": 404, "message": "Deduction not found"}

            rec = rows[0]  # the target record
            if rec["is_deleted"]:  # already soft-deleted
                return {"statusCode": 409, "message": "Deduction has already been deleted"}

            employee_id   = rec["employee_id"]    # employee whose balance must be restored
            leave_type_id = rec["leave_type_id"]  # leave type to recalculate

            query(  # remove the DEBIT ledger entry to restore the balance
                """DELETE FROM leave_credit_transactions
                   WHERE source_type = 'MANUAL_DEDUCTION'
                     AND source_id = %s
                     AND transaction_type = 'DEBIT'""",
                [deduction_id]
            )

            query(  # mark the deduction record as deleted
                "UPDATE manual_balance_deductions SET is_deleted = 1 WHERE id = %s",
                [deduction_id]
            )

            balance_after = recalculate_ledger_snapshots(employee_id, leave_type_id)  # cascade-update snapshots after removing DEBIT

            return {  # return success
                "statusCode": 200,
                "message": "Deduction deleted and balance restored",
                "balance_after": balance_after,  # restored balance for confirmation
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}
