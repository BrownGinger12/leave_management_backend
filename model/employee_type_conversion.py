from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
import uuid  # import uuid for unique number generation


class EmployeeTypeConversion(BaseModel):
    """
    Pydantic model representing a personnel type conversion record.
    Handles converting an employee between TEACHING and NON_TEACHING,
    applying the DepEd leave credit conversion formula and posting all
    ledger debits and credits atomically.

    Attributes:
        employee_id: FK to the employee being converted.
        conversion_date: Effective date of the conversion.
        remarks: Optional notes about the conversion.
        created_by: FK to users.id (the admin who triggered the conversion).
    """
    employee_id: int  # FK to employees table
    conversion_date: str  # effective date of conversion (YYYY-MM-DD)
    remarks: Optional[str] = None  # optional notes
    created_by: Optional[int] = None  # FK to users.id

    # --------------------------
    # Generate unique numbers
    # --------------------------

    @staticmethod
    def _generate_conversion_number() -> str:
        """
        Generates a unique conversion number using a UUID-based suffix.

        Returns:
            str: A conversion number in the format 'ETC-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"ETC-{suffix}"  # format as ETC-XXXXXXXX

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
    # Convert employee type
    # --------------------------

    @staticmethod
    def convert(employee_id: int, data: dict) -> dict:
        """
        Converts an employee's type between TEACHING and NON_TEACHING using
        the DepEd leave credit conversion formula, posting all necessary
        ledger transactions and updating the balance cache.

        TEACHING → NON_TEACHING:
            total_credits = (30 × vsc_balance) / 69
            vl_credits = sl_credits = total_credits / 2

        NON_TEACHING → TEACHING:
            vsc_credits = ((vl_balance + sl_balance) / 30) × 69

        Conversion is idempotent per employee per date — duplicate requests
        for the same employee_id + conversion_date are rejected with 409.

        Parameters:
            employee_id (int): The primary key of the employee to convert.
            data (dict): Must include conversion_date (YYYY-MM-DD);
                         may include remarks (str) and created_by (int).

        Returns:
            dict: statusCode 200 with conversion details on success,
                  or an error dict with the appropriate statusCode.
        """
        try:
            conversion_date = data.get("conversion_date")  # get effective date from payload
            if not conversion_date:  # conversion_date is mandatory
                return {"statusCode": 400, "message": "conversion_date is required"}  # reject if missing

            remarks = data.get("remarks")  # optional notes
            created_by = data.get("created_by")  # optional user reference

            # --- Verify employee exists and is active ---
            emp = fetch_query(  # fetch the employee record
                "SELECT id, first_name, last_name, employee_number, employee_type FROM employees WHERE id = %s AND is_active = 1",
                [employee_id]
            )
            if not emp:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            employee = emp[0]  # get the first (and only) result
            current_type = employee["employee_type"]  # TEACHING or NON_TEACHING
            new_type = "NON_TEACHING" if current_type == "TEACHING" else "TEACHING"  # determine target type

            # --- Idempotency check: one conversion per employee per date per direction ---
            existing = fetch_query(  # check if the same direction was already converted on this date
                """SELECT id FROM employee_type_conversions
                   WHERE employee_id = %s AND conversion_date = %s
                     AND from_type = %s AND to_type = %s""",
                [employee_id, conversion_date, current_type, new_type]
            )
            if existing:  # duplicate conversion in the same direction detected
                return {  # return 409 Conflict
                    "statusCode": 409,
                    "message": f"A {current_type} to {new_type} conversion already exists for this employee on {conversion_date}",
                }

            # --- Fetch VL, SL, and VSC leave type IDs ---
            vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL' AND is_active = 1", [])  # get VL type
            sl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'SL' AND is_active = 1", [])  # get SL type
            vsc_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VSC' AND is_active = 1", [])  # get VSC type

            if not vl_type or not sl_type or not vsc_type:  # all three leave types must exist
                return {"statusCode": 500, "message": "Required leave types VL, SL, and VSC must all exist and be active"}  # reject if missing

            vl_type_id = vl_type[0]["id"]  # VL leave type primary key
            sl_type_id = sl_type[0]["id"]  # SL leave type primary key
            vsc_type_id = vsc_type[0]["id"]  # VSC leave type primary key

            def get_balance(lt_id):
                """
                Reads the current cached balance for the given leave type.

                Parameters:
                    lt_id (int): The leave type primary key.

                Returns:
                    float: Current balance (0.0 if no record exists).
                """
                rows = fetch_query(  # read from the balance cache
                    "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                    [employee_id, lt_id]
                )
                return float(rows[0]["balance"]) if rows else 0.0  # cast Decimal to float; default to 0

            def post_ledger(lt_id, txn_type, amount, conv_id, label, src_type="TYPE_CONVERSION"):
                """
                Inserts one CREDIT or DEBIT ledger row linked to the conversion record.

                Parameters:
                    lt_id (int): Leave type primary key.
                    txn_type (str): 'CREDIT' or 'DEBIT'.
                    amount (float): Number of days.
                    conv_id (int): Primary key of the employee_type_conversions record.
                    label (str): Remarks string for the ledger row.
                    src_type (str): source_type value; defaults to 'TYPE_CONVERSION'.

                Returns:
                    dict: statusCode 200 with insertId, or error dict.
                """
                return query_insert(  # insert ledger row
                    f"""INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, %s, %s, '{src_type}', %s, %s, 0, %s)""",
                    [
                        EmployeeTypeConversion._generate_transaction_number(),  # unique transaction number
                        employee_id,     # employee being converted
                        lt_id,           # leave type affected
                        txn_type,        # CREDIT or DEBIT
                        amount,          # days affected
                        conv_id,         # FK to the conversion audit record
                        conversion_date,  # effective date
                        label,           # remarks explaining this ledger row
                    ]
                )

            conversion_number = EmployeeTypeConversion._generate_conversion_number()  # unique conversion number

            if current_type == "TEACHING":
                # ============================================================
                # TEACHING → NON_TEACHING
                # Formula: total = (30 × vsc) / 69;  vl = sl = total / 2
                # ============================================================
                system_vsc = get_balance(vsc_type_id)  # read current VSC balance from the ledger cache
                override_vsc = data.get("vsc_balance_override")  # optional manual override for employees with no system VSC history

                if override_vsc is not None:  # admin supplied an override — validate and use it
                    try:
                        override_vsc = float(override_vsc)  # cast to float
                    except (TypeError, ValueError):  # invalid type provided
                        return {"statusCode": 400, "message": "vsc_balance_override must be a number"}  # reject
                    if override_vsc < 0:  # override cannot be negative
                        return {"statusCode": 400, "message": "vsc_balance_override cannot be negative"}  # reject
                    vsc_balance = override_vsc  # use the admin-supplied figure
                else:
                    vsc_balance = system_vsc  # use the system-computed VSC balance

                if vsc_balance < 0:  # negative balance would produce invalid credits
                    return {"statusCode": 400, "message": "VSC balance is negative; cannot convert"}  # reject

                total_credits = round((30 * vsc_balance) / 69, 4)  # apply DepEd conversion formula
                vl_credits = round(total_credits / 2, 4)  # split equally to VL
                sl_credits = round(total_credits / 2, 4)  # split equally to SL

                # --- Insert the conversion audit record first so ledger rows can reference it ---
                conv_result = query_insert(  # insert conversion record
                    """INSERT INTO employee_type_conversions
                           (conversion_number, employee_id, from_type, to_type, conversion_date,
                            vsc_balance_before, total_credits_converted, vl_balance_after, sl_balance_after,
                            vl_balance_before, sl_balance_before, vsc_balance_after, remarks, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, 0, %s, %s)""",
                    [
                        conversion_number,  # unique reference number
                        employee_id,        # employee being converted
                        current_type,       # from TEACHING
                        new_type,           # to NON_TEACHING
                        conversion_date,    # effective date
                        vsc_balance,        # VSC balance that was converted
                        total_credits,      # total VL+SL credits produced
                        vl_credits,         # VL credits assigned
                        sl_credits,         # SL credits assigned
                        remarks,            # optional notes
                        created_by,         # user who triggered the conversion
                    ]
                )
                if conv_result["statusCode"] != 200:  # check if insert failed
                    return conv_result  # return error from gateway

                conv_id = conv_result["insertId"]  # capture conversion record ID for ledger FK

                # --- Post DEBIT on VSC to zero out the balance (only if balance > 0) ---
                if vsc_balance > 0:  # skip if already zero to avoid a zero-amount debit
                    r = post_ledger(vsc_type_id, "DEBIT", vsc_balance, conv_id,
                                    f"Type conversion {current_type}->{new_type}: VSC zeroed out")
                    if r["statusCode"] != 200:  # check if ledger insert failed
                        return r  # propagate error

                # --- Post CREDIT on VL as FORWARDED_BALANCE so it appears on the leave card ---
                if vl_credits > 0:  # skip if formula produces zero
                    r = post_ledger(vl_type_id, "CREDIT", vl_credits, conv_id,
                                    f"Type conversion {current_type}->{new_type}: VL initialized from VSC",
                                    src_type="FORWARDED_BALANCE")
                    if r["statusCode"] != 200:  # check if ledger insert failed
                        return r  # propagate error

                # --- Post CREDIT on SL as FORWARDED_BALANCE so it appears on the leave card ---
                if sl_credits > 0:  # skip if formula produces zero
                    r = post_ledger(sl_type_id, "CREDIT", sl_credits, conv_id,
                                    f"Type conversion {current_type}->{new_type}: SL initialized from VSC",
                                    src_type="FORWARDED_BALANCE")
                    if r["statusCode"] != 200:  # check if ledger insert failed
                        return r  # propagate error

                # --- Zero out VSC credit pool balances (old and new) ---
                query(  # set all remaining_balance to 0 for VSC old pool
                    "UPDATE vsc_old_credit_balances SET remaining_balance = 0 WHERE employee_id = %s",
                    [employee_id]
                )
                query(  # set all remaining_balance to 0 for VSC new pool
                    "UPDATE vsc_new_credit_balances SET remaining_balance = 0 WHERE employee_id = %s",
                    [employee_id]
                )

                # --- Recalculate ledger snapshots and update employee_leave_balances cache ---
                recalculate_ledger_snapshots(employee_id, vsc_type_id)  # re-run VSC running balance
                recalculate_ledger_snapshots(employee_id, vl_type_id)   # re-run VL running balance
                recalculate_ledger_snapshots(employee_id, sl_type_id)   # re-run SL running balance

                # --- Flip the employee_type on the employees record ---
                query(  # update the employee classification
                    "UPDATE employees SET employee_type = %s WHERE id = %s",
                    [new_type, employee_id]
                )

                return {  # return success with conversion summary
                    "statusCode": 200,  # success
                    "message": f"Employee converted from TEACHING to NON_TEACHING",  # confirmation
                    "conversion_number": conversion_number,  # audit reference
                    "from_type": current_type,              # original type
                    "to_type": new_type,                    # new type
                    "vsc_balance_before": vsc_balance,       # VSC that was zeroed
                    "total_credits_converted": total_credits,  # computed total credits
                    "vl_balance_after": vl_credits,          # VL assigned
                    "sl_balance_after": sl_credits,          # SL assigned
                }

            else:
                # ============================================================
                # NON_TEACHING → TEACHING
                # Formula: vsc = ((vl + sl) / 30) × 69
                # ============================================================
                vl_balance = get_balance(vl_type_id)  # read current VL balance
                sl_balance = get_balance(sl_type_id)  # read current SL balance

                if vl_balance < 0 or sl_balance < 0:  # negative balances would produce invalid VSC
                    return {"statusCode": 400, "message": "VL or SL balance is negative; cannot convert"}  # reject

                vsc_credits = round(((vl_balance + sl_balance) / 30) * 69, 4)  # apply DepEd conversion formula

                # --- Insert the conversion audit record first ---
                conv_result = query_insert(  # insert conversion record
                    """INSERT INTO employee_type_conversions
                           (conversion_number, employee_id, from_type, to_type, conversion_date,
                            vl_balance_before, sl_balance_before, vsc_balance_after,
                            vsc_balance_before, total_credits_converted, vl_balance_after, sl_balance_after,
                            remarks, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, 0, 0, %s, %s)""",
                    [
                        conversion_number,  # unique reference number
                        employee_id,        # employee being converted
                        current_type,       # from NON_TEACHING
                        new_type,           # to TEACHING
                        conversion_date,    # effective date
                        vl_balance,         # VL balance that was converted
                        sl_balance,         # SL balance that was converted
                        vsc_credits,        # VSC credits assigned
                        vsc_credits,        # total_credits_converted = vsc for display
                        remarks,            # optional notes
                        created_by,         # user who triggered the conversion
                    ]
                )
                if conv_result["statusCode"] != 200:  # check if insert failed
                    return conv_result  # return error from gateway

                conv_id = conv_result["insertId"]  # capture conversion record ID for ledger FK

                # --- Post DEBIT on VL to zero out the balance (only if balance > 0) ---
                if vl_balance > 0:  # skip if already zero
                    r = post_ledger(vl_type_id, "DEBIT", vl_balance, conv_id,
                                    f"Type conversion {current_type}->{new_type}: VL zeroed out")
                    if r["statusCode"] != 200:  # check if ledger insert failed
                        return r  # propagate error

                # --- Post DEBIT on SL to zero out the balance (only if balance > 0) ---
                if sl_balance > 0:  # skip if already zero
                    r = post_ledger(sl_type_id, "DEBIT", sl_balance, conv_id,
                                    f"Type conversion {current_type}->{new_type}: SL zeroed out")
                    if r["statusCode"] != 200:  # check if ledger insert failed
                        return r  # propagate error

                # --- Post CREDIT on VSC (only if vsc_credits > 0) ---
                if vsc_credits > 0:  # skip if formula produces zero (e.g. both balances were 0)
                    r = post_ledger(vsc_type_id, "CREDIT", vsc_credits, conv_id,
                                    f"Type conversion {current_type}->{new_type}: VSC initialized from VL+SL")
                    if r["statusCode"] != 200:  # check if ledger insert failed
                        return r  # propagate error

                    # --- Insert into vsc_new_credit_balances so the balance appears on the leave card ---
                    query_insert(  # add a balance transfer entry visible in the VSC summary
                        """INSERT INTO vsc_new_credit_balances
                               (service_credit_application_id, employee_id, original_balance, remaining_balance, remarks)
                           VALUES (NULL, %s, %s, %s, 'Balance Transfer')""",
                        [employee_id, vsc_credits, vsc_credits]
                    )

                # --- Recalculate ledger snapshots and update employee_leave_balances cache ---
                recalculate_ledger_snapshots(employee_id, vl_type_id)   # re-run VL running balance
                recalculate_ledger_snapshots(employee_id, sl_type_id)   # re-run SL running balance
                recalculate_ledger_snapshots(employee_id, vsc_type_id)  # re-run VSC running balance

                # --- Flip the employee_type on the employees record ---
                query(  # update the employee classification
                    "UPDATE employees SET employee_type = %s WHERE id = %s",
                    [new_type, employee_id]
                )

                return {  # return success with conversion summary
                    "statusCode": 200,  # success
                    "message": f"Employee converted from NON_TEACHING to TEACHING",  # confirmation
                    "conversion_number": conversion_number,  # audit reference
                    "from_type": current_type,               # original type
                    "to_type": new_type,                     # new type
                    "vl_balance_before": vl_balance,          # VL that was zeroed
                    "sl_balance_before": sl_balance,          # SL that was zeroed
                    "vsc_balance_after": vsc_credits,         # VSC assigned
                }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Get conversion history by employee
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int) -> dict:
        """
        Retrieves all personnel type conversion records for a given employee,
        ordered by conversion_date descending (most recent first).

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with list of conversion records and employee info,
                  or 404 if the employee does not exist.
        """
        try:
            emp = fetch_query(  # verify the employee exists
                "SELECT id, first_name, last_name, employee_number, employee_type FROM employees WHERE id = %s",
                [employee_id]
            )
            if not emp:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}  # return 404

            rows = fetch_query(  # fetch all conversions for the employee ordered newest first
                """SELECT etc.*
                   FROM employee_type_conversions etc
                   WHERE etc.employee_id = %s
                   ORDER BY etc.conversion_date DESC, etc.id DESC""",
                [employee_id]
            )

            return {  # return success with data
                "statusCode": 200,  # success code
                "employee": emp[0],  # basic employee info for context
                "count": len(rows) if rows else 0,  # total records
                "data": rows if rows else [],  # conversion history
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail
