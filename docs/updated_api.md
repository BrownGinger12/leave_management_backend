# API Updates — Leave Applications

These are the recent changes to the Leave Applications module.

---

## What Changed

1. **POST `/leave-applications`** — body now uses a `dates[]` array instead of `start_date` / `end_date` / `total_days`
2. **GET responses** — all leave application responses now include a `leave_dates` array; `start_date`, `end_date`, and `total_days` are derived fields
3. **PUT `/leave-applications/<id>`** — new endpoint to replace leave dates (only when `FOR HRMO ACTION`)
4. **DELETE `/leave-applications/<id>`** — new endpoint for soft-delete with balance reversal
5. **GET `/leave-applications/employee/<id>/year/<year>`** — response now includes `deduction` and `balance_after` per application (running balance); raw `ledger` array removed

---

## Leave Date Structure

Dates are stored individually in `leave_application_dates`. `start_date`, `end_date`, and `total_days` on the response are **derived**, not stored on the header.

| `duration_type` | `half_day_period` | Days counted |
| --------------- | ----------------- | ------------ |
| `FULL_DAY`      | `null`            | 1.0          |
| `HALF_DAY`      | `AM`              | 0.5          |
| `HALF_DAY`      | `PM`              | 0.5          |

---

## POST `/leave-applications`

**Changed:** body now uses `dates[]` instead of `start_date` / `end_date`.

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

| Field                     | Type   | Required    | Description                             |
| ------------------------- | ------ | ----------- | --------------------------------------- |
| `dates`                   | array  | Yes         | At least one entry required             |
| `dates[].leave_date`      | string | Yes         | YYYY-MM-DD                              |
| `dates[].duration_type`   | string | Yes         | `FULL_DAY` or `HALF_DAY`                |
| `dates[].half_day_period` | string | Conditional | `AM` or `PM` — required when `HALF_DAY` |
| `dates[].is_paid`         | bool   | No          | Defaults to `true`                      |

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "Leave application submitted successfully",
  "data": {
    "id": 1,
    "application_number": "LA-A1B2C3D4",
    "status": "FOR HRMO ACTION",
    "start_date": "2026-07-21",
    "end_date": "2026-07-23",
    "total_days": 2.0,
    "leave_dates": [
      {
        "id": 1,
        "leave_date": "2026-07-21",
        "duration_type": "FULL_DAY",
        "half_day_period": null,
        "is_paid": 1
      },
      {
        "id": 2,
        "leave_date": "2026-07-22",
        "duration_type": "HALF_DAY",
        "half_day_period": "AM",
        "is_paid": 1
      },
      {
        "id": 3,
        "leave_date": "2026-07-23",
        "duration_type": "HALF_DAY",
        "half_day_period": "PM",
        "is_paid": 0
      }
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
    "Leave cannot be applied on 2026-12-25 because it is a full-day holiday (Christmas Day)."
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

---

## PUT `/leave-applications/<id>`

**New endpoint.** Replaces all leave dates on an existing application. Only allowed when status is `FOR HRMO ACTION`. Old balance debit is reversed and a new debit is posted. Holidays, overlaps, and balance are re-validated before any writes.

**Body**

```json
{
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
    }
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
      {
        "leave_date": "2026-07-21",
        "duration_type": "FULL_DAY",
        "half_day_period": null,
        "is_paid": 1
      },
      {
        "leave_date": "2026-07-22",
        "duration_type": "HALF_DAY",
        "half_day_period": "AM",
        "is_paid": 1
      }
    ]
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

---

## DELETE `/leave-applications/<id>`

**New endpoint.** Soft-deletes a leave application. Record stays in the database (`is_deleted = 1`) with `deleted_at` and `deleted_by` set. Excluded from all GET queries and overlap checks.

**Balance reversal rules:**

| Status at deletion | Balance action                             |
| ------------------ | ------------------------------------------ |
| `FOR HRMO ACTION`  | Reversed                                   |
| `FOR APPROVAL`     | Reversed                                   |
| `APPROVED`         | Reversed                                   |
| `RETURNED`         | No reversal (already restored by approval) |
| `DISAPPROVED`      | No reversal (already restored by approval) |

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

## GET `/leave-applications/employee/<id>/year/<year>`

**Changed:** raw `ledger` array removed. Each application now includes `deduction` and `balance_after` computed as a running total, ordered chronologically (ASC).

**Running balance rules:**

| Application status                            | `deduction`   | Effect on `balance_after`                       |
| --------------------------------------------- | ------------- | ----------------------------------------------- |
| `FOR HRMO ACTION`, `FOR APPROVAL`, `APPROVED` | `-total_days` | Balance decreases                               |
| `RETURNED`, `DISAPPROVED`                     | `0`           | Balance unchanged — correction cascades forward |
| Leave type is `NONE`                          | `-total_days` | `balance_after` is `null` (no balance tracked)  |

Every application now includes `vl_balance_after` and `sl_balance_after` regardless of leave type — these are the running VL and SL balances **at that exact point in the leave card**. Monthly credits are interleaved by transaction date so the balances reflect only what was available at that time.

For `FL` (Forced Leave, `CHARGED_TO_VL`), `balance_after` tracks the **VL balance** since FL deductions come from VL. `vl_balance_after` will show the same value.

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
      "application_number": "LA-A1B2C3D4",
      "leave_type_code": "VL",
      "status": "DISAPPROVED",
      "date_filed": "2026-07-01",
      "start_date": "2026-07-21",
      "end_date": "2026-07-22",
      "total_days": 2.0,
      "deduction": 0.0,
      "balance_after": 100.0,
      "vl_balance_after": 100.0,
      "sl_balance_after": 101.25,
      "leave_dates": ["..."]
    },
    {
      "id": 2,
      "application_number": "LA-B2C3D4E5",
      "leave_type_code": "SL",
      "status": "FOR HRMO ACTION",
      "date_filed": "2026-07-05",
      "start_date": "2026-07-28",
      "end_date": "2026-07-28",
      "total_days": 1.0,
      "deduction": -1.0,
      "balance_after": 99.0,
      "vl_balance_after": 100.0,
      "sl_balance_after": 99.0,
      "leave_dates": ["..."]
    }
  ]
}
```

---

## Leave Monetizations

Monetization converts unused VL and/or SL days into monetary value. Records are stored in `leave_applications` with `leave_type = MNT` — not a separate table. The `application_number` uses the `MN-XXXXXXXX` format. VL and SL deductions are posted immediately as separate DEBIT ledger entries on submission.

---

## POST `/leave-monetizations`

Requires `Authorization` header.

**Body**

```json
{
  "employee_id": 1,
  "vl_days": 10,
  "sl_days": 5,
  "date_filed": "2026-06-30",
  "remarks": "Terminal leave monetization"
}
```

| Field         | Type   | Required    | Description                                  |
| ------------- | ------ | ----------- | -------------------------------------------- |
| `employee_id` | int    | Yes         | FK to employees                              |
| `date_filed`  | string | Yes         | YYYY-MM-DD                                   |
| `vl_days`     | float  | Conditional | VL days to deduct — at least one must be > 0 |
| `sl_days`     | float  | Conditional | SL days to deduct — at least one must be > 0 |
| `remarks`     | string | No          | Stored in the `reason` field on the record   |

**Response** `201`

```json
{
  "statusCode": 201,
  "message": "Leave monetization submitted successfully",
  "data": {
    "id": 5,
    "application_number": "MN-A1B2C3D4",
    "leave_type_code": "MNT",
    "leave_type_name": "Monetization",
    "employee_id": 1,
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001",
    "date_filed": "2026-06-30",
    "reason": "Terminal leave monetization",
    "mnt_vl_days": 10.0,
    "mnt_sl_days": 5.0,
    "status": "FOR HRMO ACTION",
    "start_date": null,
    "end_date": null,
    "leave_dates": []
  }
}
```

> **Field name mapping** — the request uses `vl_days`/`sl_days`/`remarks`; the response returns `mnt_vl_days`/`mnt_sl_days`/`reason`.

**Insufficient balance** `400`

```json
{
  "statusCode": 400,
  "message": "Insufficient VL balance. Available: 8.0, Requested: 10.0"
}
```

---

## GET `/leave-monetizations`

Returns a paginated list of all monetizations across all employees.

**Query params**

| Param   | Default | Description         |
| ------- | ------- | ------------------- |
| `page`  | `1`     | Page number         |
| `limit` | `10`    | Records per page    |

**Response** `200`

```json
{
  "statusCode": 200,
  "page": 1,
  "limit": 10,
  "total": 1,
  "pages": 1,
  "data": [{ "...": "same shape as submit response data" }]
}
```

---

## GET `/leave-monetizations/<id>`

Returns a single monetization record by its `leave_applications.id`.

**Response** `200` — same shape as submit response `data`.

**Not found** `404`

```json
{ "statusCode": 404, "message": "Leave monetization not found" }
```

---

## GET `/leave-monetizations/employee/<employee_id>`

Returns all monetizations for a specific employee.

**Response** `200`

```json
{
  "statusCode": 200,
  "employee": { "id": 1, "first_name": "Juan", "last_name": "Dela Cruz", "employee_number": "EMP-2024-0001" },
  "count": 1,
  "data": [{ "...": "same shape as submit response data" }]
}
```

---

## DELETE `/leave-monetizations/<id>`

Requires `Authorization` header. Soft-deletes the `leave_applications` record and reverses VL/SL balance deductions unless the status is already `RETURNED` or `DISAPPROVED`.

**Response** `200`

```json
{ "statusCode": 200, "message": "Leave monetization deleted successfully" }
```

---

## MNT rows in the running balance (`GET /leave-applications/employee/<id>/year/<year>`)

Monetization records appear in this endpoint alongside regular leave applications. MNT-specific behavior:

| Field             | Value                                              |
| ----------------- | -------------------------------------------------- |
| `leave_type_code` | `MNT`                                              |
| `start_date`      | `null`                                             |
| `end_date`        | `null`                                             |
| `leave_dates`     | `[]`                                               |
| `mnt_vl_days`     | VL days deducted                                   |
| `mnt_sl_days`     | SL days deducted                                   |
| `deduction`       | `-(mnt_vl_days + mnt_sl_days)` or `0` if reversed |
| `balance_after`   | `null` (no single balance column for MNT)          |
| `vl_balance_after`| VL balance after this row's deduction              |
| `sl_balance_after`| SL balance after this row's deduction              |

The frontend should fall back to `date_filed` when `start_date` is `null`, and render `mnt_vl_days` + `mnt_sl_days` as a breakdown instead of a single `total_days` figure.

---

## GET `/leave-types/teaching/<employee_id>`

**New endpoint.** Returns all leave types available for teaching staff for a specific employee. Excludes `SL` (Sick Leave) and `PR` (Personal Reason) — both are funded through VSC credits and are handled through separate balance rules.

**URL params**

| Param         | Type | Description                |
| ------------- | ---- | -------------------------- |
| `employee_id` | int  | The employee's primary key |

**Response** `200`

```json
{
  "statusCode": 200,
  "employee_id": 1,
  "count": 11,
  "data": [
    { "id": 9,  "code": "CTO",  "name": "Compensatory Time Off",   "balance_type": "SELF",           "is_active": 1 },
    { "id": 4,  "code": "FL",   "name": "Forced Leave",            "balance_type": "CHARGED_TO_VL",  "is_active": 1 },
    { "id": 5,  "code": "ML",   "name": "Maternity Leave",         "balance_type": "NONE",           "is_active": 1 },
    { "id": 11, "code": "OL",   "name": "Others",                  "balance_type": "NONE",           "is_active": 1 },
    { "id": 6,  "code": "PL",   "name": "Paternity Leave",         "balance_type": "NONE",           "is_active": 1 },
    { "id": 7,  "code": "SLB",  "name": "Solo Parent Leave",       "balance_type": "NONE",           "is_active": 1 },
    { "id": 3,  "code": "SPL",  "name": "Special Privilege Leave", "balance_type": "SELF",           "is_active": 1 },
    { "id": 10, "code": "VSC",  "name": "Vacation Service Credits","balance_type": "SELF",           "is_active": 1 },
    { "id": 8,  "code": "VAWC", "name": "VAWC Leave",              "balance_type": "NONE",           "is_active": 1 },
    { "id": 1,  "code": "VL",   "name": "Vacation Leave",          "balance_type": "SELF",           "is_active": 1 },
    { "id": 12, "code": "WL",   "name": "Wellness Leave",          "balance_type": "SELF",           "is_active": 1 }
  ]
}
```

**Employee not found** `404`

```json
{ "statusCode": 404, "message": "Employee not found" }
```

---

## Database Changes

Three new columns added to `leave_applications`:

```sql
is_deleted  TINYINT(1) NOT NULL DEFAULT 0,  -- 1 = soft-deleted
deleted_at  DATETIME DEFAULT NULL,            -- timestamp of deletion
deleted_by  INT DEFAULT NULL                  -- FK to users.id
```

New table `leave_refunded_dates` — one row per credit posted when a holiday refund fires:

```sql
CREATE TABLE leave_refunded_dates (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    leave_application_id    INT NOT NULL,       -- FK → leave_applications.id
    calendar_event_id       INT NOT NULL,       -- FK → calendar_events.id (the holiday)
    holiday_date            DATE NOT NULL,      -- the holiday date that was refunded
    amount_refunded         DECIMAL(8,2),       -- days credited back
    credited_leave_type_id  INT NOT NULL,       -- FK → leave_types.id (type that received the credit)
    refunded_at             TIMESTAMP           -- when the refund was recorded
);
```

> FL (`CHARGED_TO_VL`) produces two rows per application per holiday — one for FL and one for VL, since both balances are credited.
