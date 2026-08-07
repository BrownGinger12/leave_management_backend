from flask import request, jsonify, send_file  # import request/jsonify for HTTP I/O, send_file for Excel download
from datetime import date  # import date for default year range
from model.leave_without_pay import LeaveWithoutPay  # import the LWOP model
from gateway.auth_gateway import require_role  # import role decorator


def _current_year_range():
    """Returns (Jan 1, Dec 31) of the current year as YYYY-MM-DD strings."""
    year = date.today().year  # current calendar year
    return f"{year}-01-01", f"{year}-12-31"  # full year range


@require_role("PAYROLL")
def get_teaching_leave_without_pay():
    """
    Handles GET /leave-without-pay/teaching.
    Returns a paginated list of leave-without-pay dates for TEACHING employees.
    PAYROLL only.

    Query params:
        date_from (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.
        page      (int): Page number. Default 1.
        limit     (int): Records per page. Default 10.

    Returns:
        JSON response with paginated LWOP records and HTTP 200, or an error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # read start date
        date_to   = request.args.get("date_to",   default=default_to,   type=str)  # read end date
        page      = request.args.get("page",       default=1,            type=int)  # read page number
        limit     = request.args.get("limit",      default=10,           type=int)  # read page size

        school_type = request.args.get("school_type", default=None, type=str)  # optional school type filter
        response = LeaveWithoutPay.get_paginated("TEACHING", date_from, date_to, page, limit, school_type)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


@require_role("PAYROLL")
def get_non_teaching_leave_without_pay():
    """
    Handles GET /leave-without-pay/non-teaching.
    Returns a paginated list of leave-without-pay dates for NON_TEACHING employees.
    PAYROLL only.

    Query params:
        date_from (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to   (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.
        page      (int): Page number. Default 1.
        limit     (int): Records per page. Default 10.

    Returns:
        JSON response with paginated LWOP records and HTTP 200, or an error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from = request.args.get("date_from", default=default_from, type=str)  # read start date
        date_to   = request.args.get("date_to",   default=default_to,   type=str)  # read end date
        page      = request.args.get("page",       default=1,            type=int)  # read page number
        limit     = request.args.get("limit",      default=10,           type=int)  # read page size

        school_type = request.args.get("school_type", default=None, type=str)  # optional school type filter
        response = LeaveWithoutPay.get_paginated("NON_TEACHING", date_from, date_to, page, limit, school_type)  # delegate to model
        return jsonify(response), response["statusCode"]  # return result

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500  # return 500


@require_role("ADMIN", "DIVISION_PERSONNEL", "PAYROLL")
def export_teaching_leave_without_pay():
    """
    Handles GET /leave-without-pay/teaching/export — generates and downloads an Excel
    report of TEACHING leave-without-pay applications for a given date range using the
    official DepEd template (LEAVE WITHOUT PAY TEACHING.xlsx).
    ADMIN, DIVISION_PERSONNEL, and PAYROLL.

    Query params:
        date_from   (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to     (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.
        school_type (str): Optional — REGULAR, IU, or SHS.

    Returns:
        An .xlsx file attachment, or a JSON error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from   = request.args.get("date_from",   default=default_from, type=str)  # start of LWOP date range
        date_to     = request.args.get("date_to",     default=default_to,   type=str)  # end of LWOP date range
        school_type = request.args.get("school_type", default=None,         type=str)  # optional school type filter

        result = LeaveWithoutPay.export_teaching_to_excel(date_from, date_to, school_type)  # generate workbook

        if isinstance(result, dict):  # model returned an error dict instead of a buffer
            return jsonify(result), result.get("statusCode", 500)

        filename = f"lwop_teaching_{date_from}_to_{date_to}.xlsx"  # descriptive download filename
        return send_file(  # stream the BytesIO buffer as a file download
            result,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Excel MIME type
            as_attachment=True,  # trigger browser download dialog
            download_name=filename,  # suggested filename for the browser
        )

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500


@require_role("ADMIN", "DIVISION_PERSONNEL", "PAYROLL")
def export_non_teaching_leave_without_pay():
    """
    Handles GET /leave-without-pay/non-teaching/export — generates and downloads an Excel
    report of NON_TEACHING leave-without-pay applications for a given date range using the
    official DepEd template (LEAVE WITHOUT PAY NON TEACHING.xlsx).
    Unpaid days are split into VL (col M) and SL (col N) to match the template layout.
    ADMIN, DIVISION_PERSONNEL, and PAYROLL.

    Query params:
        date_from   (str): Start date (YYYY-MM-DD). Defaults to Jan 1 of current year.
        date_to     (str): End date (YYYY-MM-DD). Defaults to Dec 31 of current year.
        school_type (str): Optional — REGULAR, IU, or SHS.

    Returns:
        An .xlsx file attachment, or a JSON error response.
    """
    try:
        default_from, default_to = _current_year_range()  # default to full current year
        date_from   = request.args.get("date_from",   default=default_from, type=str)  # start of LWOP date range
        date_to     = request.args.get("date_to",     default=default_to,   type=str)  # end of LWOP date range
        school_type = request.args.get("school_type", default=None,         type=str)  # optional school type filter

        result = LeaveWithoutPay.export_non_teaching_to_excel(date_from, date_to, school_type)  # generate workbook

        if isinstance(result, dict):  # model returned an error dict instead of a buffer
            return jsonify(result), result.get("statusCode", 500)

        filename = f"lwop_non_teaching_{date_from}_to_{date_to}.xlsx"  # descriptive download filename
        return send_file(  # stream the BytesIO buffer as a file download
            result,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Excel MIME type
            as_attachment=True,  # trigger browser download dialog
            download_name=filename,  # suggested filename for the browser
        )

    except Exception as e:  # catch unexpected errors
        return jsonify({"message": str(e)}), 500
