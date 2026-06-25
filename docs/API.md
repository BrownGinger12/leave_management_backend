# DepEd Leave Management API

Base URL: `http://localhost:5000`

All protected routes require: `Authorization: Bearer <token>`

---

## Schools

### GET `/schools`

Returns all schools in the division ordered alphabetically by name.

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 69,
  "data": [
    { "id": 1, "name": "Agudo E/S" },
    { "id": 2, "name": "Alimatoc E/S" }
  ]
}
```

---

## Calendar Events

### GET `/calendar-events`

Returns all holidays for a given year, ordered by date ascending. Requires auth.

**Query Parameters** (optional)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `year` | int | current year | Calendar year to filter by |

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 2,
  "data": [
    {
      "id": 1,
      "date": "2026-01-01",
      "name": "New Year's Day",
      "blocks_leave": 1,
      "period": "FULL",
      "created_by": 1,
      "created_at": "2026-06-24T10:00:00"
    }
  ]
}
```

---

### GET `/calendar-events/current-month`

Returns all holidays for the current calendar month, ordered by date ascending. Requires auth.

**Response** `200`

```json
{
  "statusCode": 200,
  "year": 2026,
  "month": 6,
  "count": 1,
  "data": [...]
}
```

---

### POST `/calendar-events`

Creates a new holiday. **Admin only.**

**Headers:** `Authorization: Bearer <token>`

**Body**

```json
{
  "date": "2026-12-25",
  "name": "Christmas Day",
  "blocks_leave": 1,
  "period": "FULL"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | string | Yes | YYYY-MM-DD. Must be unique per date. |
| `name` | string | Yes | Display name (e.g. "Christmas Day"). |
| `blocks_leave` | int | No | `1` = leave blocked on this date, `0` = allowed. Default `0`. |
| `period` | string | No | `FULL` = full day, `AM` = morning half, `PM` = afternoon half. Default `FULL`. |

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "Calendar event created successfully",
  "id": 1
}
```

---

### PUT `/calendar-events/<id>`

Updates an existing holiday by ID. **Admin only.**

**Headers:** `Authorization: Bearer <token>`

**Body** (all fields optional)

```json
{
  "name": "Christmas Day",
  "blocks_leave": 1,
  "period": "AM"
}
```

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Calendar event updated successfully"
}
```

---

### DELETE `/calendar-events/<id>`

Deletes a holiday by ID. **Admin only.**

**Headers:** `Authorization: Bearer <token>`

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Calendar event deleted successfully"
}
```

---

## Positions

### GET `/positions`

Returns all positions. Optionally filter by category using the `type` query parameter.

**Query Parameters** (optional)

| Parameter | Type   | Values                     | Description                           |
| --------- | ------ | -------------------------- | ------------------------------------- |
| `type`    | string | `TEACHING`, `NON_TEACHING` | Filter positions by employee category |

**Examples**

- `GET /positions` — all positions (40 non-teaching + 13 teaching)
- `GET /positions?type=TEACHING` — teaching positions only
- `GET /positions?type=NON_TEACHING` — non-teaching positions only

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 53,
  "data": [
    { "id": 1, "name": "Administrative Aide I", "type": "NON_TEACHING" },
    { "id": 2, "name": "Teacher I", "type": "TEACHING" }
  ]
}
```

---

## Authentication

### POST `/auth/login`

Authenticate and receive a JWT token (valid for 8 hours).

**Body**

```json
{
  "username": "jdelacruz",
  "password": "your_password"
}
```

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Login successful",
  "token": "<jwt>",
  "user": {
    "id": 1,
    "employee_id": 1,
    "username": "jdelacruz",
    "role": "ADMIN",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001"
  }
}
```

---

### GET `/auth/me`

Returns the profile of the currently authenticated user.

**Headers** — `Authorization: Bearer <token>`

**Response** `200`

```json
{
  "statusCode": 200,
  "data": { ...user }
}
```

---

## Users _(ADMIN only)_

> All `/users` endpoints require an ADMIN token.

### POST `/users`

Create a new user account linked to an existing employee.

**Headers** — `Authorization: Bearer <admin-token>`

**Body**

```json
{
  "employee_id": 1,
  "username": "jdelacruz",
  "password": "SecurePassword123",
  "role": "TEACHING_PERSONNEL"
}
```

> `role`: `ADMIN` | `DIVISION_PERSONNEL` | `TEACHING_PERSONNEL`
> One account per employee. Username must be unique.

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "User account created",
  "data": { ...user }
}
```

---

### GET `/users?page=1&limit=10`

Get a paginated list of all user accounts.

**Headers** — `Authorization: Bearer <admin-token>`

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 10,
  "total": 25,
  "page": 1,
  "limit": 10,
  "data": [ ...users ]
}
```

---

### GET `/users/<id>`

Get a single user account by ID.

**Headers** — `Authorization: Bearer <admin-token>`

**Response** `200`

```json
{
  "statusCode": 200,
  "data": { ...user }
}
```

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
  "division": "Schools Division of Manila",
  "original_appointment": "2015-06-01",
  "latest_appointment": "2022-01-15",
  "position": "Teacher III",
  "salary": 35000.0,
  "contact_number": "09171234567",
  "is_active": true,
  "leave_card_number": ""
}
```

> `division`, `original_appointment`, `latest_appointment`, `position`, `salary`, `contact_number`: optional
> `is_active`: optional, defaults to `true`; set to `false` to soft-delete
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

Search employees by name, employee number, leave card number, or email.

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
  "school_id": 1,
  "division": "Schools Division of Manila",
  "original_appointment": "2015-06-01",
  "latest_appointment": "2022-01-15",
  "position": "Teacher III",
  "salary": 35000.0,
  "contact_number": "09171234567",
  "is_active": true
}
```

> All fields are optional. Only include fields you want to change.

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

### GET `/employees/<id>/leave-balances`

Get all current leave balances for a specific employee, joined with leave type details.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": {
    "id": 1,
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001"
  },
  "data": [
    {
      "id": 1,
      "balance": 100.0,
      "leave_type_id": 1,
      "code": "VL",
      "name": "Vacation Leave",
      "balance_type": "SELF"
    }
  ]
}
```

> Returns an empty `data` array if the employee has no balances yet.

---

### POST `/employees/<id>/photo`

Upload a photo for an employee. Replaces and deletes any previously uploaded photo.

**Body** — `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `photo` | file | Image file. Allowed: `png`, `jpg`, `jpeg`, `gif` |

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Employee photo uploaded successfully",
  "data": { ...employee }
}
```

> `data.photo` holds a **signed, expiring URL** valid for **10 minutes**. Any endpoint that returns an employee record returns `photo` in this signed form.

---

### GET `/uploads/employee_photos/<filename>?expires=<ts>&signature=<sig>`

Serves an uploaded employee photo. Requires a valid, non-expired `expires`/`signature` pair from the signed URL in `data.photo`.

**Response** `200` — the image file, `403` if invalid/expired, `404` if not found.

---

## Monthly Leave Credits

Tracks monthly VL and SL accrual (typically 1.25 days each per month). A `UNIQUE` constraint on `(employee_id, leave_type_id, year, month)` prevents double-crediting.

### POST `/monthly-leave-credits`

Credit one month of VL or SL for an employee. Returns `409` if already credited for that month.

**Body**

```json
{
  "employee_id": 1,
  "leave_type_id": 1,
  "year": 2026,
  "month": 6,
  "amount": 1.25,
  "transaction_date": "2026-06-30",
  "remarks": "June 2026 monthly VL credit"
}
```

> `leave_type_id` must correspond to **VL** or **SL** only.
> `month`: 1–12.
> `transaction_date`: use the last day of the month (e.g. `2026-06-30`).
> `remarks`: optional.

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "VL credit of 1.25 day(s) applied for 2026-06",
  "balance_before": 10.0,
  "balance_after": 11.25,
  "data": { ...monthly_credit with ledger details }
}
```

**Already credited** `409`

```json
{
  "statusCode": 409,
  "message": "VL has already been credited for 2026-06"
}
```

---

### GET `/monthly-leave-credits/employee/<employee_id>/year/<year>`

Get all monthly VL/SL credits for an employee in a given year, each including its linked ledger transaction.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": {
    "id": 1,
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001"
  },
  "year": 2026,
  "count": 2,
  "data": [
    {
      "id": 1,
      "leave_type_code": "VL",
      "year": 2026,
      "month": 6,
      "amount": 1.25,
      "transaction_number": "TXN-A1B2C3D4",
      "transaction_type": "CREDIT",
      "balance_snapshot_after": 11.25,
      "transaction_date": "2026-06-30",
      "ledger_remarks": "June 2026 monthly VL credit"
    }
  ]
}
```

---

## Leave Credits

### POST `/leave-credits`

Manually credit leave days to an employee's balance. Accepts **any active leave type** (VL, SL, CTO, VSC, SPL, WL, FL, etc.). Posts a `CREDIT` to the ledger and triggers a cascading balance recalculation.

**Body**

```json
{
  "employee_id": 1,
  "leave_type_id": 1,
  "amount": 5.0,
  "transaction_date": "2026-06-30",
  "remarks": "Initial FL credit"
}
```

> `remarks`: optional.

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "VL credit of 5.0 day(s) applied successfully",
  "balance_before": 0.0,
  "balance_after": 5.0,
  "data": { ...transaction }
}
```

---

## Leave Applications

### Leave Application Status Values

| Status            | Description                                                  |
| ----------------- | ------------------------------------------------------------ |
| `FOR HRMO ACTION` | Initial status — application submitted, awaiting HRMO review |
| `FOR APPROVAL`    | HRMO processed — forwarded to next approval level            |
| `APPROVED`        | Final approval granted                                       |
| `RETURNED`        | Returned to employee for correction — balance restored       |
| `DISAPPROVED`     | Final rejection — balance restored                           |

> Balance is deducted **at submission**. It is only restored if the application is `RETURNED` or `DISAPPROVED`.

---

### Leave Date Structure

Each application stores its dates individually in `leave_application_dates`. `start_date`, `end_date`, and `total_days` are **derived** from these records — not stored on the application header.

**Duration calculation:**
| `duration_type` | `half_day_period` | Days counted |
|---|---|---|
| `FULL_DAY` | `null` | 1.0 |
| `HALF_DAY` | `AM` | 0.5 |
| `HALF_DAY` | `PM` | 0.5 |

---

### POST `/leave-applications`

Submit a leave application with individual leave dates. Validates holidays, overlaps, and balance before inserting. Created with status `FOR HRMO ACTION`. **Balance is deducted immediately on submission.**

**Balance check rules by leave type:**
| Leave Type | Rule | Balance Checked |
|---|---|---|
| VL, SL, SPL, CTO, VSC, WL | `SELF` | Own balance |
| FL | `CHARGED_TO_VL` | FL entitlement **and** VL balance |
| ML, PL, SLB, VAWC, OL | `NONE` | No check |

> For FL: two DEBIT entries are posted on submission — one from FL balance and one from VL balance.

**Body**

```json
{
  "employee_id": 1,
  "leave_type_id": 1,
  "date_filed": "2026-07-10",
  "reason": "Personal matters",
  "other_leave_description": null,
  "dates": [
    {
      "leave_date": "2026-07-21",
      "duration_type": "FULL_DAY",
      "half_day_period": null,
      "is_paid": true
    },
    {
      "leave_date": "2026-07-22",
      "duration_type": "HALF_DAY",
      "half_day_period": "AM",
      "is_paid": true
    },
    {
      "leave_date": "2026-07-23",
      "duration_type": "HALF_DAY",
      "half_day_period": "PM",
      "is_paid": false
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `employee_id` | int | Yes | FK to employees |
| `leave_type_id` | int | Yes | FK to leave_types |
| `date_filed` | string | Yes | YYYY-MM-DD |
| `reason` | string | Yes | Reason for leave |
| `other_leave_description` | string | No | Required only for Others (OL) leave type |
| `dates` | array | Yes | At least one date entry required |
| `dates[].leave_date` | string | Yes | YYYY-MM-DD |
| `dates[].duration_type` | string | Yes | `FULL_DAY` or `HALF_DAY` |
| `dates[].half_day_period` | string | Conditional | `AM` or `PM` — required when `duration_type` is `HALF_DAY` |
| `dates[].is_paid` | bool | No | Whether this date is paid leave. Defaults to `true` |

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "Leave application submitted successfully",
  "data": {
    "id": 1,
    "application_number": "LA-A1B2C3D4",
    "employee_id": 1,
    "leave_type_id": 1,
    "date_filed": "2026-07-10",
    "reason": "Personal matters",
    "status": "FOR HRMO ACTION",
    "status_updated_by": null,
    "start_date": "2026-07-21",
    "end_date": "2026-07-23",
    "total_days": 2.0,
    "leave_dates": [
      { "id": 1, "leave_date": "2026-07-21", "duration_type": "FULL_DAY", "half_day_period": null, "is_paid": 1 },
      { "id": 2, "leave_date": "2026-07-22", "duration_type": "HALF_DAY", "half_day_period": "AM", "is_paid": 1 },
      { "id": 3, "leave_date": "2026-07-23", "duration_type": "HALF_DAY", "half_day_period": "PM", "is_paid": 0 }
    ]
  }
}
```

**Holiday conflict** `400`

```json
{
  "statusCode": 400,
  "message": "Leave date conflicts detected",
  "errors": [
    "Leave cannot be applied on 2026-12-25 because it is a full-day holiday (Christmas Day).",
    "Leave cannot be applied on 2026-12-24 PM because it is a half-day holiday (Christmas Eve)."
  ]
}
```

**Overlapping leave** `400`

```json
{
  "statusCode": 400,
  "message": "Leave date conflicts detected",
  "errors": [
    "An overlapping leave already exists on 2026-07-21 (Application: LA-XXXXXXXX, Status: APPROVED)."
  ]
}
```

**Insufficient balance** `400`

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

### PUT `/leave-applications/<id>`

Replace the leave dates on an existing application. Only allowed when the application status is `FOR HRMO ACTION`. The old balance debit is reversed and a new debit is posted for the updated total. Holiday conflicts, overlaps (excluding this application's own old dates), and balance are all re-validated before any writes.

**Body** — only `dates` is required; same structure as POST

```json
{
  "dates": [
    { "leave_date": "2026-07-21", "duration_type": "FULL_DAY", "half_day_period": null, "is_paid": true },
    { "leave_date": "2026-07-22", "duration_type": "HALF_DAY", "half_day_period": "AM", "is_paid": true }
  ]
}
```

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Leave application updated successfully",
  "data": {
    "id": 1,
    "application_number": "LA-A1B2C3D4",
    "status": "FOR HRMO ACTION",
    "start_date": "2026-07-21",
    "end_date": "2026-07-22",
    "total_days": 1.5,
    "leave_dates": [
      { "leave_date": "2026-07-21", "duration_type": "FULL_DAY", "half_day_period": null, "is_paid": 1 },
      { "leave_date": "2026-07-22", "duration_type": "HALF_DAY", "half_day_period": "AM", "is_paid": 1 }
    ],
    "...": "..."
  }
}
```

**Wrong status** `400`

```json
{
  "statusCode": 400,
  "message": "Only applications with status 'FOR HRMO ACTION' can be edited. Current status: FOR APPROVAL"
}
```

> Holiday conflict, overlap, and insufficient balance errors follow the same shape as POST.

---

### DELETE `/leave-applications/<id>`

Soft-deletes a leave application. The record is kept in the database (`is_deleted = 1`) for recovery but is excluded from all GET queries and overlap checks. Records who deleted it and when.

**Balance reversal rules:**
| Status at deletion | Balance action |
|---|---|
| `FOR HRMO ACTION` | Reversed |
| `FOR APPROVAL` | Reversed |
| `APPROVED` | Reversed |
| `RETURNED` | No reversal (already restored) |
| `DISAPPROVED` | No reversal (already restored) |

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Leave application deleted successfully"
}
```

**Not found** `404`

```json
{
  "statusCode": 404,
  "message": "Leave application not found"
}
```

---

### GET `/leave-applications/<id>`

Get a single leave application by ID. Includes employee info, leave type, individual leave dates, and derived `start_date`, `end_date`, `total_days`.

**Response** `200`

```json
{
  "statusCode": 200,
  "data": {
    "id": 1,
    "application_number": "LA-A1B2C3D4",
    "status": "APPROVED",
    "date_filed": "2026-07-10",
    "start_date": "2026-07-21",
    "end_date": "2026-07-23",
    "total_days": 2.0,
    "leave_dates": [
      { "leave_date": "2026-07-21", "duration_type": "FULL_DAY", "half_day_period": null, "is_paid": 1 },
      { "leave_date": "2026-07-22", "duration_type": "HALF_DAY", "half_day_period": "AM", "is_paid": 1 },
      { "leave_date": "2026-07-23", "duration_type": "HALF_DAY", "half_day_period": "PM", "is_paid": 0 }
    ],
    "...": "..."
  }
}
```

---

### GET `/leave-applications/employee/<employee_id>`

Get all leave applications for a specific employee, ordered by date filed descending. **Excludes CTO and VSC.** Each application includes its leave dates and derived fields.

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 3,
  "data": [ ...applications with leave_dates ]
}
```

---

### GET `/leave-applications/employee/<employee_id>/year/<year>`

Get all leave applications for an employee in a given calendar year. Results are ordered **chronologically ascending** (oldest first). Each application includes `deduction` and `balance_after` computed as a running total — behaves like an Excel ledger column.

**Running balance rules:**

| Status | `deduction` | Effect on `balance_after` |
|---|---|---|
| `FOR HRMO ACTION`, `FOR APPROVAL`, `APPROVED` | `-total_days` | Balance decreases |
| `RETURNED`, `DISAPPROVED` | `0.0` | Balance unchanged — cascades forward to subsequent rows |
| Leave type `balance_type = NONE` | `-total_days` | `balance_after` is `null` |

> For `FL` (Forced Leave, `CHARGED_TO_VL`), `balance_after` tracks the **VL balance** since FL deductions come from VL.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": { "id": 1, "first_name": "Juan", "last_name": "Dela Cruz", "employee_number": "EMP-2024-0001" },
  "year": 2026,
  "count": 2,
  "data": [
    {
      "id": 1,
      "application_number": "LA-A1B2C3D4",
      "leave_type_code": "VL",
      "balance_type": "SELF",
      "status": "DISAPPROVED",
      "date_filed": "2026-07-01",
      "start_date": "2026-07-21",
      "end_date": "2026-07-22",
      "total_days": 2.0,
      "deduction": 0.0,
      "balance_after": 100.0,
      "leave_dates": [ "..." ]
    },
    {
      "id": 2,
      "application_number": "LA-B2C3D4E5",
      "leave_type_code": "VL",
      "balance_type": "SELF",
      "status": "FOR HRMO ACTION",
      "date_filed": "2026-07-05",
      "start_date": "2026-07-28",
      "end_date": "2026-07-28",
      "total_days": 1.0,
      "deduction": -1.0,
      "balance_after": 99.0,
      "leave_dates": [ "..." ]
    }
  ]
}
```

---

### GET `/leave-applications?page=1&limit=10`

Get a paginated list of all leave applications, ordered by date filed descending. **Excludes CTO and VSC** — use `/leave-applications/cto-vsc` for those.

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
  "data": [ ...applications with leave_dates ]
}
```

---

### GET `/leave-applications/cto-vsc?page=1&limit=10`

Get a paginated list of CTO and VSC leave applications only, ordered by date filed descending.

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 5,
  "total": 12,
  "page": 1,
  "limit": 10,
  "data": [ ...applications with leave_dates ]
}
```

---

### GET `/leave-applications/cto-vsc/employee/<employee_id>`

Get all CTO and VSC leave applications for a specific employee, ordered by date filed descending.

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 3,
  "data": [ ...applications with leave_dates ]
}
```

---

### GET `/leave-applications/number/<application_number>`

Get a single leave application by its unique application number. Includes leave dates and derived fields.

**Example:** `GET /leave-applications/number/LA-A1B2C3D4`

**Response** `200`

```json
{
  "statusCode": 200,
  "data": { ...application with leave_dates }
}
```

---

### GET `/leave-applications/search`

Paginated search with optional filters. All filters are optional and combinable. Results ordered by `date_filed` descending.

**Query Params**
| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `year` | int | `2026` | Filter by calendar year of `date_filed` |
| `date_from` | string | `2026-01-01` | Lower bound of `date_filed` (YYYY-MM-DD) |
| `date_to` | string | `2026-06-30` | Upper bound of `date_filed` (YYYY-MM-DD) |
| `status` | string | `FOR APPROVAL` | Filter by application status |
| `leave_type_code` | string | `VL` | Filter by leave type code |
| `page` | int | `1` | Page number (default `1`) |
| `limit` | int | `10` | Records per page (default `10`) |

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 5,
  "total": 12,
  "page": 1,
  "limit": 10,
  "filters": { "year": 2026, "status": "FOR APPROVAL" },
  "data": [ ...applications with leave_dates ]
}
```

---

## Leave Approvals

### POST `/leave-approvals`

Submit an approval decision on a leave application. All status transitions are allowed, including re-activating an accidentally returned or disapproved application.

**Transition rules and balance behavior:**

| From status | To status | Balance effect |
|---|---|---|
| Any active | `RETURNED` / `DISAPPROVED` | CREDIT posted — balance restored |
| `RETURNED` / `DISAPPROVED` | Any active | DEBIT re-posted — balance re-reserved |
| Active → Active | (e.g. `FOR APPROVAL` → `APPROVED`) | No balance change |
| Reversed → Reversed | (e.g. `RETURNED` → `DISAPPROVED`) | No balance change |

> "Active" = `FOR HRMO ACTION`, `FOR APPROVAL`, `APPROVED`
> Re-activating from `RETURNED`/`DISAPPROVED` requires sufficient balance; returns `400` if insufficient.
> For FL (`CHARGED_TO_VL`), balance checked/affected is VL.
> `status_updated_by` on the application is automatically set to `approver_id`.

**Body**

```json
{
  "leave_application_id": 1,
  "approver_id": 2,
  "level": 1,
  "status": "FOR APPROVAL",
  "remarks": "Re-activating — accidentally disapproved"
}
```

> `status`: `FOR HRMO ACTION` | `FOR APPROVAL` | `APPROVED` | `RETURNED` | `DISAPPROVED`
> `remarks`: optional.

**Response** `200`

```json
{
  "statusCode": 200,
  "message": "Leave application status updated to 'FOR APPROVAL' successfully",
  "data": { ...approval }
}
```

**Insufficient balance on re-activation** `400`

```json
{
  "statusCode": 400,
  "message": "Insufficient VL balance to re-activate. Required: 6.0, Available: 3.0"
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
  "data": [
    {
      "id": 1,
      "leave_application_id": 1,
      "approver_id": 2,
      "level": 1,
      "status": "APPROVED",
      "remarks": "Approved as requested",
      "approved_at": "2026-07-22 10:30:00",
      "first_name": "Maria",
      "last_name": "Santos",
      "employee_number": "EMP-2024-0002"
    }
  ]
}
```

---

## Leave Credit Transactions (Ledger)

The ledger is the source of truth for all balance movements. `balance_snapshot_after` is always recomputed in chronological order (`transaction_date ASC, id ASC`) whenever a new entry is posted — like an Excel running total.

**`transaction_type`**: `CREDIT` (balance increases) | `DEBIT` (balance decreases)

**`source_type`**:
| Value | Origin |
|---|---|
| `SYSTEM_ADJUSTMENT` | Monthly VL/SL credit |
| `MANUAL_ADJUSTMENT` | Manual credit via `/leave-credits` |
| `LEAVE_APPLICATION` | DEBIT on submission, or CREDIT reversal on return/disapproval |
| `SPECIAL_ORDER` | CTO/VSC credit via service credit application |

---

### GET `/leave-credit-transactions/employee/<employee_id>/year/<year>`

Get all ledger transactions for an employee in a given calendar year, ordered by date descending.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": {
    "id": 1,
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001"
  },
  "year": 2026,
  "count": 5,
  "data": [
    {
      "id": 10,
      "transaction_number": "TXN-A1B2C3D4",
      "employee_id": 1,
      "leave_type_id": 1,
      "leave_type_code": "VL",
      "leave_type_name": "Vacation Leave",
      "transaction_type": "DEBIT",
      "amount": 2.0,
      "source_type": "LEAVE_APPLICATION",
      "source_id": 1,
      "transaction_date": "2026-07-21",
      "balance_snapshot_after": 98.0,
      "remarks": "Leave application submitted — VL deducted",
      "created_at": "2026-07-10 09:00:00"
    }
  ]
}
```

---

## Special Orders

Special Orders (SO) authorize CTO and VSC service credits. A Special Order must be created first before a service credit application can reference it.

### POST `/special-orders`

Create a new Special Order.

**Body**

```json
{
  "special_order": "SO-2026-001",
  "activity_name": "Regional Year-End Assessment",
  "reference": "REF-2026-001",
  "date_of_activity": "2026-06-10"
}
```

> `special_order`: **required** — SO number; must be unique (returns `409` if duplicate)
> `activity_name`: **required** — name of the activity
> `date_of_activity`: **required** — `YYYY-MM-DD`
> `reference`: optional

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "Special Order created successfully",
  "data": {
    "id": 1,
    "special_order": "SO-2026-001",
    "activity_name": "Regional Year-End Assessment",
    "reference": "REF-2026-001",
    "date_of_activity": "2026-06-10",
    "created_at": "2026-06-18 09:00:00"
  }
}
```

**Duplicate SO number** `409`

```json
{
  "statusCode": 409,
  "message": "Special Order 'SO-2026-001' already exists"
}
```

---

### GET `/special-orders/filter`

Filter Special Orders by year and/or date range on `date_of_activity`. All filters are optional and combinable. Results ordered by `date_of_activity` descending.

**Query Params**
| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `year` | int | `2026` | Filter by calendar year of `date_of_activity` |
| `date_from` | string | `2026-01-01` | Lower bound of `date_of_activity` (YYYY-MM-DD) |
| `date_to` | string | `2026-06-30` | Upper bound of `date_of_activity` (YYYY-MM-DD) |
| `page` | int | `1` | Page number (default `1`) |
| `limit` | int | `10` | Records per page (default `10`) |

> `date_from` and `date_to` can be combined for a range or used independently.
> `year` and `date_from`/`date_to` can be combined (e.g. narrow to a specific month within a year).

**Example:** `GET /special-orders/filter?year=2026&date_from=2026-06-01&date_to=2026-06-30`

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 3,
  "total": 5,
  "page": 1,
  "limit": 10,
  "filters": {
    "year": 2026,
    "date_from": "2026-06-01",
    "date_to": "2026-06-30"
  },
  "data": [ ...special_orders ]
}
```

> `filters` echoes back only the filters that were actually applied (omits unset ones).

---

### GET `/special-orders/search?q=<keyword>`

Search Special Orders by `special_order` number or `activity_name` using a partial match. Paginated.

**Query Params**
| Param | Required | Description |
|-------|----------|-------------|
| `q` | Yes | Search keyword — matched against `special_order` and `activity_name` |
| `page` | No | Page number (default `1`) |
| `limit` | No | Records per page (default `10`) |

**Example:** `GET /special-orders/search?q=SO-2026&page=1&limit=10`

**Response** `200`

```json
{
  "statusCode": 200,
  "query": "SO-2026",
  "count": 2,
  "total": 2,
  "page": 1,
  "limit": 10,
  "data": [ ...special_orders ]
}
```

**Missing query** `400`

```json
{
  "statusCode": 400,
  "message": "query is required"
}
```

---

### GET `/special-orders/<id>`

Get a single Special Order by ID.

**Response** `200`

```json
{
  "statusCode": 200,
  "data": { ...special_order }
}
```

---

### GET `/special-orders?page=1&limit=10`

Get a paginated list of all Special Orders, ordered by `date_of_activity` descending.

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
  "total": 25,
  "page": 1,
  "limit": 10,
  "data": [ ...special_orders ]
}
```

---

## Service Credit Applications (CTO / VSC)

CTO and VSC share the same table and endpoints. Use the `type` field to distinguish them.

- **CTO** (Compensatory Time Off) — expires 1 year from the latest participation date
- **VSC** (Vacation Service Credits) — no expiration

**Balance formula:** `balance_earned = hours_rendered / 8 × 1.5`

---

### POST `/service-credit-applications`

Submit a new CTO or VSC service credit application. **Balance is credited immediately on submission** — there is no approval step. A `CREDIT` is posted to the ledger (`source_type: SPECIAL_ORDER`) and the balance cache is updated automatically.

**Credit type is determined automatically from the employee's classification:**
| Employee Type | Credit Type |
|---|---|
| `TEACHING` | `VSC` (Vacation Service Credits) |
| `NON_TEACHING` | `CTO` (Compensatory Time Off) |

**Body**

```json
{
  "employee_id": 1,
  "special_order_id": 1,
  "hours_rendered": 16,
  "participation_dates": ["2026-06-10", "2026-06-11"],
  "date_filed": "2026-06-17",
  "date_of_upload": "2026-06-17",
  "uploaded_by": 2
}
```

> `special_order_id`: **required** — FK to `special_orders.id`; create the Special Order first via `POST /special-orders`
> `type` is **not accepted** — it is auto-derived from `employee_type` (TEACHING → VSC, NON_TEACHING → CTO)
> `participation_dates`: **required** — non-empty list of `YYYY-MM-DD` strings; the latest date determines `valid_until` for CTO
> `valid_until`: **auto-computed** — latest `participation_date` + 1 year (CTO only); always `null` for VSC
> `balance_earned` is auto-computed (`hours_rendered / 8 × 1.5`)
> `date_of_upload`, `uploaded_by`: optional
> `uploaded_by`: employee ID (FK to `employees.id`); returns 404 if the employee does not exist
> Activity name, reference, and date of activity are read from the linked Special Order and included in the response

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "CTO application submitted successfully",
  "data": {
    "id": 1,
    "application_number": "SC-A1B2C3D4",
    "employee_id": 1,
    "special_order_id": 1,
    "special_order": "SO-2026-001",
    "activity_name": "Regional Year-End Assessment",
    "type": "CTO",
    "hours_rendered": 16.0,
    "balance_earned": 3.0,
    "valid_until": "2027-06-11",
    "date_filed": "2026-06-17",
    "participation_dates": ["2026-06-10", "2026-06-11"]
  }
}
```

> Response includes joined Special Order fields: `special_order`, `activity_name`, `reference`, `date_of_activity`.

---

### GET `/service-credit-applications/<id>`

Get a single service credit application by ID, including employee details and participation dates.

**Response** `200`

```json
{
  "statusCode": 200,
  "data": { ...application }
}
```

---

### GET `/service-credit-applications/employee/<employee_id>/cto-leave-summary`

Returns all CTO service credit records for an employee, ordered by earliest `valid_until` first (credits with no expiry last). Each credit carries a `leave_applications` array of CTO leave applications that were primarily charged to it.

**Duplicate prevention**: when a leave application spans multiple credits, it is assigned to the credit whose `original_balance >= total_days` (the credit that could have covered the full leave without going negative); ties break by highest `credit_balance_id` (last record). If no single credit was large enough, it falls back to the credit with the largest `amount_deducted`; ties again break by highest `credit_balance_id`. Each leave application appears under exactly one credit.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": {
    "id": 1,
    "first_name": "...",
    "last_name": "...",
    "employee_number": "..."
  },
  "count": 2,
  "data": [
    {
      "credit_balance_id": 1,
      "service_credit_application_id": 3,
      "credit_application_number": "SC-XXXXXXXX",
      "original_balance": 3.0,
      "remaining_balance": 1.5,
      "valid_until": "2027-03-15",
      "special_order_number": "SO-2026-001",
      "activity_name": "Training Activity",
      "date_of_activity": "2026-03-15",
      "hours_rendered": 16.0,
      "balance_earned": 3.0,
      "date_filed": "2026-03-20",
      "date_of_upload": "2026-03-22",
      "uploaded_by": 2,
      "uploaded_by_name": "Juan Dela Cruz",
      "type": "CTO",
      "participation_dates": ["2026-03-14", "2026-03-15"],
      "leave_applications": [
        {
          "id": 5,
          "application_number": "LA-YYYYYYYY",
          "employee_id": 1,
          "leave_type_id": 6,
          "date_filed": "2026-04-08",
          "start_date": "2026-04-10",
          "end_date": "2026-04-11",
          "total_days": 2.0,
          "reason": "Personal rest",
          "other_leave_description": null,
          "status": "APPROVED",
          "with_pay": 1,
          "status_updated_by": 2,
          "created_at": "2026-04-08T09:00:00",
          "leave_type_code": "CTO",
          "leave_type_name": "Compensatory Time Off",
          "username": "jdelacruz",
          "remarks": "Approved — leave records verified",
          "date_of_action": "2026-04-09T10:30:00",
          "approver_name": "Maria Santos"
        }
      ]
    }
  ]
}
```

---

### GET `/service-credit-applications/employee/<employee_id>/vsc-old-leave-summary`

Returns all VSC service credit records earned from activities with `date_of_activity < 2024-10-01` for a teaching employee, each carrying the VSC leave applications primarily charged to it. No `valid_until` field (VSC does not expire).

**Routing rule**: when a VSC service credit is submitted, the system reads `date_of_activity` from the linked special order and inserts into `vsc_old_credit_balances` if `< 2024-10-01`, or `vsc_new_credit_balances` if `>= 2024-10-01`.

**Leave assignment**: each VSC leave is assigned to exactly one credit across both period tables. Priority is the credit whose `original_balance >= total_days` (won't go negative); ties break by highest `service_credit_application_id` (last record). Fallback: highest ID overall. No leave appears in both summaries.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": { "id": 3, "first_name": "...", "last_name": "...", "employee_number": "..." },
  "count": 1,
  "data": [
    {
      "credit_balance_id": 1,
      "service_credit_application_id": 2,
      "credit_application_number": "SC-XXXXXXXX",
      "original_balance": 3.0,
      "remaining_balance": 3.0,
      "special_order_number": "SO-2024-001",
      "activity_name": "Training Activity",
      "date_of_activity": "2024-08-15",
      "hours_rendered": 16.0,
      "balance_earned": 3.0,
      "date_filed": "2024-08-20",
      "date_of_upload": "2024-08-22",
      "uploaded_by": 2,
      "uploaded_by_name": "Juan Dela Cruz",
      "type": "VSC",
      "participation_dates": ["2024-08-14", "2024-08-15"],
      "leave_applications": [
        {
          "id": 7,
          "application_number": "LA-ZZZZZZZZ",
          "employee_id": 3,
          "leave_type_id": 10,
          "date_filed": "2024-09-01",
          "start_date": "2024-09-10",v
          "end_date": "2024-09-12",
          "total_days": 3.0,
          "reason": "Personal",
          "other_leave_description": null,
          "status": "APPROVED",
          "with_pay": 1,
          "status_updated_by": 2,
          "created_at": "2024-09-01T08:00:00",
          "leave_type_code": "VSC",
          "leave_type_name": "Vacation Service Credits",
          "username": "mreyes",
          "remarks": "Approved",
          "date_of_action": "2024-09-02T10:00:00",
          "approver_name": "Maria Santos"
        }
      ]
    }
  ]
}
```

---

### GET `/service-credit-applications/employee/<employee_id>/vsc-new-leave-summary`

Returns all VSC service credit records earned from activities with `date_of_activity >= 2024-10-01` for a teaching employee, each carrying the VSC leave applications primarily charged to it. No `valid_until` field (VSC does not expire).

Same leave assignment and routing rules as the old-period summary above. Leave applications appear in exactly one of the two summaries — never both.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": {
    "id": 3,
    "first_name": "...",
    "last_name": "...",
    "employee_number": "..."
  },
  "count": 1,
  "data": [
    {
      "credit_balance_id": 1,
      "service_credit_application_id": 5,
      "credit_application_number": "SC-YYYYYYYY",
      "original_balance": 1.5,
      "remaining_balance": 1.5,
      "special_order_number": "SO-2024-002",
      "activity_name": "Workshop",
      "date_of_activity": "2024-10-10",
      "hours_rendered": 8.0,
      "balance_earned": 1.5,
      "date_filed": "2024-10-15",
      "date_of_upload": "2024-10-16",
      "uploaded_by": 2,
      "uploaded_by_name": "Juan Dela Cruz",
      "type": "VSC",
      "participation_dates": ["2024-10-10"],
      "leave_applications": []
    }
  ]
}
```

---

### GET `/service-credit-applications/employee/<employee_id>`

Get all service credit applications for a specific employee, ordered by creation date descending.

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 2,
  "data": [ ...applications ]
}
```

---

### GET `/service-credit-applications?page=1&limit=10`

Get a paginated list of all service credit applications across all employees.

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

### GET `/service-credit-applications/special-order/<special_order_id>/search`

Search service credit applications within a specific Special Order by application number, employee number, first name, or last name. Paginated.

**Query Params**
| Param | Required | Description |
|-------|----------|-------------|
| `q` | Yes | Search keyword — matched against `application_number`, `employee_number`, `first_name`, `last_name` |
| `page` | No | Page number (default `1`) |
| `limit` | No | Records per page (default `10`) |

**Example:** `GET /service-credit-applications/special-order/1/search?q=juan&page=1&limit=10`

**Response** `200`

```json
{
  "statusCode": 200,
  "special_order": {
    "id": 1,
    "special_order": "SO-2026-001",
    "activity_name": "Regional Year-End Assessment"
  },
  "query": "juan",
  "count": 2,
  "total": 2,
  "page": 1,
  "limit": 10,
  "data": [ ...applications ]
}
```

**Missing query** `400`

```json
{
  "statusCode": 400,
  "message": "query is required"
}
```

**Special Order not found** `404`

```json
{
  "statusCode": 404,
  "message": "Special Order 1 not found"
}
```

---

### GET `/service-credit-applications/special-order/<special_order_id>?page=1&limit=10`

Get all service credit applications linked to a specific Special Order, paginated.

**Query Params**
| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number |
| `limit` | `10` | Records per page |

**Response** `200`

```json
{
  "statusCode": 200,
  "special_order": {
    "id": 1,
    "special_order": "SO-2026-001",
    "activity_name": "Regional Year-End Assessment"
  },
  "count": 3,
  "total": 3,
  "page": 1,
  "limit": 10,
  "data": [ ...applications ]
}
```

**Not found** `404`

```json
{
  "statusCode": 404,
  "message": "Special Order 1 not found"
}
```

---

### GET `/service-credit-applications/number/<application_number>`

Get a single service credit application by its unique application number. No pagination.

**Example:** `GET /service-credit-applications/number/SC-A1B2C3D4`

**Response** `200`

```json
{
  "statusCode": 200,
  "data": { ...application }
}
```

**Not found** `404`

```json
{
  "statusCode": 404,
  "message": "Service credit application 'SC-A1B2C3D4' not found"
}
```

---

### GET `/service-credit-applications/search`

Paginated search with optional filters. All filters are optional and combinable. Results ordered by `date_filed` descending.

**Query Params**
| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `special_order_id` | int | `1` | Filter by Special Order FK |
| `type` | string | `CTO` | Filter by credit type (`CTO` or `VSC`) |
| `year` | int | `2026` | Filter by calendar year of `date_filed` |
| `date_from` | string | `2026-01-01` | Lower bound of `date_filed` (YYYY-MM-DD) |
| `date_to` | string | `2026-06-30` | Upper bound of `date_filed` (YYYY-MM-DD) |
| `page` | int | `1` | Page number (default `1`) |
| `limit` | int | `10` | Records per page (default `10`) |

> `type` must be `CTO` or `VSC` if provided (returns `400` otherwise).
> `date_from` and `date_to` can be combined for a date range. Either can be used alone.
> `year` and `date_from`/`date_to` can be combined.

**Example:** `GET /service-credit-applications/search?type=CTO&year=2026&page=1&limit=10`

**Response** `200`

```json
{
  "statusCode": 200,
  "count": 3,
  "total": 7,
  "page": 1,
  "limit": 10,
  "filters": {
    "type": "CTO",
    "year": 2026
  },
  "data": [ ...applications ]
}
```

> `filters` echoes back only the filters that were actually applied (omits unset ones).

**Invalid type** `400`

```json
{
  "statusCode": 400,
  "message": "type must be CTO or VSC"
}
```

---

## Leave Types

### GET `/leave-types`

Get all active leave types.

**Response** `200`

```json
{
  "statusCode": 200,
  "data": [
    {
      "id": 1,
      "code": "VL",
      "name": "Vacation Leave",
      "balance_type": "SELF",
      "is_active": 1
    },
    {
      "id": 2,
      "code": "SL",
      "name": "Sick Leave",
      "balance_type": "SELF",
      "is_active": 1
    },
    {
      "id": 3,
      "code": "SPL",
      "name": "Special Privilege Leave",
      "balance_type": "SELF",
      "is_active": 1
    },
    {
      "id": 4,
      "code": "FL",
      "name": "Forced Leave",
      "balance_type": "CHARGED_TO_VL",
      "is_active": 1
    },
    {
      "id": 5,
      "code": "ML",
      "name": "Maternity Leave",
      "balance_type": "NONE",
      "is_active": 1
    },
    {
      "id": 6,
      "code": "PL",
      "name": "Paternity Leave",
      "balance_type": "NONE",
      "is_active": 1
    },
    {
      "id": 7,
      "code": "SLB",
      "name": "Solo Parent Leave",
      "balance_type": "NONE",
      "is_active": 1
    },
    {
      "id": 8,
      "code": "VAWC",
      "name": "VAWC Leave",
      "balance_type": "NONE",
      "is_active": 1
    },
    {
      "id": 9,
      "code": "CTO",
      "name": "Compensatory Time Off",
      "balance_type": "SELF",
      "is_active": 1
    },
    {
      "id": 10,
      "code": "VSC",
      "name": "Vacation Service Credits",
      "balance_type": "SELF",
      "is_active": 1
    },
    {
      "id": 11,
      "code": "OL",
      "name": "Others",
      "balance_type": "NONE",
      "is_active": 1
    },
    {
      "id": 12,
      "code": "WL",
      "name": "Wellness Leave",
      "balance_type": "SELF",
      "is_active": 1
    }
  ]
}
```

**`balance_type` values:**
| Value | Meaning |
|---|---|
| `SELF` | Deducted from the leave type's own balance |
| `CHARGED_TO_VL` | Deducted from both the leave type's own balance **and** VL balance |
| `NONE` | No balance required — no deduction |

---

## Error Responses

All endpoints return a consistent error format:

| Status | Meaning                                                                                |
| ------ | -------------------------------------------------------------------------------------- |
| `400`  | Bad request — missing field, invalid value, or insufficient balance                    |
| `404`  | Resource not found                                                                     |
| `409`  | Conflict — duplicate record (e.g. duplicate monthly credit, duplicate employee number) |
| `500`  | Internal server error                                                                  |

```json
{
  "statusCode": 400,
  "message": "Description of the error"
}
```
