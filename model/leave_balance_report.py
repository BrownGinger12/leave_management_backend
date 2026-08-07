from pydantic import BaseModel  # import BaseModel as the base for all models
from gateway.mysql_gateway import fetch_query  # import fetch_query for SELECT operations


class LeaveBalanceReport(BaseModel):
    """
    Model for exporting a snapshot of all employee leave balances using the
    official DepEd LEAVE BALANCES template.
    Balances are sourced from employee_leave_balances (current cached snapshot).
    VSC is split into old (activity < 2024-10-01) and new (activity >= 2024-10-01)
    using a FIFO approach: old credits are consumed before new ones.
    """

    @staticmethod
    def export_to_excel(as_of: str = None):
        """
        Generates an Excel report of all active employees and their current leave
        balances using the official DepEd LEAVE BALANCES template
        (Template/LEAVE BALANCES.xlsx).
        Each row is one employee. VSC is split into two columns by activity period.

        Parameters:
            as_of (str): Date string shown in the report header (MM/DD/YYYY or YYYY-MM-DD).
                         Defaults to today if not provided.

        Returns:
            io.BytesIO: In-memory Excel file ready to be sent as an attachment.
            dict: Error dict if a problem occurs before the file is generated.
        """
        import os  # used to build the template path
        import io  # used to create an in-memory byte buffer
        import openpyxl  # used to load and write the Excel workbook
        from openpyxl.styles import Border, Side, Font, Alignment  # cell styling classes
        from datetime import date  # used for default as_of date

        try:
            if not as_of:  # default to today when not provided
                as_of = date.today().strftime("%m/%d/%Y")  # MM/DD/YYYY format
            elif "-" in as_of:  # convert YYYY-MM-DD to MM/DD/YYYY for display
                parts = as_of.split("-")  # split on hyphen
                as_of = f"{parts[1]}/{parts[2]}/{parts[0]}"  # reformat to MM/DD/YYYY

            rows = fetch_query(  # fetch one row per employee with all leave balances
                """SELECT
                        e.id AS employee_id,
                        e.leave_card_number,
                        e.first_name, e.last_name, e.middle_name,
                        e.position,
                        e.employee_type,
                        s.name AS school_name,
                        MAX(CASE WHEN lt.code = 'VL'   THEN elb.balance ELSE 0 END) AS vl,
                        MAX(CASE WHEN lt.code = 'SL'   THEN elb.balance ELSE 0 END) AS sl,
                        MAX(CASE WHEN lt.code = 'CTO'  THEN elb.balance ELSE 0 END) AS cto,
                        MAX(CASE WHEN lt.code = 'WL'   THEN elb.balance ELSE 0 END) AS wl,
                        MAX(CASE WHEN lt.code = 'SPL'  THEN elb.balance ELSE 0 END) AS spl,
                        MAX(CASE WHEN lt.code = 'FL'   THEN elb.balance ELSE 0 END) AS fl,
                        MAX(CASE WHEN lt.code IN ('SLB', 'SLBT') THEN elb.balance ELSE 0 END) AS slb,
                        MAX(CASE WHEN lt.code = 'VSC'  THEN elb.balance ELSE 0 END) AS vsc_total,
                        COALESCE((
                            SELECT SUM(lct.amount)
                            FROM leave_credit_transactions lct
                            JOIN service_credit_applications sca ON sca.id = lct.source_id
                            JOIN special_orders so ON so.id = sca.special_order_id
                            WHERE lct.employee_id = e.id
                              AND lct.leave_type_id = (SELECT id FROM leave_types WHERE code = 'VSC' LIMIT 1)
                              AND lct.transaction_type = 'CREDIT'
                              AND lct.source_type = 'SPECIAL_ORDER'
                              AND so.date_of_activity < '2024-10-01'
                        ), 0) AS vsc_old_credits
                    FROM employees e
                    LEFT JOIN employee_leave_balances elb ON elb.employee_id = e.id
                    LEFT JOIN leave_types lt ON lt.id = elb.leave_type_id
                    LEFT JOIN schools s ON s.id = e.school_id
                    WHERE e.is_active = 1
                    GROUP BY e.id, e.leave_card_number, e.first_name, e.last_name,
                             e.middle_name, e.position, e.employee_type, s.name
                    ORDER BY e.last_name ASC, e.first_name ASC""",
                []
            ) or []

            template_path = os.path.join(  # resolve absolute path to the leave balances template
                os.path.dirname(os.path.dirname(__file__)), "Template", "LEAVE BALANCES.xlsx"
            )
            wb = openpyxl.load_workbook(template_path)  # load template (preserves header and formatting)
            ws = wb.active  # use the first sheet

            ws.unmerge_cells("A14:O14")  # unmerge AS OF row so we can write the date
            ws.cell(row=14, column=1).value = f"AS OF {as_of}"  # write the as_of date into the header
            ws.merge_cells("A14:O14")  # re-merge to restore original layout

            ws.unmerge_cells("A49:N49")  # unmerge page-counter row so it can be relocated

            thin = Side(style="thin")  # thin border side definition
            thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)  # all-sides thin border

            DATA_START = 17  # row where data rows begin in this template

            TYPE_MAP = {  # map database employee_type to readable label
                "TEACHING": "Teaching",
                "NON_TEACHING": "Non-Teaching",
            }

            for i, row in enumerate(rows):  # write one row per employee
                r = DATA_START + i  # absolute sheet row for this employee

                last = (row["last_name"] or "").strip()  # employee last name
                first = (row["first_name"] or "").strip()  # employee first name
                middle = (row.get("middle_name") or "").strip()  # middle name (may be None)
                mi = f" {middle[0]}." if middle else ""  # middle initial with period, or empty
                full_name = f"{last}, {first}{mi}"  # format: LAST, FIRST MI.

                emp_type = TYPE_MAP.get(row.get("employee_type") or "", row.get("employee_type") or "")  # readable type

                vsc_total = float(row["vsc_total"] or 0)  # total current VSC balance
                vsc_old_credits = float(row["vsc_old_credits"] or 0)  # credits from old-period activities
                # FIFO: old credits consumed first; old remaining = min(old credits, total balance)
                vsc_old = min(vsc_old_credits, vsc_total)  # old VSC remaining (cannot exceed total)
                vsc_new = max(0.0, vsc_total - vsc_old)  # new VSC = total minus old portion

                values = [  # ordered by column A–O (15 columns)
                    i + 1,                                    # A: sequential row number
                    row.get("leave_card_number") or "",       # B: leave card number
                    full_name,                                # C: formatted employee name
                    row.get("position") or "",                # D: position/designation
                    emp_type,                                 # E: Teaching or Non-Teaching
                    row.get("school_name") or "",             # F: school or division name
                    float(row["vl"] or 0),                    # G: Vacation Leave balance
                    float(row["sl"] or 0),                    # H: Sick Leave balance
                    round(vsc_new, 4),                        # I: VSC new (activity >= 2024-10-01)
                    round(vsc_old, 4),                        # J: VSC old (activity < 2024-10-01)
                    float(row["cto"] or 0),                   # K: CTO / COC balance
                    float(row["wl"] or 0),                    # L: Wellness Leave balance
                    float(row["spl"] or 0),                   # M: Special Privilege Leave balance
                    float(row["fl"] or 0),                    # N: Forced Leave balance
                    float(row["slb"] or 0),                   # O: Solo Parent Leave balance
                ]

                for col_idx, val in enumerate(values, start=1):  # write each value into its cell
                    cell = ws.cell(row=r, column=col_idx)  # target cell
                    cell.value = val  # set value
                    cell.border = thin_border  # apply thin border to match header style

            for old_row in [45, 47, 49]:  # clear old static footer rows from template
                ws.cell(row=old_row, column=1).value = None  # clear master cell (column A)
            ws.cell(row=47, column=2).value = None  # clear signature line in column B

            footer_row = max(45, DATA_START + len(rows) + 3)  # footer at least at row 45, or below data

            cert_cell = ws.cell(row=footer_row, column=1)  # CERTIFIED CORRECT label cell
            cert_cell.value = "CERTIFIED CORRECT:"  # footer label
            cert_cell.font = Font(bold=True)  # bold to match template style

            ws.cell(row=footer_row + 2, column=2).value = "_________________________"  # signature line

            page_row = footer_row + 4  # row for the page counter
            ws.merge_cells(f"A{page_row}:O{page_row}")  # merge across all 15 columns
            page_cell = ws.cell(row=page_row, column=1)  # write to the master cell of the merge
            page_cell.value = "page 1 of 1"  # static page label
            page_cell.alignment = Alignment(horizontal="center")  # centre-align

            buffer = io.BytesIO()  # create in-memory byte buffer
            wb.save(buffer)  # write workbook to buffer
            buffer.seek(0)  # rewind to beginning before returning
            return buffer  # caller streams this as a file download

        except Exception as e:  # catch unexpected errors (missing template, DB failure, etc.)
            return {"statusCode": 500, "message": str(e)}
