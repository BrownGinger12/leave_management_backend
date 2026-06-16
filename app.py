from flask import Flask  # import Flask to create the application instance
from flask_cors import CORS  # import CORS to allow cross-origin requests
from dotenv import load_dotenv  # import load_dotenv to read environment variables from .env

from handler import employee_handler  # import employee handler functions
from handler import leave_credit_handler  # import leave credit handler functions
from handler import leave_application_handler  # import leave application handler functions
from handler import leave_approval_handler  # import leave approval handler functions
from handler import cto_application_handler  # import CTO application handler functions
from handler import leave_type_handler  # import leave type handler functions
from handler import leave_credit_transaction_handler  # import leave credit transaction handler functions

load_dotenv()  # load environment variables from .env file into os.environ

app = Flask(__name__)  # create the Flask application instance
CORS(app)  # enable CORS for all routes


# --------------------------
# Employee routes
# --------------------------

app.add_url_rule("/employees", view_func=employee_handler.create_employee, methods=["POST"])  # create employee
app.add_url_rule("/employees", view_func=employee_handler.get_employees_paginated, methods=["GET"])  # list employees (paginated)
app.add_url_rule("/employees/count", view_func=employee_handler.get_employee_count, methods=["GET"])  # total count
app.add_url_rule("/employees/pages", view_func=employee_handler.get_total_employee_pages, methods=["GET"])  # total pages
app.add_url_rule("/employees/search", view_func=employee_handler.search_employees, methods=["GET"])  # search employees
app.add_url_rule("/employees/<int:employee_id>", view_func=employee_handler.get_employee_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/employees/<int:employee_id>", view_func=employee_handler.update_employee, methods=["PUT"])  # update by ID
app.add_url_rule("/employees/<int:employee_id>", view_func=employee_handler.delete_employee, methods=["DELETE"])  # delete by ID
app.add_url_rule("/employees/<int:employee_id>/leave-balances", view_func=employee_handler.get_employee_leave_balances, methods=["GET"])  # get leave balances by employee


# --------------------------
# Leave Type routes
# --------------------------

app.add_url_rule("/leave-types", view_func=leave_type_handler.get_all_leave_types, methods=["GET"])  # get all leave types


# --------------------------
# Leave Credit Transaction routes
# --------------------------

app.add_url_rule("/leave-credit-transactions/employee/<int:employee_id>", view_func=leave_credit_transaction_handler.get_transactions_by_employee, methods=["GET"])  # get paginated ledger transactions by employee


# --------------------------
# Leave Credit routes
# --------------------------

app.add_url_rule("/leave-credits", view_func=leave_credit_handler.credit_leave, methods=["POST"])  # credit VL or SL balance


# --------------------------
# Leave Application routes
# --------------------------

app.add_url_rule("/leave-applications", view_func=leave_application_handler.submit_leave_application, methods=["POST"])  # submit leave application
app.add_url_rule("/leave-applications", view_func=leave_application_handler.get_all_leave_applications, methods=["GET"])  # list all leave applications (paginated)
app.add_url_rule("/leave-applications/<int:application_id>", view_func=leave_application_handler.get_leave_application_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/leave-applications/employee/<int:employee_id>", view_func=leave_application_handler.get_leave_applications_by_employee, methods=["GET"])  # get all by employee


# --------------------------
# Leave Approval routes
# --------------------------

app.add_url_rule("/leave-approvals", view_func=leave_approval_handler.decide_leave_application, methods=["POST"])  # submit approval decision
app.add_url_rule("/leave-approvals/application/<int:application_id>", view_func=leave_approval_handler.get_approvals_by_application, methods=["GET"])  # get approvals by application


# --------------------------
# CTO Application routes
# --------------------------

app.add_url_rule("/cto-applications", view_func=cto_application_handler.submit_cto_application, methods=["POST"])  # submit CTO application
app.add_url_rule("/cto-applications", view_func=cto_application_handler.get_all_cto_applications, methods=["GET"])  # list all CTO applications (paginated)
app.add_url_rule("/cto-applications/decide", view_func=cto_application_handler.decide_cto_application, methods=["POST"])  # approve or reject CTO application
app.add_url_rule("/cto-applications/<int:application_id>", view_func=cto_application_handler.get_cto_application_by_id, methods=["GET"])  # get by ID
app.add_url_rule("/cto-applications/employee/<int:employee_id>", view_func=cto_application_handler.get_cto_applications_by_employee, methods=["GET"])  # get all by employee


if __name__ == "__main__":
    app.run(  # start the development server
        host="0.0.0.0",  # listen on all network interfaces
        port=5000,  # bind to port 5000
        debug=True,  # enable debug mode for auto-reload and detailed error pages
    )
