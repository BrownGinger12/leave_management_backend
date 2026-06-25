import requests
import json
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POSTMAN_API_KEY")
COLLECTION_UID = "41962454-abd659ae-2811-4b93-a3bd-6a1b121d479b"

def new_id():
    """Generates a new Postman-style item ID prefixed with the workspace owner."""
    return f"41962454-{uuid.uuid4()}"

collection = {
    "info": {
        "_postman_id": "abd659ae-2811-4b93-a3bd-6a1b121d479b",
        "name": "DepEd Leave Management API",
        "description": "API collection for the DepEd Leave Management System",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [
        {"key": "base_url", "value": "http://localhost:5000", "type": "string"}
    ],
    "item": [
        # --------------------------
        # Employees
        # --------------------------
        {
            "name": "Employees",
            "item": [
                {
                    "name": "Create Employee",
                    "id": "41f89d8f-30ee-47ba-aaa9-6cfdd8793553",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "employee_number": "EMP-2024-0001",
                                "first_name": "Juan",
                                "last_name": "Dela Cruz",
                                "middle_name": "Santos",
                                "email": "juan.delacruz@deped.gov.ph",
                                "employee_type": "TEACHING",
                                "employment_status": "PERMANENT",
                                "school_id": 1,
                                "department": "Mathematics",
                                "leave_card_number": ""
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {"raw": "{{base_url}}/employees", "host": ["{{base_url}}"], "path": ["employees"]}
                    },
                    "response": []
                },
                {
                    "name": "Get All Employees",
                    "id": "ed159f5c-8b1f-4f1d-a67c-951daf3e0876",
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/employees?page=1&limit=10",
                            "host": ["{{base_url}}"], "path": ["employees"],
                            "query": [{"key": "page", "value": "1"}, {"key": "limit", "value": "10"}]
                        }
                    },
                    "response": []
                },
                {
                    "name": "Get Employee by ID",
                    "id": "e377020a-9835-43e6-afc0-baf257d59b64",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {"raw": "{{base_url}}/employees/1", "host": ["{{base_url}}"], "path": ["employees", "1"]}
                    },
                    "response": []
                },
                {
                    "name": "Get Employee Count",
                    "id": "e4c6da43-f69d-4842-a195-8d595bd53b44",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {"raw": "{{base_url}}/employees/count", "host": ["{{base_url}}"], "path": ["employees", "count"]}
                    },
                    "response": []
                },
                {
                    "name": "Get Total Employee Pages",
                    "id": "4bdb52bb-5658-41b1-adee-cb0461012470",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/employees/pages?limit=10",
                            "host": ["{{base_url}}"], "path": ["employees", "pages"],
                            "query": [{"key": "limit", "value": "10"}]
                        }
                    },
                    "response": []
                },
                {
                    "name": "Search Employees",
                    "id": "a58d8c0a-6027-4208-864a-4bb79464f4c8",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/employees/search?query=juan&page=1&limit=10",
                            "host": ["{{base_url}}"], "path": ["employees", "search"],
                            "query": [{"key": "query", "value": "juan"}, {"key": "page", "value": "1"}, {"key": "limit", "value": "10"}]
                        }
                    },
                    "response": []
                },
                {
                    "name": "Update Employee",
                    "id": "16d04f00-9903-4c70-bae2-95edddda4409",
                    "request": {
                        "method": "PUT",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "first_name": "Juan",
                                "last_name": "Dela Cruz",
                                "middle_name": "Santos",
                                "email": "juan@deped.gov.ph",
                                "employee_type": "TEACHING",
                                "employment_status": "PERMANENT",
                                "school_id": 1,
                                "department": "Mathematics"
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {"raw": "{{base_url}}/employees/1", "host": ["{{base_url}}"], "path": ["employees", "1"]}
                    },
                    "response": []
                },
                {
                    "name": "Delete Employee",
                    "id": "3eabe756-7e9d-49c9-bebc-0337237ea864",
                    "request": {
                        "method": "DELETE", "header": [],
                        "url": {"raw": "{{base_url}}/employees/1", "host": ["{{base_url}}"], "path": ["employees", "1"]}
                    },
                    "response": []
                },
                {
                    "name": "Get Employee Leave Balances",
                    "id": "ed15f6a3-d898-4d5a-8379-9dfae055f312",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/employees/1/leave-balances",
                            "host": ["{{base_url}}"], "path": ["employees", "1", "leave-balances"]
                        },
                        "description": "Returns all leave balances for a specific employee, joined with leave type details."
                    },
                    "response": []
                },
                {
                    "name": "Upload Employee Photo",
                    "id": new_id(),
                    "request": {
                        "method": "POST",
                        "header": [],
                        "body": {
                            "mode": "formdata",
                            "formdata": [{"key": "photo", "type": "file", "src": ""}]
                        },
                        "url": {
                            "raw": "{{base_url}}/employees/1/photo",
                            "host": ["{{base_url}}"], "path": ["employees", "1", "photo"]
                        },
                        "description": "Uploads a photo for an employee (multipart/form-data). Replaces any existing photo. Returns the updated employee record. data.photo contains a signed, expiring URL valid for 10 minutes."
                    },
                    "response": []
                },
                {
                    "name": "Get Employee Photo",
                    "id": new_id(),
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}/uploads/employee_photos/<filename>?expires=<ts>&signature=<sig>",
                            "host": ["{{base_url}}"],
                            "path": ["uploads", "employee_photos", "<filename>"],
                            "query": [{"key": "expires", "value": "<ts>"}, {"key": "signature", "value": "<sig>"}]
                        },
                        "description": "Serves a private employee photo file. Requires valid expires and signature from the signed URL returned in data.photo. Returns 403 if signature is invalid or expired."
                    },
                    "response": []
                }
            ]
        },
        # --------------------------
        # Leave Credits
        # --------------------------
        {
            "name": "Leave Credits",
            "item": [
                {
                    "name": "Credit VL or SL Balance",
                    "id": "bb6621a3-2549-447e-8823-19243273daae",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "employee_id": 1,
                                "leave_type_id": 1,
                                "amount": 1.25,
                                "transaction_date": "2026-06-17",
                                "remarks": "Monthly VL credit"
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {"raw": "{{base_url}}/leave-credits", "host": ["{{base_url}}"], "path": ["leave-credits"]},
                        "description": "Credits VL or SL days to an employee balance. leave_type_id must correspond to VL or SL. Inserts a CREDIT into the ledger and updates the cached balance."
                    },
                    "response": []
                }
            ]
        },
        # --------------------------
        # Leave Applications
        # --------------------------
        {
            "name": "Leave Applications",
            "item": [
                {
                    "name": "Submit Leave Application",
                    "id": "958b3997-4359-4299-bc83-6a703f85060b",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "employee_id": 1,
                                "leave_type_id": 1,
                                "date_filed": "2026-06-17",
                                "start_date": "2026-06-20",
                                "end_date": "2026-06-22",
                                "reason": "Personal matters",
                                "with_pay": True,
                                "other_leave_description": None
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {"raw": "{{base_url}}/leave-applications", "host": ["{{base_url}}"], "path": ["leave-applications"]},
                        "description": "Submits a leave application. Balance is validated but NOT deducted until approved."
                    },
                    "response": []
                },
                {
                    "name": "Get All Leave Applications",
                    "id": new_id(),
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/leave-applications?page=1&limit=10",
                            "host": ["{{base_url}}"], "path": ["leave-applications"],
                            "query": [{"key": "page", "value": "1"}, {"key": "limit", "value": "10"}]
                        },
                        "description": "Returns a paginated list of all leave applications across all employees, ordered by date filed descending. Includes employee name and leave type details."
                    },
                    "response": []
                },
                {
                    "name": "Get Leave Application by ID",
                    "id": "e359e85c-2544-4308-8cee-2b5ab0c7af30",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/leave-applications/1",
                            "host": ["{{base_url}}"], "path": ["leave-applications", "1"]
                        },
                        "description": "Retrieves a single leave application by its primary key, including employee name and leave type details."
                    },
                    "response": []
                },
                {
                    "name": "Get Leave Applications by Employee",
                    "id": "c0e98737-a501-4e8a-bac8-9236718d4ed2",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/leave-applications/employee/1",
                            "host": ["{{base_url}}"], "path": ["leave-applications", "employee", "1"]
                        },
                        "description": "Retrieves all leave applications submitted by a specific employee, ordered by date filed descending."
                    },
                    "response": []
                }
            ]
        },
        # --------------------------
        # Leave Approvals
        # --------------------------
        {
            "name": "Leave Approvals",
            "item": [
                {
                    "name": "Decide Leave Application",
                    "id": "020b1d7f-86cb-4d77-b4e8-c12c21a4bbae",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "leave_application_id": 1,
                                "approver_id": 2,
                                "level": 1,
                                "status": "APPROVED",
                                "remarks": "Approved as requested"
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {"raw": "{{base_url}}/leave-approvals", "host": ["{{base_url}}"], "path": ["leave-approvals"]},
                        "description": "Processes an approval decision. APPROVED posts DEBIT to ledger and deducts from balance cache. REJECTED marks application as rejected."
                    },
                    "response": []
                },
                {
                    "name": "Get Approvals by Application",
                    "id": "96c9ba0a-4690-4d4c-af86-682f312e8ee7",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/leave-approvals/application/1",
                            "host": ["{{base_url}}"], "path": ["leave-approvals", "application", "1"]
                        },
                        "description": "Retrieves all approval records for a specific leave application, ordered by level ascending."
                    },
                    "response": []
                }
            ]
        },
        # --------------------------
        # Service Credit Applications (CTO / VSC)
        # --------------------------
        {
            "name": "Service Credit Applications (CTO / VSC)",
            "item": [
                {
                    "name": "Submit Service Credit Application",
                    "id": new_id(),
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "employee_id": 1,
                                "type": "CTO",
                                "hours_rendered": 16,
                                "participation_dates": ["2026-06-10", "2026-06-11"],
                                "date_filed": "2026-06-17"
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {
                            "raw": "{{base_url}}/service-credit-applications",
                            "host": ["{{base_url}}"], "path": ["service-credit-applications"]
                        },
                        "description": "Submits a CTO or VSC service credit application.\n- type: CTO | VSC\n- balance_earned is auto-computed (hours_rendered / 8 * 1.5)\n- expiration_date is auto-computed for CTO (1 year from latest participation date); null for VSC\nCreated as PENDING. Credit is NOT posted to the ledger until approved."
                    },
                    "response": []
                },
                {
                    "name": "Decide Service Credit Application",
                    "id": new_id(),
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "service_credit_application_id": 1,
                                "approver_id": 2,
                                "status": "APPROVED",
                                "remarks": "Approved - activity verified"
                            }, indent=2),
                            "options": {"raw": {"language": "json"}}
                        },
                        "url": {
                            "raw": "{{base_url}}/service-credit-applications/decide",
                            "host": ["{{base_url}}"], "path": ["service-credit-applications", "decide"]
                        },
                        "description": "Processes an APPROVED or REJECTED decision.\nOn APPROVED: posts CREDIT to leave_credit_transactions (source_type=SPECIAL_ORDER) for the matching leave type (CTO or VSC) and updates the employee balance cache.\nOn REJECTED: records rejection only."
                    },
                    "response": []
                },
                {
                    "name": "Get All Service Credit Applications",
                    "id": new_id(),
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/service-credit-applications?page=1&limit=10",
                            "host": ["{{base_url}}"], "path": ["service-credit-applications"],
                            "query": [{"key": "page", "value": "1"}, {"key": "limit", "value": "10"}]
                        },
                        "description": "Returns a paginated list of all service credit applications (CTO and VSC) across all employees, ordered by date filed descending. Each record includes a participation_dates list."
                    },
                    "response": []
                },
                {
                    "name": "Get Service Credit Application by ID",
                    "id": new_id(),
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/service-credit-applications/1",
                            "host": ["{{base_url}}"], "path": ["service-credit-applications", "1"]
                        },
                        "description": "Retrieves a single service credit application by its primary key, including employee details and participation_dates list."
                    },
                    "response": []
                },
                {
                    "name": "Get Service Credit Applications by Employee",
                    "id": new_id(),
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/service-credit-applications/employee/1",
                            "host": ["{{base_url}}"], "path": ["service-credit-applications", "employee", "1"]
                        },
                        "description": "Retrieves all service credit applications (CTO and VSC) submitted by a specific employee, ordered by creation date descending. Each record includes a participation_dates list."
                    },
                    "response": []
                }
            ]
        },
        # --------------------------
        # Leave Types
        # --------------------------
        {
            "name": "Leave Types",
            "item": [
                {
                    "name": "Get All Leave Types",
                    "id": "c627792d-cf95-4f24-88e9-df4e5969cb94",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {"raw": "{{base_url}}/leave-types", "host": ["{{base_url}}"], "path": ["leave-types"]},
                        "description": "Returns all leave types ordered by code. Includes code, name, balance_type (SELF / CHARGED_TO_VL / NONE), and is_active flag."
                    },
                    "response": []
                }
            ]
        },
        # --------------------------
        # Leave Credit Transactions
        # --------------------------
        {
            "name": "Leave Credit Transactions",
            "item": [
                {
                    "name": "Get Transactions by Employee",
                    "id": "ae612d41-7ab7-43d0-a7e6-58d4570000dd",
                    "request": {
                        "method": "GET", "header": [],
                        "url": {
                            "raw": "{{base_url}}/leave-credit-transactions/employee/1?page=1&limit=10",
                            "host": ["{{base_url}}"], "path": ["leave-credit-transactions", "employee", "1"],
                            "query": [{"key": "page", "value": "1"}, {"key": "limit", "value": "10"}]
                        },
                        "description": "Returns paginated ledger transactions (CREDIT and DEBIT) for a specific employee, ordered by transaction date descending. Includes leave type code and name."
                    },
                    "response": []
                }
            ]
        }
    ]
}

resp = requests.put(
    f"https://api.getpostman.com/collections/{COLLECTION_UID}",
    headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
    json={"collection": collection}
)
data = resp.json()
if resp.status_code == 200:
    print(f"OK — updated: {data.get('collection', {}).get('name')}")
else:
    print(f"ERROR {resp.status_code}: {data}")
