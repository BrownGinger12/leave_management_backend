from flask import request, jsonify, send_file  # import request/jsonify for HTTP I/O, send_file for Excel download
from datetime import date  # import date for default as_of value
from model.leave_balance_report import LeaveBalanceReport  # import the leave balance report model
from gateway.auth_gateway import require_role  # import role decorator


@require_role("ADMIN", "DIVISION_PERSONNEL", "PAYROLL")
def export_leave_balances():
    """
    Handles GET /leave-balances/export — generates and downloads an Excel report
    of all active employees and their current leave balances using the official
    DepEd LEAVE BALANCES template. VSC is split into old and new period columns.
    ADMIN, DIVISION_PERSONNEL, and PAYROLL.

    Query params:
        as_of (str): Date to display in the report header (YYYY-MM-DD or MM/DD/YYYY).
                     Defaults to today if not provided.

    Returns:
        An .xlsx file attachment, or a JSON error response.
    """
    try:
        as_of = request.args.get("as_of", default=None, type=str)  # optional as_of date for header

        result = LeaveBalanceReport.export_to_excel(as_of)  # generate the workbook

        if isinstance(result, dict):  # model returned an error dict instead of a buffer
            return jsonify(result), result.get("statusCode", 500)

        label = as_of or date.today().strftime("%Y-%m-%d")  # use today if not provided
        filename = f"leave_balances_{label}.xlsx"  # descriptive download filename
        return send_file(  # stream the BytesIO buffer as a file download
            result,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Excel MIME type
            as_attachment=True,  # trigger browser download dialog
            download_name=filename,  # suggested filename for the browser
        )

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500
