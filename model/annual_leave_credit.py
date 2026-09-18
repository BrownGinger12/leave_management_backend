from gateway.mysql_gateway import fetch_query, query, query_insert, recalculate_ledger_snapshots  # import gateway functions
from datetime import date  # import date to determine the credit year
import uuid  # import uuid to generate transaction numbers


class AnnualLeaveCredit:
    """
    Model for posting annual leave credits on January 1 each year.
    TEACHING employees receive 6 days of Wellness Leave (WL).
    NON_TEACHING employees receive 3 days SPL + 3 days Family Leave (FL).
    All credits are idempotent — running the job more than once in the same year
    is safe because it checks for an existing ANNUAL_CREDIT transaction before posting.
    """

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
    # Post annual credits
    # --------------------------

    @staticmethod
    def post_annual_credits(year: int = None) -> dict:
        """
        Posts annual leave credits for all active employees for the specified year.
        TEACHING: 6 days WL.
        NON_TEACHING: 3 days SPL + 3 days FL.
        Idempotent: skips employees that already received credits for the given year.
        Safe to call multiple times — only posts once per employee per year per leave type.

        Parameters:
            year (int): Calendar year to credit. Defaults to the current year.

        Returns:
            dict: statusCode 200 with credited/skipped counts, or an error dict.
        """
        try:
            if year is None:  # default to the current calendar year if not provided
                year = date.today().year

            credit_date = f"{year}-01-01"  # transaction date is always January 1 of the credit year

            # Resolve required leave type IDs in a single query
            leave_types = fetch_query(  # fetch WL, SPL, and FL leave type IDs
                "SELECT id, code FROM leave_types WHERE code IN ('WL', 'SPL', 'FL') AND is_active = 1", []
            )
            if not leave_types:  # none of the required types exist
                return {"statusCode": 500, "message": "Required leave types (WL, SPL, FL) not found in the system"}

            lt_map = {lt["code"]: lt["id"] for lt in leave_types}  # build code -> id lookup

            for code in ("WL", "SPL", "FL"):  # verify all three types are present and active
                if code not in lt_map:  # missing type
                    return {"statusCode": 500, "message": f"Leave type '{code}' not found or is inactive"}

            wl_id = lt_map["WL"]    # Wellness Leave leave_type_id
            spl_id = lt_map["SPL"]  # Special Privilege Leave leave_type_id
            fl_id = lt_map["FL"]    # Family Leave leave_type_id

            employees = fetch_query(  # fetch all active employees with their classification
                "SELECT id, employee_type FROM employees WHERE is_active = 1", []
            )
            if not employees:  # no active employees to credit
                return {"statusCode": 200, "message": "No active employees found", "credited": 0, "skipped": 0}

            credited = 0   # count of employees who received new credits
            skipped = 0    # count of employees who were already credited this year

            for emp in employees:  # iterate each active employee
                emp_id = emp["id"]              # employee primary key
                emp_type = emp["employee_type"]  # TEACHING or NON_TEACHING

                if emp_type == "TEACHING":  # TEACHING employees receive 6 days WL on Jan 1
                    already = fetch_query(  # idempotency: check for existing WL annual credit this year
                        """SELECT id FROM leave_credit_transactions
                           WHERE employee_id = %s AND leave_type_id = %s
                             AND source_type = 'ANNUAL_CREDIT'
                             AND YEAR(transaction_date) = %s
                             AND transaction_type = 'CREDIT'
                           LIMIT 1""",
                        [emp_id, wl_id, year]
                    )
                    if already:  # WL credit already exists for this year
                        skipped += 1  # skip this employee
                        continue

                    wl_result = query_insert(  # post 6 days WL CREDIT to the ledger
                        """INSERT INTO leave_credit_transactions
                               (transaction_number, employee_id, leave_type_id, transaction_type,
                                amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                           VALUES (%s, %s, %s, 'CREDIT', 6, 'ANNUAL_CREDIT', %s, %s, 0, %s)""",
                        [
                            AnnualLeaveCredit._generate_transaction_number(),  # unique transaction number
                            emp_id,                         # employee being credited
                            wl_id,                          # WL leave type
                            year,                           # source_id = year (no source document)
                            credit_date,                    # transaction date = Jan 1
                            f"Annual WL Credit - {year}",   # audit remark
                        ]
                    )
                    if wl_result["statusCode"] == 200:  # credit insert succeeded
                        recalculate_ledger_snapshots(emp_id, wl_id)  # update WL balance cache
                        credited += 1  # count this employee as credited

                elif emp_type == "NON_TEACHING":  # NON_TEACHING receive 3 days SPL + 3 days FL on Jan 1
                    already = fetch_query(  # idempotency: check for existing SPL annual credit this year
                        """SELECT id FROM leave_credit_transactions
                           WHERE employee_id = %s AND leave_type_id = %s
                             AND source_type = 'ANNUAL_CREDIT'
                             AND YEAR(transaction_date) = %s
                             AND transaction_type = 'CREDIT'
                           LIMIT 1""",
                        [emp_id, spl_id, year]
                    )
                    if already:  # SPL credit already exists — both SPL and FL were posted together
                        skipped += 1  # skip this employee
                        continue

                    spl_result = query_insert(  # post 3 days SPL CREDIT to the ledger
                        """INSERT INTO leave_credit_transactions
                               (transaction_number, employee_id, leave_type_id, transaction_type,
                                amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                           VALUES (%s, %s, %s, 'CREDIT', 3, 'ANNUAL_CREDIT', %s, %s, 0, %s)""",
                        [
                            AnnualLeaveCredit._generate_transaction_number(),  # unique transaction number
                            emp_id,                          # employee being credited
                            spl_id,                          # SPL leave type
                            year,                            # source_id = year
                            credit_date,                     # transaction date = Jan 1
                            f"Annual SPL Credit - {year}",   # audit remark
                        ]
                    )
                    if spl_result["statusCode"] == 200:  # SPL insert succeeded
                        recalculate_ledger_snapshots(emp_id, spl_id)  # update SPL balance cache

                    fl_result = query_insert(  # post 3 days FL CREDIT to the ledger
                        """INSERT INTO leave_credit_transactions
                               (transaction_number, employee_id, leave_type_id, transaction_type,
                                amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                           VALUES (%s, %s, %s, 'CREDIT', 3, 'ANNUAL_CREDIT', %s, %s, 0, %s)""",
                        [
                            AnnualLeaveCredit._generate_transaction_number(),  # unique transaction number
                            emp_id,                         # employee being credited
                            fl_id,                          # FL leave type
                            year,                           # source_id = year
                            credit_date,                    # transaction date = Jan 1
                            f"Annual FL Credit - {year}",   # audit remark
                        ]
                    )
                    if fl_result["statusCode"] == 200:  # FL insert succeeded
                        recalculate_ledger_snapshots(emp_id, fl_id)  # update FL balance cache

                    credited += 1  # count this employee as credited

            return {  # return summary of the job run
                "statusCode": 200,
                "message": f"Annual leave credits posted for {year}",
                "year": year,                # the year that was credited
                "credited": credited,        # number of employees who received new credits
                "skipped": skipped,          # number already credited (idempotency guard)
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}  # return 500 with error detail

    # --------------------------
    # Monthly VL + SL credit (1st of every month, NON_TEACHING only)
    # --------------------------

    @staticmethod
    def post_monthly_vl_sl_credits(year: int = None, month: int = None) -> dict:
        """
        Credits 1.25 days of VL and 1.25 days of SL to every active NON_TEACHING employee
        on the 1st of each month. Idempotent — safe to call multiple times; will not
        double-post if a MONTHLY_CREDIT already exists for the given employee, leave type,
        year, and month.

        Parameters:
            year (int): Calendar year. Defaults to the current year.
            month (int): Calendar month (1–12). Defaults to the current month.

        Returns:
            dict: statusCode 200 with credited/skipped counts, or an error dict.
        """
        try:
            today = date.today()  # reference date for defaults
            if year is None:   # default to current year
                year = today.year
            if month is None:  # default to current month
                month = today.month

            credit_date = f"{year}-{month:02d}-01"  # transaction date is the 1st of the month

            # ── Resolve VL and SL leave type IDs ────────────────────────────
            leave_types = fetch_query(  # fetch VL and SL type IDs in one query
                "SELECT id, code FROM leave_types WHERE code IN ('VL', 'SL') AND is_active = 1", []
            )
            if not leave_types:  # required types not found
                return {"statusCode": 500, "message": "VL or SL leave type not found in the system"}

            lt_map = {lt["code"]: lt["id"] for lt in leave_types}  # build code -> id lookup

            for code in ("VL", "SL"):  # verify both types are present
                if code not in lt_map:
                    return {"statusCode": 500, "message": f"Leave type '{code}' not found or inactive"}

            vl_id = lt_map["VL"]  # VL leave type primary key
            sl_id = lt_map["SL"]  # SL leave type primary key

            # ── Fetch all active NON_TEACHING employees ───────────────────────
            employees = fetch_query(  # only NON_TEACHING employees receive monthly VL/SL
                "SELECT id FROM employees WHERE is_active = 1 AND employee_type = 'NON_TEACHING'", []
            )
            if not employees:  # no eligible employees
                return {"statusCode": 200, "message": "No active NON_TEACHING employees found", "credited": 0, "skipped": 0}

            credited = 0  # count of employees who received new credits this run
            skipped  = 0  # count of employees already credited this month (idempotency)

            for emp in employees:  # iterate each eligible employee
                emp_id = emp["id"]  # employee primary key

                # Idempotency: the UNIQUE KEY on monthly_leave_credits (employee, leave_type, year, month)
                # is the authoritative guard — check VL row; if it exists both VL and SL were already posted
                already = fetch_query(  # one check on VL covers both (they are posted together)
                    """SELECT id FROM monthly_leave_credits
                       WHERE employee_id = %s AND leave_type_id = %s
                         AND year = %s AND month = %s
                       LIMIT 1""",
                    [emp_id, vl_id, year, month]
                )
                if already:  # already credited this month — skip
                    skipped += 1
                    continue

                # ── Post VL credit ───────────────────────────────────────────
                vl_result = query_insert(  # insert 1.25 days VL CREDIT into the ledger
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'CREDIT', 1.25, 'MONTHLY_CREDIT', %s, %s, 0, %s)""",
                    [
                        AnnualLeaveCredit._generate_transaction_number(),  # unique TXN number
                        emp_id,                                             # employee being credited
                        vl_id,                                              # VL leave type
                        year,                                               # source_id = year
                        credit_date,                                        # 1st of the month
                        f"Monthly VL Credit — {year}-{month:02d}",         # audit remark
                    ]
                )
                if vl_result["statusCode"] != 200:  # VL insert failed — skip this employee
                    continue
                recalculate_ledger_snapshots(emp_id, vl_id)  # update VL balance cache

                query(  # record VL credit in monthly_leave_credits
                    """INSERT INTO monthly_leave_credits
                           (employee_id, leave_type_id, year, month, amount, transaction_id)
                       VALUES (%s, %s, %s, %s, 1.25, %s)""",
                    [emp_id, vl_id, year, month, vl_result["insertId"]]
                )

                # ── Post SL credit ───────────────────────────────────────────
                sl_result = query_insert(  # insert 1.25 days SL CREDIT into the ledger
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, 'CREDIT', 1.25, 'MONTHLY_CREDIT', %s, %s, 0, %s)""",
                    [
                        AnnualLeaveCredit._generate_transaction_number(),  # unique TXN number
                        emp_id,                                             # employee being credited
                        sl_id,                                              # SL leave type
                        year,                                               # source_id = year
                        credit_date,                                        # 1st of the month
                        f"Monthly SL Credit — {year}-{month:02d}",         # audit remark
                    ]
                )
                if sl_result["statusCode"] == 200:  # SL insert succeeded
                    recalculate_ledger_snapshots(emp_id, sl_id)  # update SL balance cache

                    query(  # record SL credit in monthly_leave_credits
                        """INSERT INTO monthly_leave_credits
                               (employee_id, leave_type_id, year, month, amount, transaction_id)
                           VALUES (%s, %s, %s, %s, 1.25, %s)""",
                        [emp_id, sl_id, year, month, sl_result["insertId"]]
                    )

                credited += 1  # count this employee as credited

            return {  # return summary of the job run
                "statusCode": 200,
                "message": f"Monthly VL/SL credits posted for {year}-{month:02d}",
                "year":     year,      # year processed
                "month":    month,     # month processed
                "credited": credited,  # employees who received new credits
                "skipped":  skipped,   # employees already credited (idempotency)
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}

    # --------------------------
    # Startup catch-up for missed monthly credits
    # --------------------------

    @staticmethod
    def catch_up_monthly_vl_sl_credits() -> None:
        """
        Called once on server startup to credit the previous calendar month if
        the cron job that was supposed to run at month-end was missed while the
        server was down.

        Only the immediately preceding month is checked. The current month is
        not touched — it will be credited by the normal scheduler at month-end.
        Fully idempotent: if the previous month was already credited, the call
        is silently skipped. Errors are swallowed so a failure never prevents
        the server from starting.

        Parameters:
            None

        Returns:
            None
        """
        try:
            today = date.today()  # reference date
            if today.month == 1:  # January — no previous month in this year to catch up
                return
            year  = today.year       # current calendar year
            month = today.month - 1  # the month that may have been missed
            AnnualLeaveCredit.post_monthly_vl_sl_credits(year=year, month=month)  # idempotent — skips if already run
        except Exception:
            pass  # never crash the server on a catch-up failure

    # --------------------------
    # Year-end balance reset (Jan 1)
    # --------------------------

    @staticmethod
    def reset_year_end_balances(year: int = None) -> dict:
        """
        Resets WL, SPL, and FL balances to fixed annual targets for all active employees.
        Runs on January 1 each year after CTO expiry.

        Rules:
          - WL: reset to 5 days for all employees (TEACHING and NON_TEACHING).
          - SPL: reset to 3 days for all employees.
          - FL (TEACHING): transfer any remaining FL balance to VL as a carryover credit,
            then reset FL to 5 days.
          - FL (NON_TEACHING): reset FL to 5 days (no VL transfer).

        Each reset posts a net CREDIT or DEBIT so the resulting balance is exactly the target.
        Idempotent: skips employees where the year-end reset was already applied this year.

        Parameters:
            year (int): The new calendar year being started. Defaults to the current year.

        Returns:
            dict: statusCode 200 with processed/skipped counts, or an error dict.
        """
        try:
            if year is None:  # default to current year if not provided
                year = date.today().year

            reset_date = f"{year}-01-01"  # all transactions are dated January 1 of the new year
            remark_tag = f"Year-end reset {year}"  # prefix used for idempotency checks

            # ── Resolve leave type IDs ───────────────────────────────────────
            leave_types = fetch_query(  # fetch all needed leave type IDs in one query
                "SELECT id, code FROM leave_types WHERE code IN ('WL', 'SPL', 'FL', 'VL') AND is_active = 1", []
            )
            if not leave_types:  # required types not found
                return {"statusCode": 500, "message": "Required leave types not found"}

            lt_map = {lt["code"]: lt["id"] for lt in leave_types}  # build code -> id lookup

            for code in ("WL", "SPL", "FL", "VL"):  # verify all four types are present
                if code not in lt_map:
                    return {"statusCode": 500, "message": f"Leave type '{code}' not found or inactive"}

            wl_id  = lt_map["WL"]   # Wellness Leave type ID
            spl_id = lt_map["SPL"]  # Special Privilege Leave type ID
            fl_id  = lt_map["FL"]   # Family Leave type ID
            vl_id  = lt_map["VL"]   # Vacation Leave type ID (for FL carryover)

            # ── Helper: get cached balance for an employee/leave type ────────
            def get_balance(emp_id: int, lt_id: int) -> float:
                """Return the current cached balance, defaulting to 0 if no record exists."""
                row = fetch_query(  # read from the balance cache
                    "SELECT balance FROM employee_leave_balances WHERE employee_id = %s AND leave_type_id = %s",
                    [emp_id, lt_id]
                )
                return float(row[0]["balance"]) if row else 0.0  # return 0 when no balance record exists

            # ── Helper: post a net adjustment to hit a target balance ────────
            def post_reset(emp_id: int, lt_id: int, current: float, target: float,
                           code: str, extra_remark: str = "") -> bool:
                """
                Posts a CREDIT or DEBIT to bring the balance from current to target.
                Returns True on success, False if the insert failed.

                Parameters:
                    emp_id (int): Employee primary key.
                    lt_id (int): Leave type primary key.
                    current (float): Employee's balance before reset.
                    target (float): Desired balance after reset.
                    code (str): Leave type code string for the audit remark.
                    extra_remark (str): Optional suffix appended to the remark.
                """
                diff = target - current  # net adjustment needed
                if diff == 0:  # already at target — nothing to post
                    return True
                txn_type = "CREDIT" if diff > 0 else "DEBIT"  # credit to add, debit to remove
                amount   = abs(diff)  # always a positive amount
                suffix   = f" — {extra_remark}" if extra_remark else ""  # optional remark suffix
                result = query_insert(  # post the adjustment to the ledger
                    """INSERT INTO leave_credit_transactions
                           (transaction_number, employee_id, leave_type_id, transaction_type,
                            amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                       VALUES (%s, %s, %s, %s, %s, 'SYSTEM_ADJUSTMENT', %s, %s, 0, %s)""",
                    [
                        AnnualLeaveCredit._generate_transaction_number(),  # unique TXN number
                        emp_id,                                             # employee being adjusted
                        lt_id,                                              # leave type being adjusted
                        txn_type,                                           # CREDIT or DEBIT
                        amount,                                             # days adjusted
                        year,                                               # source_id = year
                        reset_date,                                         # Jan 1 of new year
                        f"{remark_tag} — {code} reset to {int(target)}{suffix}",  # audit remark
                    ]
                )
                if result["statusCode"] != 200:  # insert failed
                    return False
                recalculate_ledger_snapshots(emp_id, lt_id)  # update cached balance
                return True

            # ── Fetch all active employees ───────────────────────────────────
            employees = fetch_query(  # get all active employees and their type
                "SELECT id, employee_type FROM employees WHERE is_active = 1", []
            )
            if not employees:  # nothing to process
                return {"statusCode": 200, "message": "No active employees found", "processed": 0, "skipped": 0}

            processed = 0  # count of employees fully reset
            skipped   = 0  # count of employees already reset this year

            for emp in employees:  # iterate each active employee
                emp_id   = emp["id"]             # employee primary key
                emp_type = emp["employee_type"]  # TEACHING or NON_TEACHING

                # Idempotency: if a year-end WL reset already exists for this employee this year, skip
                already = fetch_query(  # check for existing year-end reset marker on WL
                    """SELECT id FROM leave_credit_transactions
                       WHERE employee_id = %s AND leave_type_id = %s
                         AND source_type = 'SYSTEM_ADJUSTMENT'
                         AND YEAR(transaction_date) = %s
                         AND remarks LIKE %s
                       LIMIT 1""",
                    [emp_id, wl_id, year, f"{remark_tag}%"]
                )
                if already:  # reset already ran for this employee this year
                    skipped += 1
                    continue

                # ── Reset WL → 5 (all employees) ────────────────────────────
                wl_current = get_balance(emp_id, wl_id)  # current WL balance
                post_reset(emp_id, wl_id, wl_current, 5.0, "WL")  # reset to 5

                # ── Reset SPL → 3 (all employees) ───────────────────────────
                spl_current = get_balance(emp_id, spl_id)  # current SPL balance
                post_reset(emp_id, spl_id, spl_current, 3.0, "SPL")  # reset to 3

                # ── FL handling ──────────────────────────────────────────────
                fl_current = get_balance(emp_id, fl_id)  # current FL balance

                if emp_type == "TEACHING" and fl_current > 0:  # TEACHING: transfer remaining FL → VL
                    vl_result = query_insert(  # post CREDIT to VL for the remaining FL days
                        """INSERT INTO leave_credit_transactions
                               (transaction_number, employee_id, leave_type_id, transaction_type,
                                amount, source_type, source_id, transaction_date, balance_snapshot_after, remarks)
                           VALUES (%s, %s, %s, 'CREDIT', %s, 'SYSTEM_ADJUSTMENT', %s, %s, 0, %s)""",
                        [
                            AnnualLeaveCredit._generate_transaction_number(),  # unique TXN number
                            emp_id,                                             # employee
                            vl_id,                                              # credit goes to VL
                            fl_current,                                         # amount = remaining FL
                            year,                                               # source_id = year
                            reset_date,                                         # Jan 1
                            f"{remark_tag} — FL carryover {fl_current} day(s) to VL",  # audit remark
                        ]
                    )
                    if vl_result["statusCode"] == 200:  # VL credit posted
                        recalculate_ledger_snapshots(emp_id, vl_id)  # update VL cache

                post_reset(emp_id, fl_id, fl_current, 5.0, "FL")  # reset FL to 5 for all employees

                processed += 1  # mark this employee as fully processed

            return {  # return summary of the job run
                "statusCode": 200,
                "message": f"Year-end balance reset complete for {year}",
                "year":      year,       # year that was reset
                "processed": processed,  # employees whose balances were reset
                "skipped":   skipped,    # employees already reset (idempotency)
            }

        except Exception as e:  # catch unexpected errors
            return {"statusCode": 500, "message": str(e)}
