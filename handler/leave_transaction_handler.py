from flask import request, jsonify, send_file  # import request/jsonify for HTTP I/O, send_file for Excel download
from datetime import date  # import date for default year range
from model.leave_transaction import LeaveTransaction  # import the leave transaction model
from gateway.auth_gateway import require_role  # import role decorator


def _current_year_range():
    """Returns (Jan 1, Dec 31) of the current year as YYYY-MM-DD strings."""
    year = date.today().year  # current calendar year
    return f"{year}-01-01", f"{year}-12-31"  # full year range


@require_role("ADMIN", "DIVISION_PERSONNEL", "PAYROLL")
def export_leave_transactions():
    """
    Handles GET /leave-transactions/export — generates and downloads an Excel report
    of all leave applications whose leave dates fall within the given date range,
    using the official DepEd LEAVE TRANSACTIONS template.
    Each row is one application; column K lists all individual leave dates incurred.
    ADMIN, DIVISION_PERSONNEL, and PAYROLL.

    Query params:
        date_from (str): Start of leave date range (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End of leave date range (YYYY-MM-DD). Defaults to Dec 31 of current year.

    Returns:
        An .xlsx file attachment, or a JSON error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # start of date range
        date_to   = request.args.get("date_to",   default=default_to,   type=str)  # end of date range

        result = LeaveTransaction.export_to_excel(date_from, date_to)  # generate the workbook

        if isinstance(result, dict):  # model returned an error dict instead of a buffer
            return jsonify(result), result.get("statusCode", 500)

        filename = f"leave_transactions_{date_from}_to_{date_to}.xlsx"  # descriptive download filename
        return send_file(  # stream the BytesIO buffer as a file download
            result,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Excel MIME type
            as_attachment=True,  # trigger browser download dialog
            download_name=filename,  # suggested filename for the browser
        )

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500
