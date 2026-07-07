from flask import Flask  # import Flask to create the application instance
from flask_cors import CORS  # import CORS to allow cross-origin requests
from dotenv import load_dotenv  # import load_dotenv to read environment variables from .env
from apscheduler.schedulers.background import BackgroundScheduler  # import scheduler for background jobs

from handler import employee_handler  # import employee handler functions
from handler import auth_handler  # import auth handler functions
from handler import user_handler  # import user management handler functions
from handler import leave_credit_handler  # import leave credit handler functions
from handler import monthly_leave_credit_handler  # import monthly leave credit handler functions
from handler import leave_application_handler  # import leave application handler functions
from handler import leave_approval_handler  # import leave approval handler functions
from handler import service_credit_application_handler  # import service credit application handler functions
from handler import special_order_handler  # import special order handler functions
from handler import leave_type_handler  # import leave type handler functions
from handler import leave_credit_transaction_handler  # import leave credit transaction handler functions
from handler import school_handler  # import school handler functions
from handler import position_handler  # import position handler functions
from handler import calendar_event_handler  # import calendar event handler functions
from handler import leave_monetization_handler  # import leave monetization handler functions
from handler import undertime_tardiness_handler  # import undertime/tardiness deduction handler functions
from handler import employee_type_conversion_handler  # import personnel type conversion handler functions
from handler import dashboard_handler  # import dashboard and analytics handler functions
from handler import leave_without_pay_handler  # import leave without pay handler functions

load_dotenv()  # load environment variables from .env file into os.environ

app = Flask(__name__)  # create the Flask application instance
CORS(app)  # enable CORS for all routes

from model.service_credit_application import ServiceCreditApplication  # import here to avoid circular imports at module level

scheduler = BackgroundScheduler()  # create the background scheduler
scheduler.add_job(  # register the daily CTO expiry check
    func=ServiceCreditApplication.expire_cto_credits,  # function to call
    trigger="cron",  # run on a schedule
    hour=0,          # at midnight
    minute=0,        # on the dot
    id="cto_expiry_check",       # unique job ID for deduplication
    replace_existing=True,       # replace if already registered (safe on hot reload)
)
scheduler.start()  # start the scheduler in the background
ServiceCreditApplication.expire_cto_credits()  # run once immediately on startup to catch any expirations missed while the server was down


# --------------------------
# School routes
# --------------------------

app.add_url_rule("/schools", view_func=school_handler.get_all_schools, methods=["GET"])  # get all schools in the division ordered alphabetically
app.add_url_rule("/positions", view_func=position_handler.get_all_positions, methods=["GET"])  # get all positions; optional ?type=TEACHING or ?type=NON_TEACHING filter


# --------------------------
# Calendar Event routes
# --------------------------

app.add_url_rule("/calendar-events", view_func=calendar_event_handler.get_events_by_year, methods=["GET"])  # get all events for a year; optional ?year= param, defaults to current year
app.add_url_rule("/calendar-events/current-month", view_func=calendar_event_handler.get_events_current_month, methods=["GET"])  # get all events for the current calendar month
app.add_url_rule("/calendar-events", view_func=calendar_event_handler.create_calendar_event, methods=["POST"])  # create a calendar event (ADMIN only)
app.add_url_rule("/calendar-events/<int:event_id>", view_func=calendar_event_handler.update_calendar_event, methods=["PUT"])  # update a calendar event by ID (ADMIN only)
app.add_url_rule("/calendar-events/<int:event_id>", view_func=calendar_event_handler.delete_calendar_event, methods=["DELETE"])  # delete a calendar event by ID (ADMIN only)


# --------------------------
# Auth routes
# --------------------------

app.add_url_rule("/auth/login", view_func=auth_handler.login, methods=["POST"])  # login and receive JWT token
app.add_url_rule("/auth/me", view_func=auth_handler.get_me, methods=["GET"])  # get own profile from token


# --------------------------
# User management routes (ADMIN only)
# --------------------------

app.add_url_rule("/users", view_func=user_handler.create_user, methods=["POST"])  # create a user account (ADMIN only)
app.add_url_rule("/users", view_func=user_handler.get_all_users, methods=["GET"])  # list all user accounts with pagination (ADMIN only)
app.add_url_rule("/users/<int:user_id>", view_func=user_handler.get_user_by_id, methods=["GET"])  # get user by ID (ADMIN only)
app.add_url_rule("/users/<int:user_id>/role", view_func=user_handler.update_user_role, methods=["PATCH"])  # change a user's role (ADMIN only)
app.add_url_rule("/users/<int:user_id>/deactivate", view_func=user_handler.deactivate_user, methods=["PATCH"])  # deactivate a user account (ADMIN only)
app.add_url_rule("/users/<int:user_id>/activate", view_func=user_handler.activate_user, methods=["PATCH"])  # reactivate a user account (ADMIN only)
app.add_url_rule("/users/<int:user_id>", view_func=user_handler.delete_user, methods=["DELETE"])  # permanently delete a user account (ADMIN only)
app.add_url_rule("/users/<int:user_id>/reset-password", view_func=user_handler.reset_user_password, methods=["PATCH"])  # reset a user's password (ADMIN only)


# --------------------------
# Employee routes
# --------------------------

app.add_url_rule("/employees", view_func=employee_handler.create_employee, methods=["POST"])  # create employee
app.add_url_rule("/employees", view_func=employee_handler.get_employees_paginated, methods=["GET"])  # list employees (paginated)
app.add_url_rule("/employees/count", view_func=employee_handler.get_employee_count, methods=["GET"])  # total count
app.add_url_rule("/employees/pages", view_func=employee_handler.get_total_employee_pages, methods=["GET"])  # total pages
app.add_url_rule("/employees/search", view_func=employee_handler.search_employees, methods=["GET"])  # search employees
app.add_url_rule("/employees/my-school", view_func=employee_handler.get_employees_by_school, methods=["GET"])  # list employees in the current user's school (all roles; TEACHING auto-scoped, ADMIN/DIVISION can pass ?school_id)
app.add_url_rule("/employees/my-school/search", view_func=employee_handler.search_employees_by_school, methods=["GET"])  # search employees within the current user's school by keyword (all roles; TEACHING auto-scoped, ADMIN/DIVISION can pass ?school_id)
app.add_url_rule("/employees/<int:employee_id>", view_func=employee_handler.get_employee_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/employees/<int:employee_id>", view_func=employee_handler.update_employee, methods=["PUT"])  # update by ID
app.add_url_rule("/employees/<int:employee_id>", view_func=employee_handler.delete_employee, methods=["DELETE"])  # delete by ID
app.add_url_rule("/employees/<int:employee_id>/leave-balances", view_func=employee_handler.get_employee_leave_balances, methods=["GET"])  # get leave balances by employee
app.add_url_rule("/employees/<int:employee_id>/convert-type", view_func=employee_type_conversion_handler.convert_employee_type, methods=["POST"])  # convert employee type TEACHING↔NON_TEACHING with ledger transactions (ADMIN only)
app.add_url_rule("/employees/<int:employee_id>/conversion-history", view_func=employee_type_conversion_handler.get_conversion_history, methods=["GET"])  # get full conversion history for an employee (ADMIN/DIVISION only)
app.add_url_rule("/employees/<int:employee_id>/photo", view_func=employee_handler.upload_employee_photo, methods=["POST"])  # upload employee photo
app.add_url_rule("/uploads/employee_photos/<path:filename>", view_func=employee_handler.get_employee_photo, methods=["GET"])  # serve uploaded employee photo


# --------------------------
# Leave Type routes
# --------------------------

app.add_url_rule("/leave-types", view_func=leave_type_handler.get_all_leave_types, methods=["GET"])  # get all leave types
app.add_url_rule("/leave-types/teaching/<int:employee_id>", view_func=leave_type_handler.get_teaching_leave_types, methods=["GET"])  # get leave types for teaching staff by employee (excludes SL and PR)


# --------------------------
# Leave Credit Transaction routes
# --------------------------

app.add_url_rule("/leave-credit-transactions/employee/<int:employee_id>", view_func=leave_credit_transaction_handler.get_transactions_by_employee, methods=["GET"])  # get paginated ledger transactions by employee
app.add_url_rule("/leave-credit-transactions/employee/<int:employee_id>/year/<int:year>", view_func=leave_credit_transaction_handler.get_transactions_by_employee_and_year, methods=["GET"])  # get all ledger transactions by employee and year


# --------------------------
# Leave Credit routes
# --------------------------

app.add_url_rule("/leave-credits", view_func=leave_credit_handler.credit_leave, methods=["POST"])  # credit leave balance via manual adjustment
app.add_url_rule("/leave-credits/forwarded-balance", view_func=leave_credit_handler.post_forwarded_balance, methods=["POST"])  # post forwarded balance credit for a leave type at year start


# --------------------------
# Monthly Leave Credit routes
# --------------------------

app.add_url_rule("/monthly-leave-credits", view_func=monthly_leave_credit_handler.credit_monthly_leave, methods=["POST"])  # credit monthly VL or SL for an employee
app.add_url_rule("/monthly-leave-credits/employee/<int:employee_id>/year/<int:year>", view_func=monthly_leave_credit_handler.get_monthly_credits_by_employee_and_year, methods=["GET"])  # get monthly credits by employee and year with ledger


# --------------------------
# Leave Application routes
# --------------------------

app.add_url_rule("/leave-applications", view_func=leave_application_handler.submit_leave_application, methods=["POST"])  # submit leave application
app.add_url_rule("/leave-applications", view_func=leave_application_handler.get_all_leave_applications, methods=["GET"])  # list all leave applications excluding CTO/VSC (paginated)
app.add_url_rule("/leave-applications/search", view_func=leave_application_handler.search_leave_applications, methods=["GET"])  # search with optional filters: year, date_from, date_to, status, leave_type_code
app.add_url_rule("/leave-applications/number/<string:application_number>", view_func=leave_application_handler.get_leave_application_by_number, methods=["GET"])  # get by application number (no pagination)
app.add_url_rule("/leave-applications/all", view_func=leave_application_handler.get_all_leave_applications_including_cto_vsc, methods=["GET"])  # list ALL leave applications including CTO and VSC (paginated)
app.add_url_rule("/leave-applications/cto-vsc", view_func=leave_application_handler.get_all_cto_vsc_leave_applications, methods=["GET"])  # list CTO and VSC leave applications only (paginated)
app.add_url_rule("/leave-applications/cto-vsc/employee/<int:employee_id>", view_func=leave_application_handler.get_cto_vsc_leave_applications_by_employee, methods=["GET"])  # get CTO/VSC applications by employee
app.add_url_rule("/leave-applications/my-school", view_func=leave_application_handler.get_leave_applications_by_school, methods=["GET"])  # list leave applications for the current user's school (all roles; TEACHING auto-scoped, ADMIN/DIVISION can pass ?school_id)
app.add_url_rule("/leave-applications/<int:application_id>", view_func=leave_application_handler.get_leave_application_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/leave-applications/<int:application_id>", view_func=leave_application_handler.update_leave_application, methods=["PUT"])  # replace leave dates (only when status is FOR HRMO ACTION)
app.add_url_rule("/leave-applications/<int:application_id>", view_func=leave_application_handler.delete_leave_application, methods=["DELETE"])  # soft-delete; reverses balance if not already returned/disapproved
app.add_url_rule("/leave-applications/employee/<int:employee_id>", view_func=leave_application_handler.get_leave_applications_by_employee, methods=["GET"])  # get all by employee (excludes CTO/VSC)
app.add_url_rule("/leave-applications/employee/<int:employee_id>/year/<int:year>", view_func=leave_application_handler.get_leave_applications_by_employee_and_year, methods=["GET"])  # get all by employee and year with ledger (excludes CTO/VSC)


# --------------------------
# Leave Monetization routes
# --------------------------

app.add_url_rule("/leave-monetizations", view_func=leave_monetization_handler.submit_monetization, methods=["POST"])  # submit a leave monetization; deducts VL and/or SL immediately
app.add_url_rule("/leave-monetizations", view_func=leave_monetization_handler.get_all_monetizations, methods=["GET"])  # list all monetizations (paginated)
app.add_url_rule("/leave-monetizations/<int:monetization_id>", view_func=leave_monetization_handler.get_monetization_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/leave-monetizations/<int:monetization_id>", view_func=leave_monetization_handler.delete_monetization, methods=["DELETE"])  # soft-delete; reverses balance if not already returned/disapproved
app.add_url_rule("/leave-monetizations/employee/<int:employee_id>", view_func=leave_monetization_handler.get_monetizations_by_employee, methods=["GET"])  # get all by employee


# --------------------------
# Undertime / Tardiness Deduction routes
# --------------------------

app.add_url_rule("/undertime-tardiness", view_func=undertime_tardiness_handler.create_undertime_tardiness, methods=["POST"])  # create a deduction (ADMIN only; NON_TEACHING employees only)
app.add_url_rule("/undertime-tardiness", view_func=undertime_tardiness_handler.get_all_undertime_tardiness, methods=["GET"])  # list all deductions (paginated)
app.add_url_rule("/undertime-tardiness/search", view_func=undertime_tardiness_handler.search_undertime_tardiness, methods=["GET"])  # search by application number or employee
app.add_url_rule("/undertime-tardiness/filter", view_func=undertime_tardiness_handler.filter_undertime_tardiness, methods=["GET"])  # filter by year, date range, or employee
app.add_url_rule("/undertime-tardiness/<int:deduction_id>", view_func=undertime_tardiness_handler.get_undertime_tardiness_by_id, methods=["GET"])  # get single deduction by ID
app.add_url_rule("/undertime-tardiness/<int:deduction_id>", view_func=undertime_tardiness_handler.delete_undertime_tardiness, methods=["DELETE"])  # soft-delete and reverse VL debit (ADMIN only)


# --------------------------
# Leave Approval routes
# --------------------------

app.add_url_rule("/leave-approvals", view_func=leave_approval_handler.decide_leave_application, methods=["POST"])  # submit approval decision
app.add_url_rule("/leave-approvals/application/<int:application_id>", view_func=leave_approval_handler.get_approvals_by_application, methods=["GET"])  # get approvals by application


# --------------------------
# Special Order routes
# --------------------------

app.add_url_rule("/special-orders", view_func=special_order_handler.create_special_order, methods=["POST"])  # create a new Special Order
app.add_url_rule("/special-orders", view_func=special_order_handler.get_all_special_orders, methods=["GET"])  # list all Special Orders (paginated)
app.add_url_rule("/special-orders/search", view_func=special_order_handler.search_special_orders, methods=["GET"])  # search by special_order number or activity_name (paginated)
app.add_url_rule("/special-orders/filter", view_func=special_order_handler.filter_special_orders, methods=["GET"])  # filter by year and/or date range on date_of_activity (paginated)
app.add_url_rule("/special-orders/<int:special_order_id>", view_func=special_order_handler.get_special_order_by_id, methods=["GET"])  # get Special Order by ID


# --------------------------
# Service Credit Application routes (CTO / VSC)
# --------------------------

app.add_url_rule("/service-credit-applications", view_func=service_credit_application_handler.submit_service_credit_application, methods=["POST"])  # submit CTO or VSC application; balance credited immediately
app.add_url_rule("/service-credit-applications", view_func=service_credit_application_handler.get_all_service_credit_applications, methods=["GET"])  # list all applications (paginated)
app.add_url_rule("/service-credit-applications/search", view_func=service_credit_application_handler.search_service_credit_applications, methods=["GET"])  # search with optional filters: special_order_id, type, year, date_from, date_to
app.add_url_rule("/service-credit-applications/number/<string:application_number>", view_func=service_credit_application_handler.get_service_credit_application_by_number, methods=["GET"])  # get by application number (no pagination)
app.add_url_rule("/service-credit-applications/special-order/<int:special_order_id>", view_func=service_credit_application_handler.get_service_credit_applications_by_special_order, methods=["GET"])  # get all by Special Order (paginated)
app.add_url_rule("/service-credit-applications/special-order/<int:special_order_id>/search", view_func=service_credit_application_handler.search_service_credit_applications_by_special_order, methods=["GET"])  # search within a Special Order by application number or employee
app.add_url_rule("/service-credit-applications/<int:application_id>", view_func=service_credit_application_handler.get_service_credit_application_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/service-credit-applications/employee/<int:employee_id>/cto-leave-summary", view_func=service_credit_application_handler.get_cto_leave_summary_by_employee, methods=["GET"])  # get all CTO credits with their primary leave applications for an employee
app.add_url_rule("/service-credit-applications/employee/<int:employee_id>/vsc-old-leave-summary", view_func=service_credit_application_handler.get_vsc_old_leave_summary_by_employee, methods=["GET"])  # get VSC credits (activity < 2024-10-01) with their primary leave applications
app.add_url_rule("/service-credit-applications/employee/<int:employee_id>/vsc-new-leave-summary", view_func=service_credit_application_handler.get_vsc_new_leave_summary_by_employee, methods=["GET"])  # get VSC credits (activity >= 2024-10-01) with their primary leave applications
app.add_url_rule("/service-credit-applications/employee/<int:employee_id>", view_func=service_credit_application_handler.get_service_credit_applications_by_employee, methods=["GET"])  # get all by employee


# --------------------------
# Dashboard / Analytics routes (ADMIN and DIVISION_PERSONNEL)
# --------------------------

app.add_url_rule("/dashboard/teaching/on-leave", view_func=dashboard_handler.get_teaching_on_leave, methods=["GET"])  # list of TEACHING employees on leave on a specific date
app.add_url_rule("/dashboard/non-teaching/on-leave", view_func=dashboard_handler.get_non_teaching_on_leave, methods=["GET"])  # list of NON_TEACHING employees on leave on a specific date
app.add_url_rule("/dashboard/teaching/on-leave/count", view_func=dashboard_handler.get_teaching_on_leave_count, methods=["GET"])  # count of TEACHING employees on leave + total headcount for a specific date
app.add_url_rule("/dashboard/non-teaching/on-leave/count", view_func=dashboard_handler.get_non_teaching_on_leave_count, methods=["GET"])  # count of NON_TEACHING employees on leave + total headcount for a specific date
app.add_url_rule("/dashboard/teaching/leave-type-breakdown", view_func=dashboard_handler.get_teaching_leave_type_breakdown, methods=["GET"])  # monthly leave type breakdown for TEACHING with optional date range
app.add_url_rule("/dashboard/non-teaching/leave-type-breakdown", view_func=dashboard_handler.get_non_teaching_leave_type_breakdown, methods=["GET"])  # monthly leave type breakdown for NON_TEACHING with optional date range
app.add_url_rule("/dashboard/pending-applications", view_func=dashboard_handler.get_latest_pending_applications, methods=["GET"])  # latest 5 pending (FOR HRMO ACTION) leave applications across all types


# --------------------------
# Leave Without Pay routes (PAYROLL only)
# --------------------------

app.add_url_rule("/leave-without-pay/teaching", view_func=leave_without_pay_handler.get_teaching_leave_without_pay, methods=["GET"])  # paginated LWOP dates for TEACHING employees; supports ?date_from, ?date_to, ?page, ?limit
app.add_url_rule("/leave-without-pay/non-teaching", view_func=leave_without_pay_handler.get_non_teaching_leave_without_pay, methods=["GET"])  # paginated LWOP dates for NON_TEACHING employees; supports ?date_from, ?date_to, ?page, ?limit


if __name__ == "__main__":
    app.run(  # start the development server
        host="0.0.0.0",  # listen on all network interfaces
        port=5001,  # bind to port 5000
        debug=True,  # enable debug mode for auto-reload and detailed error pages
    )
