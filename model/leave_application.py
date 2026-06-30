from pydantic import BaseModel  # import BaseModel as the base for all models
from typing import Optional  # import Optional for nullable fields
from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
from flask import g  # import g to read the authenticated user set by the auth decorator
import uuid  # import uuid to generate unique application numbers


class LeaveApplication(BaseModel):
    """
    Pydantic model representing a leave application record.

    Attributes:
        employee_id: FK to the employee submitting the application.
        leave_type_id: FK to the requested leave type.
        date_filed: Date the application was submitted (YYYY-MM-DD).
        reason: Employee's stated reason for the leave.
        other_leave_description: Extra description when leave type is Others (optional).
        dates: List of leave date entries; each must have leave_date, duration_type,
               half_day_period (required if HALF_DAY), and is_paid.
    """
    employee_id: int  # FK to employees table
    leave_type_id: int  # FK to leave_types table
    date_filed: str  # date the application was filed
    reason: str  # reason for the leave
    other_leave_description: Optional[str] = None  # extra description for Others leave type
    dates: list = []  # list of individual leave date entries

    # --------------------------
    # Generate application number
    # --------------------------

    @staticmethod
    def _generate_application_number() -> str:
        """
        Generates a unique leave application number using a UUID-based suffix.

        Returns:
            str: An application number in the format 'LA-XXXXXXXX'.
        """
        suffix = uuid.uuid4().hex[:8].upper()  # take first 8 chars of a UUID hex string
        return f"LA-{suffix}"  # format as LA-XXXXXXXX

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
    # Calculate total leave days from dates list
    # --------------------------

    @staticmethod
    def _calculate_total_days(dates: list) -> float:
        """
        Calculates total leave days from a list of leave date entries.
        FULL_DAY = 1.0, HALF_DAY (AM or PM) = 0.5.

        Parameters:
            dates (list): List of leave date dicts each with a duration_type field.

        Returns:
            float: Total leave days rounded to 2 decimal places.
        """
        total = 0.0  # start accumulator at zero
        for entry in dates:  # iterate each date entry
            total += 1.0 if entry["duration_type"] == "FULL_DAY" else 0.5  # add 1.0 or 0.5
        return round(total, 2)  # return rounded total

    # --------------------------
    # Validate dates against holiday calendar
    # --------------------------

    @staticmethod
    def _validate_holidays(dates: list) -> list:
        """
        Checks every submitted leave date against calendar_events (blocks_leave = 1).
        Collects all conflicts into a single list so the caller can return them all at once.

        Rules:
          FULL holiday  → blocks FULL_DAY, AM, and PM.
          AM holiday    → blocks FULL_DAY and AM; allows PM.
          PM holiday    → blocks FULL_DAY and PM; allows AM.

        Parameters:
            dates (list): Validated leave date dicts with leave_date, duration_type, half_day_period.

        Returns:
            list[str]: List of human-readable error messages (empty if no conflicts).
        """
        errors = []  # collect all conflict messages
        for entry in dates:  # check each submitted date
            leave_date = entry["leave_date"]  # the date being applied for
            duration_type = entry["duration_type"]  # FULL_DAY or HALF_DAY
            half_day_period = entry.get("half_day_period")  # AM, PM, or None

            holiday = fetch_query(  # look up any blocking holiday on this date
                "SELECT name, period FROM calendar_events WHERE date = %s AND blocks_leave = 1",
                [leave_date]
            )

            if not holiday:  # no holiday on this date — nothing to validate
                continue

            h = holiday[0]  # take the first (and only, due to UNIQUE date constraint) result
            holiday_name = h["name"]  # human-readable holiday name for the error message
            holiday_period = h["period"]  # FULL, AM, or PM

            if holiday_period == "FULL":  # full-day holiday blocks all leave types on this date
                errors.append(
                    f"Leave cannot be applied on {leave_date} because it is a full-day holiday ({holiday_name})."
                )
            elif holiday_period == "AM":  # AM holiday blocks FULL_DAY and AM leaves
                if duration_type == "FULL_DAY":  # full-day leave overlaps the AM holiday
                    errors.append(
                        f"Full-day leave cannot be applied on {leave_date} because the AM period is a holiday ({holiday_name})."
                    )
                elif duration_type == "HALF_DAY" and half_day_period == "AM":  # AM leave overlaps the AM holiday
                    errors.append(
                        f"Leave cannot be applied on {leave_date} AM because it is a half-day holiday ({holiday_name})."
                    )
            elif holiday_period == "PM":  # PM holiday blocks FULL_DAY and PM leaves
                if duration_type == "FULL_DAY":  # full-day leave overlaps the PM holiday
                    errors.append(
                        f"Full-day leave cannot be applied on {leave_date} because the PM period is a holiday ({holiday_name})."
                    )
                elif duration_type == "HALF_DAY" and half_day_period == "PM":  # PM leave overlaps the PM holiday
                    errors.append(
                        f"Leave cannot be applied on {leave_date} PM because it is a half-day holiday ({holiday_name})."
                    )

        return errors  # return all found holiday conflicts

    # --------------------------
    # Validate dates against existing leave overlaps
    # --------------------------

    @staticmethod
    def _validate_overlaps(employee_id: int, dates: list, exclude_application_id: int = None) -> list:
        """
        Checks every submitted leave date against the employee's existing PENDING or APPROVED
        leave applications. A conflict occurs when the same date is booked with an overlapping period.

        Conflict rules (new vs existing):
          FULL_DAY existing  → conflicts with any new duration.
          New FULL_DAY       → conflicts with any existing duration.
          Both HALF_DAY      → conflict only when same half_day_period (AM vs AM, PM vs PM).

        Parameters:
            employee_id (int): The employee submitting the application.
            dates (list): Validated leave date dicts.
            exclude_application_id (int | None): Application ID to exclude from overlap checks (used during updates).

        Returns:
            list[str]: List of human-readable error messages (empty if no conflicts).
        """
        errors = []  # collect all overlap messages
        for entry in dates:  # check each submitted date
            leave_date = entry["leave_date"]  # the date being applied for
            duration_type = entry["duration_type"]  # FULL_DAY or HALF_DAY
            half_day_period = entry.get("half_day_period")  # AM, PM, or None

            sql = (  # base query for matching dates in active applications for this employee
                """SELECT lad.duration_type, lad.half_day_period,
                          la.application_number, la.status
                   FROM leave_application_dates lad
                   JOIN leave_applications la ON la.id = lad.leave_application_id
                   WHERE la.employee_id = %s
                     AND la.status IN ('FOR HRMO ACTION', 'FOR APPROVAL', 'APPROVED')
                     AND la.is_deleted = 0
                     AND DATE_FORMAT(lad.leave_date, '%%Y-%%m-%%d') = %s"""
            )
            params = [employee_id, leave_date]  # base bound parameters

            if exclude_application_id is not None:  # exclude the application being edited from conflict detection
                sql += " AND la.id != %s"  # skip rows belonging to this application
                params.append(exclude_application_id)  # bind the excluded application ID

            existing = fetch_query(sql, params)  # execute the overlap query

            for ex in (existing or []):  # check each existing record on the same date
                ex_type = ex["duration_type"]  # existing entry's duration type
                ex_period = ex.get("half_day_period")  # existing entry's half-day period
                conflict = False  # assume no conflict until proven

                if ex_type == "FULL_DAY":  # an existing full-day blocks the entire date
                    conflict = True
                elif duration_type == "FULL_DAY":  # a new full-day conflicts with any existing entry
                    conflict = True
                elif ex_type == "HALF_DAY" and duration_type == "HALF_DAY":  # both half-days — same period = conflict
                    conflict = (ex_period == half_day_period)

                if conflict:  # this submitted date conflicts with an existing one
                    period_label = f" ({half_day_period})" if duration_type == "HALF_DAY" and half_day_period else ""  # label for half-day
                    errors.append(
                        f"An overlapping leave already exists on {leave_date}{period_label} "
                        f"(Application: {ex['application_number']}, Status: {ex['status']})."
                    )
                    break  # one error per submitted date is sufficient

        return errors  # return all found overlap conflicts

    # --------------------------
    # Fetch leave dates for a single application
    # --------------------------

    @staticmethod
    def _get_dates_for_application(application_id: int) -> list:
        """
        Fetches all leave_application_dates rows for a given application, ordered by date ascending.

        Parameters:
            application_id (int): The leave application's primary key.

        Returns:
            list[dict]: List of date rows with leave_date, duration_type, half_day_period, is_paid.
        """
        rows = fetch_query(  # query the child date table
            """SELECT id,
                      DATE_FORMAT(leave_date, '%%Y-%%m-%%d') AS leave_date,
                      duration_type, half_day_period, is_paid,
                      created_at, updated_at
               FROM leave_application_dates
               WHERE leave_application_id = %s
               ORDER BY leave_date ASC""",
            [application_id]
        )
        return rows or []  # return rows or empty list if none found

    # --------------------------
    # Enrich application rows with leave dates and derived fields
    # --------------------------

    @staticmethod
    def _enrich_with_dates(rows: list) -> list:
        """
        Attaches leave_dates, and derived start_date, end_date, total_days to each application row.
        Modifies the rows in-place and returns them.

        Parameters:
            rows (list): Leave application dicts fetched from the DB.

        Returns:
            list: The same rows with leave_dates, start_date, end_date, total_days added.
        """
        for app in rows:  # iterate each application row
            dates = LeaveApplication._get_dates_for_application(app["id"])  # fetch its dates
            app["leave_dates"] = dates  # attach the full date list
            if dates:  # derive fields only when dates exist
                app["start_date"] = dates[0]["leave_date"]  # earliest date (already sorted ASC)
                app["end_date"] = dates[-1]["leave_date"]  # latest date
                app["total_days"] = round(  # sum up all date contributions
                    sum(1.0 if d["duration_type"] == "FULL_DAY" else 0.5 for d in dates), 2
                )
            else:  # no dates — either an edge case or a monetization application
                app["start_date"] = None  # no start date derivable
                app["end_date"] = None  # no end date derivable
                mnt_total = round(  # for MNT applications, total comes from the vl+sl columns
                    float(app.get("mnt_vl_days") or 0) + float(app.get("mnt_sl_days") or 0), 2
                )
                app["total_days"] = mnt_total if mnt_total > 0 else 0.0  # use monetization total or zero
        return rows  # return the enriched rows

    # --------------------------
    # Post debit on submission
    # --------------------------

    @staticmethod
    def _post_debit(employee_id: int, leave_type_id: int, leave_type_code: str,
                    balance_type: str, total_days: float, application_id: int,
                    start_date: str) -> dict | None:
        """
        Posts a DEBIT entry to the ledger when a leave application is submitted.
        Balance is deducted immediately so available balance always reflects pending leaves.
        Uses the earliest leave date (start_date) as transaction_date for correct ledger ordering.
        No debit is posted when balance_type is NONE.

        Parameters:
            employee_id (int): The employee whose balance is being deducted.
            leave_type_id (int): The leave type being deducted.
            leave_type_code (str): The leave type code (VL, SL, FL, etc.).
            balance_type (str): SELF, CHARGED_TO_VL, or NONE.
            total_days (float): Number of days to deduct.
            application_id (int): The source leave application ID.
            start_date (str): Earliest leave date (YYYY-MM-DD) used as transaction_date.

        Returns:
            dict | None: An error dict if debit fails, None on success.
        """
        if balance_type == "NONE":  # no deduction required for this leave type
            return None  # skip ledger posting

        if balance_type == "CHARGED_TO_VL":  # FL — deduct from both FL own balance and VL balance
            vl_type = fetch_query(  # get the VL leave type ID
                "SELECT id FROM leave_types WHERE code = 'VL'", []
            )
            if not vl_type:  # VL type not found in system
                return {"statusCode": 500, "message": "VL leave type not found in the system"}  # return error

            vl_leave_type_id = vl_type[0]["id"]  # VL leave type ID for the VL deduction

            fl_result = query_insert(  # insert DEBIT for FL own balance
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApplication._generate_transaction_number(),  # unique transaction number
                    employee_id,                  # employee being debited
                    leave_type_id,                # FL leave type ID
                    total_days,                   # days deducted
                    application_id,               # source leave application
                    start_date,                   # earliest leave date as transaction_date
                    f"Leave application submitted — {leave_type_code} deducted",  # auto remarks
                ]
            )
            if fl_result["statusCode"] != 200:  # check if FL ledger insert failed
                return fl_result  # return the error

            recalculate_ledger_snapshots(employee_id, leave_type_id)  # cascade-recalculate all FL snapshots

            vl_result = query_insert(  # insert DEBIT for VL balance
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApplication._generate_transaction_number(),  # unique transaction number
                    employee_id,                  # employee being debited
                    vl_leave_type_id,             # VL leave type ID
                    total_days,                   # days deducted
                    application_id,               # source leave application
                    start_date,                   # earliest leave date as transaction_date
                    f"Leave application submitted — VL charged for {leave_type_code}",  # auto remarks
                ]
            )
            if vl_result["statusCode"] != 200:  # check if VL ledger insert failed
                return vl_result  # return the error

            recalculate_ledger_snapshots(employee_id, vl_leave_type_id)  # cascade-recalculate all VL snapshots
            return None  # both FL and VL debits posted successfully

        if balance_type == "CHARGED_TO_VSC":  # PR — cascade through new VSC credits via per-credit log
            return LeaveApplication._deduct_vsc(  # delegate to VSC-specific cascading deduction (new credits only)
                employee_id=employee_id,
                total_days=total_days,
                application_id=application_id,
                start_date=start_date,
                leave_type_code=leave_type_code,  # "PR"
            )

        # SELF — deduct from the leave type's own balance only
        if leave_type_code == "CTO":  # CTO deduction cascades across per-credit balances by earliest valid_until
            return LeaveApplication._deduct_cto(  # delegate to CTO-specific cascading deduction
                employee_id=employee_id,
                leave_type_id=leave_type_id,
                total_days=total_days,
                application_id=application_id,
                start_date=start_date,
            )

        if leave_type_code == "SL":  # SL: use VSC credits first (old then new) if they can fully cover
            old_row = fetch_query(  # sum remaining old VSC credits
                "SELECT COALESCE(SUM(remaining_balance), 0.0) AS total FROM vsc_old_credit_balances WHERE employee_id = %s AND remaining_balance > 0",
                [employee_id]
            )
            new_row = fetch_query(  # sum remaining new VSC credits
                "SELECT COALESCE(SUM(remaining_balance), 0.0) AS total FROM vsc_new_credit_balances WHERE employee_id = %s AND remaining_balance > 0",
                [employee_id]
            )
            total_vsc = float(old_row[0]["total"]) + float(new_row[0]["total"])  # combined VSC available

            if total_vsc >= total_days:  # VSC can fully cover — deduct from VSC, leave regular SL balance untouched
                return LeaveApplication._deduct_vsc(  # cascade old VSC then new VSC
                    employee_id=employee_id,
                    total_days=total_days,
                    application_id=application_id,
                    start_date=start_date,
                    leave_type_code="SL",
                )
            # VSC insufficient — fall through to deduct from regular SL balance below

        insert_result = query_insert(  # insert the DEBIT record for SELF leave types
            """INSERT INTO leave_credit_transactions
                   (transaction_number, employee_id, leave_type_id, transaction_type,
                    amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
               VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
            [
                LeaveApplication._generate_transaction_number(),  # generated transaction number
                employee_id,                  # employee being debited
                leave_type_id,                # leave type being debited
                total_days,                   # days being deducted
                application_id,               # source: the submitted leave application
                start_date,                   # earliest leave date as transaction_date
                f"Leave application submitted — {leave_type_code} deducted",  # auto remarks
            ]
        )

        if insert_result["statusCode"] != 200:  # check if ledger insert failed
            return insert_result  # return the error

        recalculate_ledger_snapshots(employee_id, leave_type_id)  # cascade-recalculate all snapshots
        return None  # debit posted successfully

    # --------------------------
    # Fetch a single balance
    # --------------------------

    @staticmethod
    def _get_balance(employee_id: int, leave_code: str) -> float:
        """
        Returns the employee's current cached balance for a leave type by its code.

        Parameters:
            employee_id (int): The employee's primary key.
            leave_code (str): The leave type code to look up (e.g. 'VL', 'SL', 'FL').

        Returns:
            float: Current balance in days, or 0.0 if no record exists.
        """
        row = fetch_query(  # query balance joined with leave_types for code lookup
            """SELECT elb.balance
               FROM employee_leave_balances elb
               JOIN leave_types lt ON lt.id = elb.leave_type_id
               WHERE elb.employee_id = %s AND lt.code = %s""",
            [employee_id, leave_code]
        )
        return float(row[0]["balance"]) if row else 0.0  # cast Decimal to float

    # --------------------------
    # Check CTO balance across per-credit records
    # --------------------------

    @staticmethod
    def _check_cto_balance(employee_id: int, total_days: float) -> dict | None:
        """
        Validates the employee has enough total remaining CTO balance across all their
        CTO service credit records in cto_credit_balances.

        Parameters:
            employee_id (int): The employee's primary key.
            total_days (float): Number of CTO leave days being requested.

        Returns:
            dict | None: An error dict if insufficient, None if sufficient.
        """
        row = fetch_query(  # sum all remaining CTO credit balances for this employee
            """SELECT COALESCE(SUM(remaining_balance), 0) AS total
               FROM cto_credit_balances
               WHERE employee_id = %s AND remaining_balance > 0""",
            [employee_id]
        )

        available = float(row[0]["total"]) if row else 0.0  # cast to float

        if available < total_days:  # not enough total CTO credit across all records
            return {  # return structured insufficiency error
                "statusCode": 400,
                "message": "Insufficient CTO balance",
                "leave_type_checked": "CTO",
                "required_days": total_days,
                "available_days": available,
                "shortfall_days": round(total_days - available, 2),
            }

        return None  # sufficient balance

    # --------------------------
    # Deduct CTO leave from per-credit balances (earliest valid_until first)
    # --------------------------

    @staticmethod
    def _deduct_cto(employee_id: int, leave_type_id: int, total_days: float,
                    application_id: int, start_date: str) -> dict | None:
        """
        Deducts CTO leave days from the employee's CTO service credits ordered by earliest
        valid_until first, cascading to the next credit when one is exhausted.
        Posts a separate DEBIT ledger entry per credit consumed and logs each deduction
        in cto_deduction_log for reversal tracking.

        Parameters:
            employee_id (int): The employee whose CTO credits are being debited.
            leave_type_id (int): The CTO leave type ID for ledger entries.
            total_days (float): Total CTO days to deduct.
            application_id (int): The source leave application ID.
            start_date (str): Earliest leave date (YYYY-MM-DD) used as transaction_date.

        Returns:
            dict | None: An error dict if any step fails, None on full success.
        """
        credits = fetch_query(  # fetch active CTO credits ordered by earliest expiry first
            """SELECT id, remaining_balance, valid_until,
                      (SELECT application_number FROM service_credit_applications
                       WHERE id = cto_credit_balances.service_credit_application_id) AS app_number
               FROM cto_credit_balances
               WHERE employee_id = %s AND remaining_balance > 0
               ORDER BY valid_until ASC, id ASC""",
            [employee_id]
        )

        # clear any existing log entries for this application before inserting fresh ones
        # this handles re-activation (reversed → active) where old entries from the prior submission still exist
        query(
            "DELETE FROM cto_deduction_log WHERE leave_application_id = %s",
            [application_id]
        )

        remaining = round(total_days, 2)  # track how many days still need to be deducted

        for credit in credits:  # iterate credits from earliest to latest expiry
            if remaining <= 0:  # all days accounted for — stop
                break

            deduct = round(min(float(credit["remaining_balance"]), remaining), 2)  # take as much as this credit can give

            update_result = query(  # reduce this credit's remaining balance
                "UPDATE cto_credit_balances SET remaining_balance = remaining_balance - %s WHERE id = %s",
                [deduct, credit["id"]]
            )
            if update_result["statusCode"] != 200:  # check if update failed
                return update_result  # return the error

            log_result = query_insert(  # record how much was taken from this credit for reversal tracking
                """INSERT INTO cto_deduction_log
                       (cto_credit_balance_id, leave_application_id, amount_deducted)
                   VALUES (%s, %s, %s)""",
                [credit["id"], application_id, deduct]
            )
            if log_result["statusCode"] != 200:  # check if log insert failed
                return log_result  # return the error

            valid_label = str(credit["valid_until"])  # format expiry for ledger remarks
            txn_result = query_insert(  # post a DEBIT ledger entry for this partial deduction
                """INSERT INTO leave_credit_transactions
                       (transaction_number, employee_id, leave_type_id, transaction_type,
                        amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                   VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                [
                    LeaveApplication._generate_transaction_number(),  # unique transaction number
                    employee_id,           # employee being debited
                    leave_type_id,         # CTO leave type
                    deduct,                # days deducted from this specific credit
                    application_id,        # source leave application
                    start_date,            # earliest leave date as transaction_date
                    f"CTO leave deducted from credit {credit['app_number']} (valid until {valid_label})",  # audit trail
                ]
            )
            if txn_result["statusCode"] != 200:  # check if ledger insert failed
                return txn_result  # return the error

            remaining = round(remaining - deduct, 2)  # reduce the outstanding amount

        recalculate_ledger_snapshots(employee_id, leave_type_id)  # recalculate all CTO ledger snapshots once
        return None  # all deductions posted successfully

    # --------------------------
    # Deduct VSC credits for SL / PR leave
    # --------------------------

    @staticmethod
    def _deduct_vsc(employee_id: int, total_days: float, application_id: int,
                    start_date: str, leave_type_code: str) -> dict | None:
        """
        Cascades VSC deductions for SL or PR leave applications.
        For SL: deducts from old credits first (ORDER BY id ASC), then new credits if old is exhausted.
        For PR: deducts from new credits only (ORDER BY id ASC).
        Posts a separate DEBIT ledger entry per credit consumed and logs each deduction
        in vsc_deduction_log for reversal tracking. Clears stale log entries before inserting
        to handle re-activation of a previously reversed application cleanly.

        Parameters:
            employee_id (int): The employee whose VSC credits are being deducted.
            total_days (float): Total leave days to deduct.
            application_id (int): The source leave application ID.
            start_date (str): Earliest leave date (YYYY-MM-DD) used as transaction_date.
            leave_type_code (str): 'SL' or 'PR' — determines which credit pools to use.

        Returns:
            dict | None: An error dict if any step fails, None on full success.
        """
        vsc_type = fetch_query(  # fetch the VSC leave type ID for ledger entries
            "SELECT id FROM leave_types WHERE code = 'VSC'", []
        )
        if not vsc_type:  # VSC type not found in system
            return {"statusCode": 500, "message": "VSC leave type not found in the system"}  # return error
        vsc_leave_type_id = vsc_type[0]["id"]  # VSC leave type ID used for all DEBIT ledger entries

        query(  # clear stale log entries before inserting fresh ones (handles re-activation)
            "DELETE FROM vsc_deduction_log WHERE leave_application_id = %s",
            [application_id]
        )

        remaining = round(total_days, 2)  # track outstanding days still to be deducted

        if leave_type_code == "SL":  # SL: process old credits first before touching new credits
            old_credits = fetch_query(  # fetch old VSC credits with balance remaining, oldest ID first
                "SELECT id, remaining_balance FROM vsc_old_credit_balances WHERE employee_id = %s AND remaining_balance > 0 ORDER BY id ASC",
                [employee_id]
            )
            for credit in (old_credits or []):  # iterate old credits until remaining is satisfied
                if remaining <= 0:  # all days accounted for — stop early
                    break
                deduct = round(min(float(credit["remaining_balance"]), remaining), 2)  # take as much as this credit can give

                upd = query(  # reduce this old credit's remaining balance
                    "UPDATE vsc_old_credit_balances SET remaining_balance = remaining_balance - %s WHERE id = %s",
                    [deduct, credit["id"]]
                )
                if upd["statusCode"] != 200:  # check if update failed
                    return upd  # return the error

                log_result = query_insert(  # record deduction amount for reversal tracking
                    "INSERT INTO vsc_deduction_log (leave_application_id, credit_pool, credit_balance_id, amount_deducted) VALUES (%s, 'OLD', %s, %s)",
                    [application_id, credit["id"], deduct]
                )
                if log_result["statusCode"] != 200:  # check if log insert failed
                    return log_result  # return the error

                txn_result = query_insert(  # post DEBIT to VSC ledger for this partial deduction
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                    [
                        LeaveApplication._generate_transaction_number(),  # unique transaction number
                        employee_id,           # employee being debited
                        vsc_leave_type_id,     # VSC leave type for the ledger entry
                        deduct,                # days deducted from this specific credit
                        application_id,        # source leave application
                        start_date,            # earliest leave date as transaction_date
                        f"Leave application submitted — VSC (old) charged for {leave_type_code}",  # audit trail
                    ]
                )
                if txn_result["statusCode"] != 200:  # check if ledger insert failed
                    return txn_result  # return the error

                remaining = round(remaining - deduct, 2)  # reduce outstanding amount

        if remaining > 0:  # for SL (after old exhausted) and PR: process new credits
            new_credits = fetch_query(  # fetch new VSC credits with balance remaining, oldest ID first
                "SELECT id, remaining_balance FROM vsc_new_credit_balances WHERE employee_id = %s AND remaining_balance > 0 ORDER BY id ASC",
                [employee_id]
            )
            for credit in (new_credits or []):  # iterate new credits until remaining is satisfied
                if remaining <= 0:  # all days accounted for — stop early
                    break
                deduct = round(min(float(credit["remaining_balance"]), remaining), 2)  # take as much as this credit can give

                upd = query(  # reduce this new credit's remaining balance
                    "UPDATE vsc_new_credit_balances SET remaining_balance = remaining_balance - %s WHERE id = %s",
                    [deduct, credit["id"]]
                )
                if upd["statusCode"] != 200:  # check if update failed
                    return upd  # return the error

                log_result = query_insert(  # record deduction amount for reversal tracking
                    "INSERT INTO vsc_deduction_log (leave_application_id, credit_pool, credit_balance_id, amount_deducted) VALUES (%s, 'NEW', %s, %s)",
                    [application_id, credit["id"], deduct]
                )
                if log_result["statusCode"] != 200:  # check if log insert failed
                    return log_result  # return the error

                txn_result = query_insert(  # post DEBIT to VSC ledger for this partial deduction
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'DEBIT', %s, 'LEAVE_APPLICATION', %s, %s, 0, %s)""",
                    [
                        LeaveApplication._generate_transaction_number(),  # unique transaction number
                        employee_id,           # employee being debited
                        vsc_leave_type_id,     # VSC leave type for the ledger entry
                        deduct,                # days deducted from this specific credit
                        application_id,        # source leave application
                        start_date,            # earliest leave date as transaction_date
                        f"Leave application submitted — VSC (new) charged for {leave_type_code}",  # audit trail
                    ]
                )
                if txn_result["statusCode"] != 200:  # check if ledger insert failed
                    return txn_result  # return the error

                remaining = round(remaining - deduct, 2)  # reduce outstanding amount

        recalculate_ledger_snapshots(employee_id, vsc_leave_type_id)  # recalculate all VSC ledger snapshots once
        return None  # all VSC deductions posted successfully

    # --------------------------
    # Holiday refund — credit back overlapping leave balances
    # --------------------------

    @staticmethod
    def _refund_holiday(holiday_date: str, holiday_period: str, calendar_event_id: int) -> None:
        """
        Runs in a background thread when a holiday is created or activated.
        Finds all active (non-deleted, non-reversed) leave applications that have a date
        overlapping with the holiday, credits back the appropriate balance per application,
        and records each refund in the leave_refunded_dates table.
        Idempotent: skips any application that already has a row in leave_refunded_dates
        for the given holiday_date.

        Holiday period matching rules:
          FULL → any leave date on that day (full-day or half-day)
          AM   → full-day leaves (refund 0.5) and AM half-day leaves (refund 0.5)
          PM   → full-day leaves (refund 0.5) and PM half-day leaves (refund 0.5)

        Balance credit rules mirror the deduction rules:
          NONE            → skip (no balance was deducted)
          SELF (non-CTO)  → credit own leave type
          SELF (CTO)      → credit CTO ledger
          SELF (SL+VSC)   → credit VSC ledger (SL was funded by VSC)
          CHARGED_TO_VL   → credit both FL and VL
          CHARGED_TO_VSC  → credit VSC

        Parameters:
            holiday_date (str): The holiday date in YYYY-MM-DD format.
            holiday_period (str): 'FULL', 'AM', or 'PM'.
            calendar_event_id (int): The calendar_events.id of the holiday (used as source_id).
        """
        try:
            if holiday_period == "AM":  # AM holiday: match full-day or AM half-day leaves
                period_filter = "(lad.duration_type = 'FULL_DAY' OR (lad.duration_type = 'HALF_DAY' AND lad.half_day_period = 'AM'))"
            elif holiday_period == "PM":  # PM holiday: match full-day or PM half-day leaves
                period_filter = "(lad.duration_type = 'FULL_DAY' OR (lad.duration_type = 'HALF_DAY' AND lad.half_day_period = 'PM'))"
            else:  # FULL holiday: match any leave on this date
                period_filter = "1=1"

            rows = fetch_query(  # find all active leave apps with a date on this holiday
                f"""SELECT la.id AS application_id, la.employee_id, la.leave_type_id,
                           lt.code AS leave_type_code, lt.balance_type,
                           lad.duration_type, lad.half_day_period
                    FROM leave_application_dates lad
                    JOIN leave_applications la ON la.id = lad.leave_application_id
                    JOIN leave_types lt ON lt.id = la.leave_type_id
                    WHERE lad.leave_date = %s
                      AND {period_filter}
                      AND la.is_deleted = 0
                      AND la.status NOT IN ('RETURNED', 'DISAPPROVED')""",
                [holiday_date]
            )

            vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # fetch VL type once
            vl_type_id = vl_type[0]["id"] if vl_type else None  # VL leave type ID
            vsc_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VSC'", [])  # fetch VSC type once
            vsc_type_id = vsc_type[0]["id"] if vsc_type else None  # VSC leave type ID

            for row in (rows or []):  # process each overlapping leave application
                application_id = row["application_id"]  # leave application primary key
                employee_id = row["employee_id"]  # employee being refunded
                leave_type_id = row["leave_type_id"]  # leave type of the application
                code = row["leave_type_code"]  # short leave code (VL, SL, CTO, etc.)
                balance_type = row["balance_type"]  # SELF, CHARGED_TO_VL, CHARGED_TO_VSC, NONE

                already_refunded = fetch_query(  # idempotency check: skip if already processed for this date
                    "SELECT id FROM leave_refunded_dates WHERE leave_application_id = %s AND holiday_date = %s LIMIT 1",
                    [application_id, holiday_date]
                )
                if already_refunded:  # refund already recorded for this application + date combination
                    continue  # skip — idempotency guard

                if holiday_period == "FULL":  # full-day holiday
                    refund_amount = 1.0 if row["duration_type"] == "FULL_DAY" else 0.5  # full or half
                else:  # AM or PM holiday — always 0.5 regardless of leave duration_type
                    refund_amount = 0.5

                credits_to_post = []  # collect (leave_type_id, amount) pairs to credit

                if balance_type == "NONE":  # no balance was deducted — nothing to refund
                    pass  # skip credit posting for NONE types

                elif balance_type == "CHARGED_TO_VL":  # FL — credit back both FL and VL
                    credits_to_post.append((leave_type_id, refund_amount))  # FL entitlement credit
                    if vl_type_id:  # also credit VL balance
                        credits_to_post.append((vl_type_id, refund_amount))  # VL credit

                elif balance_type == "CHARGED_TO_VSC":  # PR — credit VSC balance
                    if vsc_type_id:  # credit VSC ledger
                        credits_to_post.append((vsc_type_id, refund_amount))  # VSC credit

                else:  # SELF — determine effective leave type
                    if code == "SL":  # SL may have used VSC credits instead of regular SL balance
                        vsc_log = fetch_query(  # check if this SL app deducted from VSC
                            "SELECT id FROM vsc_deduction_log WHERE leave_application_id = %s LIMIT 1",
                            [application_id]
                        )
                        effective_id = vsc_type_id if vsc_log else leave_type_id  # VSC or regular SL
                    else:  # all other SELF types (VL, SPL, CTO, etc.)
                        effective_id = leave_type_id  # credit own leave type

                    if effective_id:  # post credit to the effective type
                        credits_to_post.append((effective_id, refund_amount))  # own-type credit

                for credit_type_id, credit_amount in credits_to_post:  # post each collected credit
                    LeaveApplication._post_holiday_credit(  # insert CREDIT ledger entry
                        employee_id, credit_type_id, credit_amount, calendar_event_id, holiday_date, code
                    )
                    recalculate_ledger_snapshots(employee_id, credit_type_id)  # update cached balance
                    query_insert(  # record this refund in the dedicated table
                        """INSERT INTO leave_refunded_dates
                               (leave_application_id, calendar_event_id, holiday_date,
                                amount_refunded, credited_leave_type_id)
                           VALUES (%s, %s, %s, %s, %s)""",
                        [application_id, calendar_event_id, holiday_date, credit_amount, credit_type_id]
                    )

        except Exception as e:  # catch all errors — this runs in a background thread
            import traceback  # import here to keep it out of the module-level namespace
            print(f"[holiday_refund] Error processing {holiday_date}: {e}")  # log the short message
            traceback.print_exc()  # print the full stack trace so the root cause is visible

    @staticmethod
    def _post_holiday_credit(employee_id: int, leave_type_id: int, amount: float,
                              calendar_event_id: int, holiday_date: str, leave_type_code: str) -> None:
        """
        Posts a single CREDIT ledger entry for a holiday refund.

        Parameters:
            employee_id (int): The employee receiving the credit.
            leave_type_id (int): The leave type being credited.
            amount (float): Days to credit back.
            calendar_event_id (int): The calendar_events.id used as source_id.
            holiday_date (str): The holiday date (YYYY-MM-DD) used as transaction_date.
            leave_type_code (str): The leave code for the remarks string.
        """
        result = query_insert(  # insert CREDIT entry for this holiday refund
            """INSERT INTO leave_credit_transactions
                   (transaction_number, employee_id, leave_type_id, transaction_type,
                    amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
               VALUES (%s, %s, %s, 'CREDIT', %s, 'HOLIDAY_REFUND', %s, %s, 0, %s)""",
            [
                LeaveApplication._generate_transaction_number(),  # unique transaction number
                employee_id,          # employee being credited
                leave_type_id,        # leave type being credited
                amount,               # days refunded
                calendar_event_id,    # source: the holiday calendar event
                holiday_date,         # transaction date = the holiday date
                f"Holiday refund — {leave_type_code} leave on {holiday_date}",  # audit remarks
            ]
        )
        if result.get("statusCode") != 200:  # raise so the caller can surface the error
            raise RuntimeError(f"holiday credit insert failed: {result.get('message')}")

    # --------------------------
    # Check employee balance
    # --------------------------

    @staticmethod
    def _check_balance(employee_id: int, leave_type: dict, total_days: float) -> dict | None:
        """
        Validates the employee has sufficient balance for the requested leave.
        Rules by balance_type:
          SELF          → employee must have enough of their own leave type balance.
          CHARGED_TO_VL → employee must have enough FL entitlement AND enough VL balance.
          NONE          → no balance check required.

        Parameters:
            employee_id (int): The employee's primary key.
            leave_type (dict): The leave_type row — id, code, name, balance_type.
            total_days (float): Number of leave days being requested.

        Returns:
            dict | None: An error dict with balance details if insufficient, None if sufficient.
        """
        balance_type = leave_type["balance_type"]  # determine which check rule applies
        code = leave_type["code"]  # leave type code (VL, SL, FL, etc.)

        if balance_type == "NONE":  # no balance required for this leave type
            return None  # pass without checking

        if balance_type == "SELF":  # check the employee's own balance for this leave type
            if code == "CTO":  # CTO uses per-credit balance tracking instead of the aggregate cache
                return LeaveApplication._check_cto_balance(employee_id, total_days)  # delegate to CTO-specific check

            if code == "SL":  # SL uses VSC credits first (old then new) before falling back to regular SL balance
                old_row = fetch_query(  # sum remaining old VSC credits for this employee
                    "SELECT COALESCE(SUM(remaining_balance), 0.0) AS total FROM vsc_old_credit_balances WHERE employee_id = %s AND remaining_balance > 0",
                    [employee_id]
                )
                new_row = fetch_query(  # sum remaining new VSC credits for this employee
                    "SELECT COALESCE(SUM(remaining_balance), 0.0) AS total FROM vsc_new_credit_balances WHERE employee_id = %s AND remaining_balance > 0",
                    [employee_id]
                )
                total_vsc = float(old_row[0]["total"]) + float(new_row[0]["total"])  # combined VSC available

                if total_vsc >= total_days:  # VSC can fully cover this SL leave — no regular SL needed
                    return None  # pass balance check; _deduct_vsc will handle the actual deduction

            available = LeaveApplication._get_balance(employee_id, code)  # fetch own balance for non-CTO types

            if available < total_days:  # employee does not have enough
                return {  # return structured insufficiency error
                    "statusCode": 400,
                    "message": f"Insufficient {code} balance",
                    "leave_type_checked": code,
                    "required_days": total_days,
                    "available_days": available,
                    "shortfall_days": round(total_days - available, 2),
                }

        elif balance_type == "CHARGED_TO_VL":  # FL case: check both FL entitlement and VL balance
            fl_available = LeaveApplication._get_balance(employee_id, code)  # employee's FL entitlement
            vl_available = LeaveApplication._get_balance(employee_id, "VL")  # employee's VL balance

            errors = []  # collect all insufficiency details

            if fl_available < total_days:  # FL entitlement is not enough
                errors.append({
                    "leave_type_checked": code,
                    "required_days": total_days,
                    "available_days": fl_available,
                    "shortfall_days": round(total_days - fl_available, 2),
                })

            if vl_available < total_days:  # VL balance is not enough to cover FL charge
                errors.append({
                    "leave_type_checked": "VL",
                    "required_days": total_days,
                    "available_days": vl_available,
                    "shortfall_days": round(total_days - vl_available, 2),
                })

            if errors:  # at least one check failed
                return {
                    "statusCode": 400,
                    "message": f"Insufficient balance for {code} application. {code} is charged against VL — both {code} entitlement and VL balance must be sufficient.",
                    "insufficient_balances": errors,
                }

        elif balance_type == "CHARGED_TO_VSC":  # PR case: charged against new VSC credits only
            new_row = fetch_query(  # sum remaining new VSC credits for this employee
                "SELECT COALESCE(SUM(remaining_balance), 0.0) AS total FROM vsc_new_credit_balances WHERE employee_id = %s AND remaining_balance > 0",
                [employee_id]
            )
            new_available = float(new_row[0]["total"]) if new_row else 0.0  # available new VSC days

            if new_available < total_days:  # new VSC credits are not enough to fund this PR leave
                return {  # return structured insufficiency error
                    "statusCode": 400,
                    "message": f"Insufficient new VSC balance for {code} application. New VSC credits must be sufficient.",
                    "insufficient_balances": [{
                        "leave_type_checked": "VSC (new)",
                        "required_days": total_days,
                        "available_days": new_available,
                        "shortfall_days": round(total_days - new_available, 2),
                    }],
                }

        return None  # all checks passed

    # --------------------------
    # Submit leave application
    # --------------------------

    @staticmethod
    def submit(data: dict) -> dict:
        """
        Submits a new leave application after validating dates, holiday conflicts,
        overlap with existing leaves, leave type rules, and balance.
        Creates the application header and inserts individual date records.
        Balance is deducted immediately using the computed total from the dates array.

        Parameters:
            data (dict): Must contain: employee_id, leave_type_id, date_filed, reason, dates.
                         dates is a list of dicts each with:
                           leave_date (YYYY-MM-DD), duration_type (FULL_DAY|HALF_DAY),
                           half_day_period (AM|PM, required if HALF_DAY), is_paid (bool).
                         Optional: other_leave_description.

        Returns:
            dict: statusCode 201 with the created application data, or an error dict.
        """
        try:
            # --- Step 1: validate required header fields ---
            required_fields = ["employee_id", "leave_type_id", "date_filed", "reason", "dates"]  # mandatory keys
            for field in required_fields:  # check each required field
                if field not in data or (not data[field] and data[field] != 0):  # missing or empty
                    return {"statusCode": 400, "message": f"{field} is required"}  # reject immediately

            dates = data["dates"]  # reference the dates list

            if not isinstance(dates, list) or len(dates) == 0:  # must be a non-empty list
                return {"statusCode": 400, "message": "At least one leave date is required in dates[]"}

            # --- Step 2: validate and normalise each date entry ---
            VALID_DURATION_TYPES = ("FULL_DAY", "HALF_DAY")  # accepted duration_type values
            VALID_PERIODS = ("AM", "PM")  # accepted half_day_period values
            validation_errors = []  # accumulate format/logic errors
            seen_period_keys = set()  # track (date, period) combos to detect duplicates within this submission

            for i, entry in enumerate(dates):  # iterate each submitted date
                leave_date = (entry.get("leave_date") or "").strip()  # read and trim date string
                duration_type = (entry.get("duration_type") or "").strip().upper()  # normalise to uppercase
                raw_period = entry.get("half_day_period")  # may be None
                half_day_period = (raw_period or "").strip().upper() or None  # normalise or None

                if not leave_date:  # date string is missing or blank
                    validation_errors.append(f"dates[{i}]: leave_date is required")
                    continue  # skip further checks for this entry

                if duration_type not in VALID_DURATION_TYPES:  # unrecognised duration type
                    validation_errors.append(f"{leave_date}: duration_type must be FULL_DAY or HALF_DAY")
                    continue

                if duration_type == "HALF_DAY" and (not half_day_period or half_day_period not in VALID_PERIODS):  # HALF_DAY needs a period
                    validation_errors.append(f"{leave_date}: half_day_period (AM or PM) is required for HALF_DAY")
                    continue

                # normalise entry in-place so downstream validators see clean values
                entry["leave_date"] = leave_date  # trimmed date string
                entry["duration_type"] = duration_type  # uppercase
                entry["half_day_period"] = half_day_period if duration_type == "HALF_DAY" else None  # None for FULL_DAY
                entry["is_paid"] = bool(entry.get("is_paid", True))  # default to paid

                # check for duplicate (date + period) within this submission
                period_key = f"{leave_date}_{'FULL' if duration_type == 'FULL_DAY' else half_day_period}"  # unique key per slot
                if period_key in seen_period_keys:  # duplicate slot in this payload
                    validation_errors.append(f"{leave_date}: duplicate leave date/period in this submission")
                else:
                    seen_period_keys.add(period_key)  # mark as seen

                # check if FULL_DAY and any HALF_DAY are both submitted for the same date
                other_keys_on_same_date = [k for k in seen_period_keys if k.startswith(f"{leave_date}_") and k != period_key]
                if duration_type == "FULL_DAY" and any(
                    k.startswith(f"{leave_date}_AM") or k.startswith(f"{leave_date}_PM")
                    for k in other_keys_on_same_date
                ):  # FULL_DAY conflicts with an AM or PM already added
                    validation_errors.append(f"{leave_date}: cannot combine FULL_DAY with a HALF_DAY entry on the same date")
                elif duration_type == "HALF_DAY" and f"{leave_date}_FULL" in seen_period_keys:  # HALF_DAY added after a FULL_DAY
                    validation_errors.append(f"{leave_date}: cannot combine FULL_DAY with a HALF_DAY entry on the same date")

            if validation_errors:  # format/logic errors — return all at once
                return {"statusCode": 400, "message": "Validation failed", "errors": validation_errors}

            # --- Step 3: validate holiday conflicts ---
            holiday_errors = LeaveApplication._validate_holidays(dates)  # check each date against calendar_events

            # --- Step 4: validate overlaps with existing leaves ---
            overlap_errors = LeaveApplication._validate_overlaps(data["employee_id"], dates)  # check DB for conflicts

            all_errors = holiday_errors + overlap_errors  # combine both error lists
            if all_errors:  # at least one conflict found — return all errors together
                return {"statusCode": 400, "message": "Leave date conflicts detected", "errors": all_errors}

            # --- Step 5: verify employee and leave type ---
            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [data["employee_id"]]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}

            leave_type = fetch_query(  # fetch leave type rules
                "SELECT id, code, name, balance_type, is_active FROM leave_types WHERE id = %s",
                [data["leave_type_id"]]
            )
            if not leave_type:  # leave type not found
                return {"statusCode": 404, "message": "Leave type not found"}
            if not leave_type[0]["is_active"]:  # leave type is disabled
                return {"statusCode": 400, "message": f"{leave_type[0]['name']} is no longer active"}

            # --- Step 6: calculate total days and derive start date ---
            total_days = LeaveApplication._calculate_total_days(dates)  # sum from dates array
            min_date = min(d["leave_date"] for d in dates)  # earliest leave date for ledger transaction_date

            # --- Step 7: check balance ---
            balance_error = LeaveApplication._check_balance(data["employee_id"], leave_type[0], total_days)
            if balance_error:  # insufficient balance — return the error
                return balance_error

            # --- Step 8: insert application header ---
            application_number = LeaveApplication._generate_application_number()  # generate unique number

            result = query_insert(  # insert the leave application
                """INSERT INTO leave_applications
                       (application_number, employee_id, leave_type_id, date_filed,
                        reason, other_leave_description, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'FOR HRMO ACTION')""",
                [
                    application_number,                   # generated application number
                    data["employee_id"],                  # employee submitting the application
                    data["leave_type_id"],                # leave type requested
                    data["date_filed"],                   # date filed
                    data["reason"],                       # reason for leave
                    data.get("other_leave_description"),  # extra description for Others type
                ]
            )
            if result["statusCode"] != 200:  # insert failed
                return result

            application_id = result["insertId"]  # the new application's primary key

            # --- Step 9: insert each leave date ---
            for entry in dates:  # iterate normalised date entries
                date_result = query_insert(  # insert one row per leave date
                    """INSERT INTO leave_application_dates
                           (leave_application_id, leave_date, duration_type, half_day_period, is_paid)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [
                        application_id,             # FK to the application just created
                        entry["leave_date"],         # the specific leave date
                        entry["duration_type"],      # FULL_DAY or HALF_DAY
                        entry["half_day_period"],    # AM, PM, or None
                        1 if entry["is_paid"] else 0,  # convert bool to tinyint
                    ]
                )
                if date_result["statusCode"] != 200:  # date insert failed
                    return date_result

            # --- Step 10: post balance debit ---
            debit_error = LeaveApplication._post_debit(  # deduct balance immediately on submission
                employee_id=data["employee_id"],
                leave_type_id=data["leave_type_id"],
                leave_type_code=leave_type[0]["code"],
                balance_type=leave_type[0]["balance_type"],
                total_days=total_days,
                application_id=application_id,
                start_date=min_date,  # use earliest leave date as ledger transaction_date
            )
            if debit_error:  # debit posting failed
                return debit_error

            # --- Step 11: fetch and return the created application ---
            application = fetch_query(  # fetch the full created application record
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s""",
                [application_id]
            )

            if application:  # enrich with dates before returning
                enriched = LeaveApplication._enrich_with_dates(application)
                return {
                    "statusCode": 201,
                    "message": "Leave application submitted successfully",
                    "data": enriched[0],
                }

            return {"statusCode": 201, "message": "Leave application submitted successfully"}

        except ValueError as e:  # catch invalid date format errors
            return {"statusCode": 400, "message": f"Invalid date format: {str(e)}"}
        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get leave application by ID
    # --------------------------

    @staticmethod
    def get_by_id(application_id: int) -> dict:
        """
        Retrieves a single leave application by its primary key with joined employee,
        leave type info, individual leave dates, and derived start/end/total_days.

        Parameters:
            application_id (int): The primary key of the application to fetch.

        Returns:
            dict: statusCode 200 with the application data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the application with joined details
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s AND la.is_deleted = 0""",
                [application_id]
            )

            if not rows:  # not found
                return {"statusCode": 404, "message": f"Leave application {application_id} not found"}

            enriched = LeaveApplication._enrich_with_dates(rows)  # attach dates and derived fields
            return {"statusCode": 200, "data": enriched[0]}  # return single record

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get all leave applications by employee
    # --------------------------

    @staticmethod
    def get_by_employee(employee_id: int) -> dict:
        """
        Retrieves all leave applications submitted by a specific employee (excluding CTO/VSC),
        ordered by date filed descending. Each application includes its leave dates.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with a list of applications, or 404 if none found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}

            rows = fetch_query(  # fetch all non-CTO/VSC applications for the employee
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.employee_id = %s
                     AND lt.code NOT IN ('CTO', 'VSC')
                     AND la.is_deleted = 0
                   ORDER BY la.date_filed DESC""",
                [employee_id]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields

            if not enriched:  # no applications found
                return {"statusCode": 404, "message": "No leave applications found for this employee"}

            return {"statusCode": 200, "count": len(enriched), "data": enriched}

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get leave applications by employee and year (with ledger)
    # --------------------------

    @staticmethod
    def get_by_employee_and_year(employee_id: int, year: int) -> dict:
        """
        Retrieves all leave applications for a specific employee in a given calendar year,
        each enriched with individual leave dates, a computed deduction, and a running
        balance_after that behaves like an Excel ledger column — reversals zero out
        the deduction and cascade the correction forward to all subsequent rows.

        Parameters:
            employee_id (int): The employee's primary key.
            year (int): The calendar year to filter by (e.g. 2026).

        Returns:
            dict: statusCode 200 with a list of applications (ASC by date) each containing
                  deduction and balance_after fields, or 404 if the employee is not found.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id, first_name, last_name, employee_number FROM employees WHERE id = %s",
                [employee_id]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}

            rows = fetch_query(  # fetch non-CTO/VSC applications in chronological order for running balance
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name, lt.balance_type
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.employee_id = %s
                     AND YEAR(la.date_filed) = %s
                     AND lt.code NOT IN ('CTO', 'VSC')
                     AND la.is_deleted = 0
                   ORDER BY la.date_filed ASC, la.id ASC""",
                [employee_id, year]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields

            # Query total refunded days per application from leave_refunded_dates
            all_app_ids = [app["id"] for app in enriched]  # collect all app IDs for this year
            refunded_per_app = {}  # app_id -> total holiday-refunded days
            if all_app_ids:  # only query if there are applications
                app_placeholders = ", ".join(["%s"] * len(all_app_ids))  # build IN clause
                refund_rows = fetch_query(  # sum refunded amounts grouped by application
                    f"""SELECT leave_application_id, SUM(amount_refunded) AS total_refunded
                        FROM leave_refunded_dates
                        WHERE leave_application_id IN ({app_placeholders})
                        GROUP BY leave_application_id""",
                    all_app_ids
                )
                for r in (refund_rows or []):  # build lookup dict from the result
                    refunded_per_app[r["leave_application_id"]] = float(r["total_refunded"])

            for app in enriched:  # attach refunded_days and effective_days to each app
                app["refunded_days"] = round(refunded_per_app.get(app["id"], 0.0), 4)  # total days credited back by holiday refunds
                app["effective_days"] = round(max(0.0, float(app["total_days"] or 0.0) - app["refunded_days"]), 4)  # net days actually charged after holiday refunds

            REVERSED_STATUSES = {"RETURNED", "DISAPPROVED"}  # statuses where the deduction was already restored

            # Resolve VL, SL, and VSC type IDs — VL/SL are always shown; VSC is needed for CHARGED_TO_VSC (PR) apps
            vl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VL'", [])  # look up VL type
            vl_leave_type_id = vl_type[0]["id"] if vl_type else None  # store VL id or None if not found
            sl_type = fetch_query("SELECT id FROM leave_types WHERE code = 'SL'", [])  # look up SL type
            sl_leave_type_id = sl_type[0]["id"] if sl_type else None  # store SL id or None if not found
            vsc_type = fetch_query("SELECT id FROM leave_types WHERE code = 'VSC'", [])  # look up VSC type
            vsc_leave_type_id = vsc_type[0]["id"] if vsc_type else None  # store VSC id or None if not found

            # Determine which SL apps used VSC credits (those deduct from VSC, not SL balance)
            sl_app_ids = [app["id"] for app in enriched if app["leave_type_code"] == "SL"]  # collect SL app IDs
            vsc_funded_sl = set()  # set of SL app IDs that deducted from VSC
            if sl_app_ids:  # only query if there are SL apps this year
                sl_placeholders = ", ".join(["%s"] * len(sl_app_ids))  # build IN clause
                vsc_log_rows = fetch_query(  # check which SL apps have a vsc_deduction_log entry
                    f"SELECT DISTINCT leave_application_id FROM vsc_deduction_log WHERE leave_application_id IN ({sl_placeholders})",
                    sl_app_ids
                )
                vsc_funded_sl = {row["leave_application_id"] for row in (vsc_log_rows or [])}  # IDs that used VSC

            # Map each application to its effective leave_type_id for balance tracking
            # SELF(CTO/SL-via-VSC)→ VSC/CTO id | SELF(SL/VL/etc.) → own id | CHARGED_TO_VL → VL | CHARGED_TO_VSC → VSC | NONE → None
            effective_type_map = {}  # app_id -> effective leave_type_id or None
            for app in enriched:  # iterate to build the map
                if app["balance_type"] == "NONE":  # no balance deducted for this leave type
                    effective_type_map[app["id"]] = None  # skip balance tracking
                elif app["balance_type"] == "CHARGED_TO_VL":  # FL — VL is the actual balance affected
                    effective_type_map[app["id"]] = vl_leave_type_id  # track VL running balance
                elif app["balance_type"] == "CHARGED_TO_VSC":  # PR — VSC is the actual balance affected
                    effective_type_map[app["id"]] = vsc_leave_type_id  # track VSC running balance
                elif app["leave_type_code"] == "SL" and app["id"] in vsc_funded_sl:  # SL funded by VSC — VSC balance changes, not SL
                    effective_type_map[app["id"]] = vsc_leave_type_id  # track VSC running balance
                else:  # SELF — leave type's own balance is affected
                    effective_type_map[app["id"]] = app["leave_type_id"]  # track own balance

            # Collect the unique effective leave type IDs that need a balance lookup
            unique_eff_types = {v for v in effective_type_map.values() if v is not None}  # skip None entries
            if vl_leave_type_id:  # always include VL — must appear in the leave card VL column even if no VL apps
                unique_eff_types.add(vl_leave_type_id)
            if sl_leave_type_id:  # always include SL — must appear in the leave card SL column even if no SL apps
                unique_eff_types.add(sl_leave_type_id)

            # Fetch current cached balance for each unique effective leave type
            current_balances = {}  # leave_type_id -> current balance float
            for lt_id in unique_eff_types:  # one query per unique effective type
                bal_rows = fetch_query(  # read from the cached balance table
                    "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                    [employee_id, lt_id]
                )
                current_balances[lt_id] = float(bal_rows[0]["balance"]) if bal_rows else 0.0  # default to 0

            # Compute the sum of active (non-reversed) days this year per effective type
            # Used to back-calculate the balance at the very start of this year
            active_sums = {lt_id: 0.0 for lt_id in unique_eff_types}  # initialise to zero per type
            for app in enriched:  # accumulate active deductions for each effective type
                eff_type = effective_type_map[app["id"]]  # get this app's effective type
                if eff_type is None:  # NONE type — check for MNT which splits across VL and SL
                    if app.get("leave_type_code") == "MNT" and app["status"] not in REVERSED_STATUSES:  # MNT deducts from VL and SL separately
                        mnt_vl = float(app.get("mnt_vl_days") or 0)  # VL portion of this monetization
                        mnt_sl = float(app.get("mnt_sl_days") or 0)  # SL portion of this monetization
                        if vl_leave_type_id and mnt_vl > 0:  # add VL days to VL active sum
                            active_sums[vl_leave_type_id] = active_sums.get(vl_leave_type_id, 0.0) + mnt_vl
                        if sl_leave_type_id and mnt_sl > 0:  # add SL days to SL active sum
                            active_sums[sl_leave_type_id] = active_sums.get(sl_leave_type_id, 0.0) + mnt_sl
                    continue  # no single effective type balance to track
                if app["status"] not in REVERSED_STATUSES:  # only active apps reduced the balance
                    active_sums[eff_type] += app["effective_days"]  # use net days after holiday refunds

            # Fetch non-leave-app credits (monthly, manual, system) for this year per effective type
            # These must be interleaved with apps so credits only count from their transaction date onward
            year_credits_by_type = {}  # lt_id -> list of {amount, date} in chronological order
            for lt_id in unique_eff_types:  # one query per unique effective type
                credit_rows = fetch_query(  # only CREDIT rows; exclude HOLIDAY_REFUND (baked into effective_days) and MONETIZATION DEBITs
                    """SELECT amount, transaction_date
                       FROM leave_credit_transactions
                       WHERE employee_id = %s AND leave_type_id = %s
                         AND YEAR(transaction_date) = %s
                         AND transaction_type = 'CREDIT'
                         AND source_type NOT IN ('LEAVE_APPLICATION', 'HOLIDAY_REFUND')
                       ORDER BY transaction_date ASC, id ASC""",
                    [employee_id, lt_id, year]
                )
                year_credits_by_type[lt_id] = [  # normalise to plain dicts with string dates
                    {"amount": float(r["amount"]), "date": str(r["transaction_date"])}
                    for r in (credit_rows or [])
                ]

            # Sum all non-leave-app credits posted in this year per effective type
            year_credit_sums = {
                lt_id: sum(c["amount"] for c in year_credits_by_type[lt_id])
                for lt_id in unique_eff_types
            }

            # balance_forwarded = the balance each type carried INTO this year (before any this-year transactions)
            # Derivation: current_balance = all_credits_ever - all_active_debits_ever
            #             balance_forwarded = current_balance + active_this_year - credits_this_year
            running_balances = {  # mutable running total per effective type; starts at balance_forwarded
                lt_id: current_balances[lt_id] + active_sums[lt_id] - year_credit_sums[lt_id]
                for lt_id in unique_eff_types
            }

            # Build a merged timeline of credit events and leave-app events, then sort chronologically
            # Credits use transaction_date; apps use start_date (first leave day) so they land at the right month
            timeline = []  # list of event dicts to process in date order

            for lt_id in unique_eff_types:  # add all credit events for each effective type
                for credit in year_credits_by_type[lt_id]:  # each non-leave-app credit transaction
                    timeline.append({
                        "lt_id": lt_id,          # which effective type this credit affects
                        "date": credit["date"],   # credit transaction_date (YYYY-MM-DD string)
                        "is_credit": True,        # flag: this event adds to the running balance
                        "amount": credit["amount"],  # amount credited
                        "app": None,              # no application for credit events
                    })

            for app in enriched:  # add ALL leave-application events including NONE-type — needed for VL/SL snapshot
                eff_type = effective_type_map[app["id"]]  # effective type for balance tracking (None for NONE types)
                sort_date = str(app["date_filed"])  # sort by filing date to match display and leave card recording order
                timeline.append({
                    "lt_id": eff_type,              # effective leave type this app deducts from (None = no deduction)
                    "date": sort_date,              # chronological position in the leave card
                    "is_credit": False,             # flag: this event may reduce the running balance
                    "amount": app["effective_days"],  # net days after holiday refunds (0 if fully refunded)
                    "app": app,                     # reference to the application dict for updating balance_after
                })

            # Sort chronologically; credits land BEFORE apps on the same date
            # (month-end credits must be available before same-date leave applications are processed)
            timeline.sort(key=lambda e: (e["date"], 0 if e["is_credit"] else 1))

            # Walk the timeline and assign deduction + balance_after + vl/sl snapshots to each app event
            for event in timeline:  # process each event in chronological order
                lt_id = event["lt_id"]  # effective leave type for this event
                if event["is_credit"]:  # credit event: increase the running balance
                    running_balances[lt_id] += event["amount"]  # apply the credit
                else:  # leave-app event: optionally deduct from running balance
                    app = event["app"]  # the application being processed
                    total_days = event["amount"]  # days requested
                    if lt_id is None:  # NONE balance type — MNT splits deduction across VL and SL
                        if app.get("leave_type_code") == "MNT" and app["status"] not in REVERSED_STATUSES:  # active MNT: apply VL/SL deductions now
                            mnt_vl = float(app.get("mnt_vl_days") or 0)  # VL portion
                            mnt_sl = float(app.get("mnt_sl_days") or 0)  # SL portion
                            if vl_leave_type_id and mnt_vl > 0:  # decrement VL running balance
                                running_balances[vl_leave_type_id] -= mnt_vl
                            if sl_leave_type_id and mnt_sl > 0:  # decrement SL running balance
                                running_balances[sl_leave_type_id] -= mnt_sl
                        app["deduction"] = -total_days if app["status"] not in REVERSED_STATUSES else 0.0  # negative days or 0 if reversed
                        app["balance_after"] = None  # no single balance column for MNT
                    elif app["status"] in REVERSED_STATUSES:  # reversed: balance already restored, no deduction
                        app["deduction"] = 0.0  # zero deduction shown on the leave card
                        app["balance_after"] = round(running_balances[lt_id], 4)  # balance unchanged
                    else:  # active application: deduct from the running total
                        running_balances[lt_id] -= total_days  # apply the deduction
                        app["deduction"] = -total_days  # negative = days consumed
                        app["balance_after"] = round(running_balances[lt_id], 4)  # snapshot after deduction
                    # Always include VL and SL column snapshots regardless of this application's leave type
                    app["vl_balance_after"] = round(running_balances.get(vl_leave_type_id, 0.0), 4) if vl_leave_type_id else None  # current VL balance at this point in the leave card
                    app["sl_balance_after"] = round(running_balances.get(sl_leave_type_id, 0.0), 4) if sl_leave_type_id else None  # current SL balance at this point in the leave card

            return {
                "statusCode": 200,
                "employee": employee[0],  # basic employee info for context
                "year": year,             # the year filter applied
                "count": len(enriched),   # total applications returned
                "data": enriched,         # applications in date_filed ASC order
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get leave application by application number
    # --------------------------

    @staticmethod
    def get_by_application_number(application_number: str) -> dict:
        """
        Retrieves a single leave application by its unique application number.

        Parameters:
            application_number (str): The application number (e.g. 'LA-A1B2C3D4').

        Returns:
            dict: statusCode 200 with the application data, or 404 if not found.
        """
        try:
            rows = fetch_query(  # fetch the application matching the application number
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.application_number = %s AND la.is_deleted = 0""",
                [application_number]
            )

            if not rows:  # no match found
                return {"statusCode": 404, "message": f"Leave application '{application_number}' not found"}

            enriched = LeaveApplication._enrich_with_dates(rows)  # attach dates and derived fields
            return {"statusCode": 200, "data": enriched[0]}

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Search leave applications (paginated)
    # --------------------------

    @staticmethod
    def search(filters: dict, page: int = 1, limit: int = 10) -> dict:
        """
        Searches leave applications using optional filters with pagination.
        All filters are optional and combinable. Results are ordered by date_filed DESC.
        Supported filters: year (of date_filed), date_from, date_to, status, leave_type_code.

        Parameters:
            filters (dict): Optional filter keys — year, date_from, date_to, status, leave_type_code.
            page (int): Page number (default 1).
            limit (int): Records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated results and applied filters, or an error dict.
        """
        try:
            valid_statuses = ("FOR HRMO ACTION", "FOR APPROVAL", "RETURNED", "DISAPPROVED", "APPROVED")

            if filters.get("status") and filters["status"] not in valid_statuses:  # validate status value if provided
                return {
                    "statusCode": 400,
                    "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                }

            conditions = ["lt.code NOT IN ('CTO', 'VSC')", "la.is_deleted = 0"]  # always exclude CTO/VSC and soft-deleted
            params = []  # bound parameter values matching each placeholder

            if filters.get("year"):  # filter by calendar year of date_filed
                conditions.append("YEAR(la.date_filed) = %s")
                params.append(filters["year"])

            if filters.get("date_from"):  # filter by lower bound of date_filed range
                conditions.append("la.date_filed >= %s")
                params.append(filters["date_from"])

            if filters.get("date_to"):  # filter by upper bound of date_filed range
                conditions.append("la.date_filed <= %s")
                params.append(filters["date_to"])

            if filters.get("status"):  # filter by application status
                conditions.append("la.status = %s")
                params.append(filters["status"])

            if filters.get("leave_type_code"):  # filter by leave type code
                conditions.append("lt.code = %s")
                params.append(filters["leave_type_code"].upper())

            where_clause = "WHERE " + " AND ".join(conditions)  # always has at least the CTO/VSC exclusion

            count_row = fetch_query(  # get total matching records for pagination metadata
                f"""SELECT COUNT(*) AS total
                    FROM leave_applications la
                    JOIN leave_types lt ON lt.id = la.leave_type_id
                    JOIN employees e ON e.id = la.employee_id
                    {where_clause}""",
                params
            )

            total = count_row[0]["total"] if count_row else 0  # extract total count
            offset = (page - 1) * limit  # calculate row offset for the requested page

            rows = fetch_query(  # fetch the paginated matching applications
                f"""SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                           e.first_name, e.last_name, e.employee_number
                    FROM leave_applications la
                    JOIN leave_types lt ON lt.id = la.leave_type_id
                    JOIN employees e ON e.id = la.employee_id
                    {where_clause}
                    ORDER BY la.date_filed DESC, la.id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields
            active_filters = {k: v for k, v in filters.items() if v is not None}  # strip None values

            return {
                "statusCode": 200,
                "count": len(enriched),
                "total": total,
                "page": page,
                "limit": limit,
                "filters": active_filters,
                "data": enriched,
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get all leave applications including CTO/VSC (paginated)
    # --------------------------

    @staticmethod
    def get_all_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of ALL leave applications across all employees and
        all leave types (including CTO and VSC), ordered by date filed descending.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated leave application data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get total count across all leave types excluding soft-deleted
                "SELECT COUNT(*) AS total FROM leave_applications WHERE is_deleted = 0", []
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated applications including CTO and VSC
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.is_deleted = 0
                   ORDER BY la.date_filed DESC, la.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields

            return {
                "statusCode": 200,
                "count": len(enriched),
                "total": total,
                "page": page,
                "limit": limit,
                "data": enriched,
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get all CTO/VSC leave applications (paginated)
    # --------------------------

    @staticmethod
    def get_cto_vsc_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of CTO and VSC leave applications only,
        ordered by date filed descending.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated CTO/VSC leave application data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get count of CTO and VSC leave applications only
                """SELECT COUNT(*) AS total
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE lt.code IN ('CTO', 'VSC') AND la.is_deleted = 0""",
                []
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated CTO/VSC applications
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE lt.code IN ('CTO', 'VSC') AND la.is_deleted = 0
                   ORDER BY la.date_filed DESC, la.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields

            return {
                "statusCode": 200,
                "count": len(enriched),
                "total": total,
                "page": page,
                "limit": limit,
                "data": enriched,
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get CTO/VSC leave applications by employee
    # --------------------------

    @staticmethod
    def get_cto_vsc_by_employee(employee_id: int) -> dict:
        """
        Retrieves all CTO and VSC leave applications submitted by a specific employee,
        ordered by date filed descending.

        Parameters:
            employee_id (int): The employee's primary key.

        Returns:
            dict: statusCode 200 with a list of CTO/VSC applications.
        """
        try:
            employee = fetch_query(  # verify the employee exists
                "SELECT id FROM employees WHERE id = %s", [employee_id]
            )
            if not employee:  # employee not found
                return {"statusCode": 404, "message": "Employee not found"}

            rows = fetch_query(  # fetch all CTO/VSC applications for the employee
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.employee_id = %s
                     AND lt.code IN ('CTO', 'VSC')
                     AND la.is_deleted = 0
                   ORDER BY la.date_filed DESC""",
                [employee_id]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields

            return {"statusCode": 200, "count": len(enriched), "data": enriched}

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Update leave application dates
    # --------------------------

    @staticmethod
    def update(application_id: int, data: dict) -> dict:
        """
        Replaces the leave dates on an existing leave application.
        Only applications with status 'FOR HRMO ACTION' can be edited.
        The old debit is reversed and a new debit is posted for the updated total.
        Holiday conflicts, overlaps (excluding this application), and balance
        (simulated post-reversal) are all validated before any writes occur.

        Parameters:
            application_id (int): Primary key of the leave application to edit.
            data (dict): Must contain dates — a list of leave date dicts each with
                         leave_date, duration_type, half_day_period, is_paid.

        Returns:
            dict: statusCode 200 with the updated application data, or an error dict.
        """
        try:
            # --- Step 1: fetch application and old computed totals ---
            application = fetch_query(  # get application row with leave type rules and old totals via subqueries
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          lt.balance_type, lt.is_active,
                          (SELECT SUM(CASE WHEN lad.duration_type = 'FULL_DAY' THEN 1.0 ELSE 0.5 END)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS old_total_days,
                          (SELECT DATE_FORMAT(MIN(lad.leave_date), '%%Y-%%m-%%d')
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS old_start_date
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.id = %s AND la.is_deleted = 0""",
                [application_id]
            )

            if not application:  # application does not exist or is soft-deleted
                return {"statusCode": 404, "message": "Leave application not found"}

            app = application[0]  # shorthand for the application row

            if app["status"] != "FOR HRMO ACTION":  # only editable before any approval action
                return {
                    "statusCode": 400,
                    "message": f"Only applications with status 'FOR HRMO ACTION' can be edited. Current status: {app['status']}",
                }

            # --- Step 2: validate and normalise new dates ---
            dates = data.get("dates")  # read the incoming dates list

            if not isinstance(dates, list) or len(dates) == 0:  # must be a non-empty list
                return {"statusCode": 400, "message": "At least one leave date is required in dates[]"}

            VALID_DURATION_TYPES = ("FULL_DAY", "HALF_DAY")  # accepted duration_type values
            VALID_PERIODS = ("AM", "PM")  # accepted half_day_period values
            validation_errors = []  # accumulate format/logic errors
            seen_period_keys = set()  # track (date, period) combos to detect duplicates within this submission

            for i, entry in enumerate(dates):  # iterate each submitted date
                leave_date = (entry.get("leave_date") or "").strip()  # read and trim date string
                duration_type = (entry.get("duration_type") or "").strip().upper()  # normalise to uppercase
                raw_period = entry.get("half_day_period")  # may be None
                half_day_period = (raw_period or "").strip().upper() or None  # normalise or None

                if not leave_date:  # date string is missing or blank
                    validation_errors.append(f"dates[{i}]: leave_date is required")
                    continue  # skip further checks for this entry

                if duration_type not in VALID_DURATION_TYPES:  # unrecognised duration type
                    validation_errors.append(f"{leave_date}: duration_type must be FULL_DAY or HALF_DAY")
                    continue

                if duration_type == "HALF_DAY" and (not half_day_period or half_day_period not in VALID_PERIODS):  # HALF_DAY needs a period
                    validation_errors.append(f"{leave_date}: half_day_period (AM or PM) is required for HALF_DAY")
                    continue

                entry["leave_date"] = leave_date  # trimmed date string
                entry["duration_type"] = duration_type  # uppercase
                entry["half_day_period"] = half_day_period if duration_type == "HALF_DAY" else None  # None for FULL_DAY
                entry["is_paid"] = bool(entry.get("is_paid", True))  # default to paid

                period_key = f"{leave_date}_{'FULL' if duration_type == 'FULL_DAY' else half_day_period}"  # unique key per slot
                if period_key in seen_period_keys:  # duplicate slot in this payload
                    validation_errors.append(f"{leave_date}: duplicate leave date/period in this submission")
                else:
                    seen_period_keys.add(period_key)  # mark as seen

                other_keys_on_same_date = [k for k in seen_period_keys if k.startswith(f"{leave_date}_") and k != period_key]
                if duration_type == "FULL_DAY" and any(
                    k.startswith(f"{leave_date}_AM") or k.startswith(f"{leave_date}_PM")
                    for k in other_keys_on_same_date
                ):  # FULL_DAY conflicts with an AM or PM already added
                    validation_errors.append(f"{leave_date}: cannot combine FULL_DAY with a HALF_DAY entry on the same date")
                elif duration_type == "HALF_DAY" and f"{leave_date}_FULL" in seen_period_keys:  # HALF_DAY added after a FULL_DAY
                    validation_errors.append(f"{leave_date}: cannot combine FULL_DAY with a HALF_DAY entry on the same date")

            if validation_errors:  # format/logic errors — return all at once
                return {"statusCode": 400, "message": "Validation failed", "errors": validation_errors}

            # --- Step 3: validate holiday conflicts ---
            holiday_errors = LeaveApplication._validate_holidays(dates)  # check each date against calendar_events

            # --- Step 4: validate overlaps, excluding this application ---
            overlap_errors = LeaveApplication._validate_overlaps(
                app["employee_id"], dates, exclude_application_id=application_id
            )  # skip the application being edited so its own old dates don't cause false conflicts

            all_errors = holiday_errors + overlap_errors  # combine both error lists
            if all_errors:  # at least one conflict — return all errors together
                return {"statusCode": 400, "message": "Leave date conflicts detected", "errors": all_errors}

            # --- Step 5: calculate new totals and recover old values ---
            new_total = LeaveApplication._calculate_total_days(dates)  # sum from new dates array
            new_min_date = min(d["leave_date"] for d in dates)  # earliest new leave date for ledger ordering

            old_total = float(app["old_total_days"] or 0.0)  # cast Decimal to float
            old_start_date = str(app["old_start_date"]) if app["old_start_date"] else new_min_date  # use new date as fallback

            balance_type = app["balance_type"]  # SELF, CHARGED_TO_VL, or NONE
            leave_type_code = app["leave_type_code"]  # VL, SL, FL, CTO, etc.

            # --- Step 6: pre-check balance simulating state after reversal ---
            # Effective available = current balance + old deducted amount (what it will be after reversal)
            if balance_type == "SELF" and leave_type_code != "CTO":  # standard self-funded leave type
                available = LeaveApplication._get_balance(app["employee_id"], leave_type_code)  # current cache
                effective = round(available + old_total, 2)  # balance after old debit is reversed
                if effective < new_total:  # not enough even after recovering old days
                    return {
                        "statusCode": 400,
                        "message": f"Insufficient {leave_type_code} balance",
                        "leave_type_checked": leave_type_code,
                        "required_days": new_total,
                        "available_days": effective,
                        "shortfall_days": round(new_total - effective, 2),
                    }

            elif balance_type == "SELF" and leave_type_code == "CTO":  # CTO uses per-credit balance tracking
                cto_row = fetch_query(  # sum all remaining CTO credits for this employee
                    "SELECT COALESCE(SUM(remaining_balance), 0) AS total FROM cto_credit_balances WHERE employee_id = %s AND remaining_balance > 0",
                    [app["employee_id"]]
                )
                cto_available = float(cto_row[0]["total"]) if cto_row else 0.0  # current remaining across all credits
                old_cto_row = fetch_query(  # sum all amounts previously deducted by this application
                    "SELECT COALESCE(SUM(amount_deducted), 0) AS total FROM cto_deduction_log WHERE leave_application_id = %s",
                    [application_id]
                )
                old_cto_deducted = float(old_cto_row[0]["total"]) if old_cto_row else 0.0  # previously deducted amount
                effective_cto = round(cto_available + old_cto_deducted, 2)  # balance after old deductions are restored
                if effective_cto < new_total:  # not enough CTO credit
                    return {
                        "statusCode": 400,
                        "message": "Insufficient CTO balance",
                        "leave_type_checked": "CTO",
                        "required_days": new_total,
                        "available_days": effective_cto,
                        "shortfall_days": round(new_total - effective_cto, 2),
                    }

            elif balance_type == "CHARGED_TO_VL":  # FL — both FL entitlement and VL balance are affected
                fl_available = LeaveApplication._get_balance(app["employee_id"], leave_type_code)  # current FL balance
                vl_available = LeaveApplication._get_balance(app["employee_id"], "VL")  # current VL balance
                effective_fl = round(fl_available + old_total, 2)  # FL after reversal
                effective_vl = round(vl_available + old_total, 2)  # VL after reversal
                balance_errors = []  # collect insufficiency details
                if effective_fl < new_total:  # FL entitlement not enough
                    balance_errors.append({
                        "leave_type_checked": leave_type_code,
                        "required_days": new_total,
                        "available_days": effective_fl,
                        "shortfall_days": round(new_total - effective_fl, 2),
                    })
                if effective_vl < new_total:  # VL not enough to cover FL charge
                    balance_errors.append({
                        "leave_type_checked": "VL",
                        "required_days": new_total,
                        "available_days": effective_vl,
                        "shortfall_days": round(new_total - effective_vl, 2),
                    })
                if balance_errors:  # at least one balance check failed
                    return {
                        "statusCode": 400,
                        "message": f"Insufficient balance for {leave_type_code} update.",
                        "insufficient_balances": balance_errors,
                    }

            # --- Step 7: reverse the old debit ---
            from model.leave_approval import LeaveApproval  # local import to avoid circular dependency at module load
            reversal_error = LeaveApproval._post_reversal(  # post CREDIT entries cancelling the old DEBIT
                employee_id=app["employee_id"],
                leave_type_id=app["leave_type_id"],
                leave_type_code=leave_type_code,
                balance_type=balance_type,
                total_days=old_total,
                application_id=application_id,
                start_date=old_start_date,
            )
            if reversal_error:  # reversal failed — return early
                return reversal_error

            # --- Step 8: delete old leave date records ---
            query(  # remove all existing date rows for this application
                "DELETE FROM leave_application_dates WHERE leave_application_id = %s",
                [application_id]
            )

            # --- Step 9: insert new leave date records ---
            for entry in dates:  # iterate the validated and normalised new date entries
                date_result = query_insert(  # insert one row per leave date
                    """INSERT INTO leave_application_dates
                           (leave_application_id, leave_date, duration_type, half_day_period, is_paid)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [
                        application_id,              # FK to this application
                        entry["leave_date"],          # the specific leave date
                        entry["duration_type"],       # FULL_DAY or HALF_DAY
                        entry["half_day_period"],     # AM, PM, or None
                        1 if entry["is_paid"] else 0, # convert bool to tinyint
                    ]
                )
                if date_result["statusCode"] != 200:  # date insert failed
                    return date_result

            # --- Step 10: post new debit for updated total ---
            debit_error = LeaveApplication._post_debit(  # deduct new total from balance
                employee_id=app["employee_id"],
                leave_type_id=app["leave_type_id"],
                leave_type_code=leave_type_code,
                balance_type=balance_type,
                total_days=new_total,
                application_id=application_id,
                start_date=new_min_date,  # earliest new leave date for ledger ordering
            )
            if debit_error:  # debit failed
                return debit_error

            # --- Step 11: fetch and return enriched updated application ---
            updated = fetch_query(  # re-fetch the application with all joins
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE la.id = %s""",
                [application_id]
            )

            if updated:  # enrich with new dates before returning
                enriched = LeaveApplication._enrich_with_dates(updated)
                return {
                    "statusCode": 200,
                    "message": "Leave application updated successfully",
                    "data": enriched[0],
                }

            return {"statusCode": 200, "message": "Leave application updated successfully"}

        except ValueError as e:  # catch invalid date format errors
            return {"statusCode": 400, "message": f"Invalid date format: {str(e)}"}
        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Soft-delete a leave application
    # --------------------------

    @staticmethod
    def soft_delete(application_id: int) -> dict:
        """
        Soft-deletes a leave application by setting is_deleted = 1, recording deleted_at
        and deleted_by (the authenticated user). The row is kept in the database for
        recovery but is excluded from all queries and overlap checks.

        Balance reversal rules:
          FOR HRMO ACTION / FOR APPROVAL / APPROVED → balance was deducted; reverse it.
          RETURNED / DISAPPROVED                    → balance already reversed; skip.

        Parameters:
            application_id (int): Primary key of the leave application to soft-delete.

        Returns:
            dict: statusCode 200 on success, or an error dict.
        """
        try:
            application = fetch_query(  # fetch application with leave type rules and computed totals
                """SELECT la.*, lt.code AS leave_type_code, lt.balance_type,
                          (SELECT SUM(CASE WHEN lad.duration_type = 'FULL_DAY' THEN 1.0 ELSE 0.5 END)
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS total_days,
                          (SELECT DATE_FORMAT(MIN(lad.leave_date), '%%Y-%%m-%%d')
                           FROM leave_application_dates lad
                           WHERE lad.leave_application_id = la.id) AS start_date
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE la.id = %s AND la.is_deleted = 0""",
                [application_id]
            )

            if not application:  # not found or already soft-deleted
                return {"statusCode": 404, "message": "Leave application not found"}

            app = application[0]  # shorthand for the application row

            ALREADY_REVERSED = ("RETURNED", "DISAPPROVED")  # statuses where balance was already restored

            if app["status"] not in ALREADY_REVERSED:  # balance was deducted and not yet reversed
                from model.leave_approval import LeaveApproval  # local import to avoid circular dependency
                reversal_error = LeaveApproval._post_reversal(  # restore the employee's balance
                    employee_id=app["employee_id"],
                    leave_type_id=app["leave_type_id"],
                    leave_type_code=app["leave_type_code"],
                    balance_type=app["balance_type"],
                    total_days=float(app["total_days"] or 0.0),  # cast Decimal to float
                    application_id=application_id,
                    start_date=str(app["start_date"]) if app["start_date"] else "",  # use earliest leave date
                )
                if reversal_error:  # reversal failed — return early before marking deleted
                    return reversal_error

            deleted_by = g.current_user.get("user_id")  # read the authenticated user's ID

            query(  # mark the record as soft-deleted with timestamp and actor
                """UPDATE leave_applications
                   SET is_deleted = 1, deleted_at = NOW(), deleted_by = %s
                   WHERE id = %s""",
                [deleted_by, application_id]
            )

            return {  # success response
                "statusCode": 200,
                "message": "Leave application deleted successfully",
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Get all leave applications (paginated)
    # --------------------------

    @staticmethod
    def get_paginated(page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of all leave applications across all employees,
        ordered by date filed descending. Excludes CTO and VSC types.

        Parameters:
            page (int): Page number to retrieve (default 1).
            limit (int): Number of records per page (default 10).

        Returns:
            dict: statusCode 200 with paginated leave application data.
        """
        try:
            offset = (page - 1) * limit  # calculate row offset for the requested page

            total_row = fetch_query(  # get count excluding CTO, VSC, and soft-deleted
                """SELECT COUNT(*) AS total
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   WHERE lt.code NOT IN ('CTO', 'VSC') AND la.is_deleted = 0""",
                []
            )
            total = total_row[0]["total"] if total_row else 0  # extract total count

            rows = fetch_query(  # fetch paginated applications excluding CTO, VSC, and soft-deleted
                """SELECT la.*, lt.code AS leave_type_code, lt.name AS leave_type_name,
                          e.first_name, e.last_name, e.employee_number
                   FROM leave_applications la
                   JOIN leave_types lt ON lt.id = la.leave_type_id
                   JOIN employees e ON e.id = la.employee_id
                   WHERE lt.code NOT IN ('CTO', 'VSC') AND la.is_deleted = 0
                   ORDER BY la.date_filed DESC, la.id DESC
                   LIMIT %s OFFSET %s""",
                [limit, offset]
            )

            enriched = LeaveApplication._enrich_with_dates(rows or [])  # attach dates and derived fields

            return {
                "statusCode": 200,
                "count": len(enriched),
                "total": total,
                "page": page,
                "limit": limit,
                "data": enriched,
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}
