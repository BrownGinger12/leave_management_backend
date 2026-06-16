# DepEd Leave Management API

Base URL: `http://localhost:5000`

---

## Employees

### POST `/employees`
Create a new employee. `leave_card_number` is auto-generated if not provided.

**Body**
```json
{
  "employee_number": "EMP-2024-0001",
  "first_name": "Juan",
  "last_name": "Dela Cruz",
  "middle_name": "Santos",
  "email": "juan.delacruz@deped.gov.ph",
  "employee_type": "TEACHING",
  "employment_status": "PERMANENT",
  "school_id": 1,
  "leave_card_number": ""
}
```
> `employee_type`: `TEACHING` | `NON_TEACHING`  
> `employment_status`: `PERMANENT` | `TEMPORARY` | `CASUAL` | `CONTRACT_OF_SERVICE`  
> `leave_card_number`: leave empty to auto-generate (`LC-XXXXXXXX`), or provide your own

**Response** `201`
```json
{
  "statusCode": 201,
  "message": "Employee created",
  "data": { ...employee }
}
```

---

### GET `/employees?page=1&limit=10`
Get paginated list of employees.

**Query Params**
| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number |
| `limit` | `10` | Records per page |

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 10,
  "total": 50,
  "page": 1,
  "limit": 10,
  "data": [ ...employees ]
}
```

---

### GET `/employees/<id>`
Get a single employee by ID.

**Response** `200`
```json
{
  "statusCode": 200,
  "data": { ...employee }
}
```

---

### GET `/employees/count`
Get total number of employees.

**Response** `200`
```json
{
  "statusCode": 200,
  "total_employees": 50
}
```

---

### GET `/employees/pages?limit=10`
Get total number of pages based on limit.

**Response** `200`
```json
{
  "statusCode": 200,
  "total_employees": 50,
  "limit": 10,
  "total_pages": 5
}
```

---

### GET `/employees/search?query=juan&page=1&limit=10`
Search employees by name, employee number, or email.

**Query Params**
| Param | Required | Description |
|-------|----------|-------------|
| `query` | Yes | Search keyword |
| `page` | No | Page number (default `1`) |
| `limit` | No | Records per page (default `10`) |

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 2,
  "data": [ ...employees ]
}
```

---

### PUT `/employees/<id>`
Update an existing employee. Only include fields to change.

**Body**
```json
{
  "first_name": "Juan",
  "last_name": "Dela Cruz",
  "middle_name": "Santos",
  "email": "juan@deped.gov.ph",
  "employee_type": "TEACHING",
  "employment_status": "PERMANENT",
  "school_id": 1
}
```

**Response** `200`
```json
{
  "statusCode": 200,
  "message": "Employee updated",
  "data": { ...employee }
}
```

---

### DELETE `/employees/<id>`
Delete an employee by ID.

**Response** `200`
```json
{
  "statusCode": 200,
  "message": "Employee deleted"
}
```

---

## Leave Credits

### POST `/leave-credits`
Credit VL or SL days to an employee's balance. Posts a `CREDIT` entry to the ledger and updates the balance cache.

**Body**
```json
{
  "employee_id": 1,
  "leave_type_id": 1,
  "amount": 1.25,
  "transaction_date": "2026-06-15",
  "remarks": "Monthly VL credit"
}
```
> `leave_type_id` must correspond to **VL** or **SL** only.

**Response** `201`
```json
{
  "statusCode": 201,
  "message": "VL credit of 1.25 day(s) applied successfully",
  "balance_before": 0.0,
  "balance_after": 1.25,
  "data": { ...transaction }
}
```

---

## Leave Applications

### POST `/leave-applications`
Submit a leave application. Validates employee balance before inserting. Created as `PENDING` — balance is **not** deducted until approved.

**Balance check rules by leave type:**
| Leave Type | Rule | Balance Checked |
|---|---|---|
| VL, SL, SPL | `SELF` | Own balance |
| FL | `CHARGED_TO_VL` | FL entitlement **and** VL balance |
| ML, PL, SLB, VAWC, OL | `NONE` | No check |

**Body**
```json
{
  "employee_id": 1,
  "leave_type_id": 1,
  "date_filed": "2026-06-15",
  "start_date": "2026-06-20",
  "end_date": "2026-06-22",
  "reason": "Personal matters",
  "other_leave_description": null
}
```
> `other_leave_description`: required only when leave type is **Others (OL)**

**Response** `201`
```json
{
  "statusCode": 201,
  "message": "Leave application submitted successfully",
  "data": { ...application }
}
```

**Insufficient balance response** `400`
```json
{
  "statusCode": 400,
  "message": "Insufficient VL balance",
  "leave_type_checked": "VL",
  "required_days": 3.0,
  "available_days": 1.25,
  "shortfall_days": 1.75
}
```

---

### GET `/leave-applications/<id>`
Get a single leave application by ID. Includes employee name and leave type details.

**Response** `200`
```json
{
  "statusCode": 200,
  "data": { ...application }
}
```

---

### GET `/leave-applications/employee/<employee_id>`
Get all leave applications for a specific employee, ordered by date filed descending.

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 3,
  "data": [ ...applications ]
}
```

---

### GET `/leave-applications?page=1&limit=10`
Get a paginated list of all leave applications across all employees, ordered by date filed descending. Includes employee name and leave type details.

**Query Params**
| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number |
| `limit` | `10` | Records per page |

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 10,
  "total": 45,
  "page": 1,
  "limit": 10,
  "data": [ ...applications ]
}
```

---

## Leave Approvals

### POST `/leave-approvals`
Submit an approval decision on a `PENDING` leave application.

- `APPROVED` → records approval, posts `DEBIT` to ledger, deducts from balance cache, sets application to `APPROVED`
- `REJECTED` → records rejection, sets application to `REJECTED`

**Body**
```json
{
  "leave_application_id": 1,
  "approver_id": 2,
  "level": 1,
  "status": "APPROVED",
  "remarks": "Approved as requested"
}
```
> `status`: `APPROVED` | `REJECTED`

**Response** `200`
```json
{
  "statusCode": 200,
  "message": "Leave application approved successfully",
  "data": { ...approval }
}
```

---

### GET `/leave-approvals/application/<application_id>`
Get all approval records for a specific leave application, ordered by level ascending.

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 1,
  "data": [ ...approvals ]
}
```

---

## CTO Applications

### POST `/cto-applications`
Submit a CTO application documenting an activity/event rendered. Created as `PENDING` — CTO credit is **not** posted until approved.

**Body**
```json
{
  "employee_id": 1,
  "activity_name": "Regional Year-End Assessment",
  "activity_start_date": "2026-06-10",
  "activity_end_date": "2026-06-12",
  "participation_start_date": "2026-06-10",
  "participation_end_date": "2026-06-12",
  "days_rendered": 3,
  "special_order_number": "SO-2026-001",
  "date_filed": "2026-06-16"
}
```
> Participation dates must fall within activity dates.  
> `special_order_number` is optional.

**Response** `201`
```json
{
  "statusCode": 201,
  "message": "CTO application submitted successfully",
  "data": { ...application }
}
```

---

### POST `/cto-applications/decide`
Process an APPROVED or REJECTED decision on a `PENDING` CTO application.

- `APPROVED` → posts `CREDIT` to ledger (`source_type: SPECIAL_ORDER`), updates CTO balance cache, sets application to `APPROVED`
- `REJECTED` → records rejection only

**Body**
```json
{
  "cto_application_id": 1,
  "approver_id": 2,
  "status": "APPROVED",
  "remarks": "Approved — activity verified"
}
```
> `status`: `APPROVED` | `REJECTED`

**Response** `200`
```json
{
  "statusCode": 200,
  "message": "CTO application approved successfully",
  "data": { ...application }
}
```

---

### GET `/cto-applications/<id>`
Get a single CTO application by ID including employee details.

**Response** `200`
```json
{
  "statusCode": 200,
  "data": { ...application }
}
```

---

### GET `/cto-applications/employee/<employee_id>`
Get all CTO applications for a specific employee, ordered by creation date descending.

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 2,
  "data": [ ...applications ]
}
```

---

### GET `/cto-applications?page=1&limit=10`
Get a paginated list of all CTO applications across all employees, ordered by date filed descending. Includes employee name and employee number.

**Query Params**
| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number |
| `limit` | `10` | Records per page |

**Response** `200`
```json
{
  "statusCode": 200,
  "count": 10,
  "total": 23,
  "page": 1,
  "limit": 10,
  "data": [ ...applications ]
}
```

---

## Error Responses

All endpoints return a consistent error format:

| Status | Meaning |
|--------|---------|
| `400` | Bad request — missing field, invalid value, or insufficient balance |
| `404` | Resource not found |
| `409` | Conflict — duplicate record (e.g. duplicate employee number) |
| `500` | Internal server error |

```json
{
  "statusCode": 400,
  "message": "Description of the error"
}
```
