# Undertime & Tardiness Deductions

Base URL: `http://localhost:5000`

All requests require:
```
Authorization: Bearer <token>
```

> Only applicable to **NON_TEACHING** employees.  
> Deducts from **Vacation Leave (VL)** balance.  
> ADMIN can write. ADMIN and DIVISION_PERSONNEL can read.

---

## Create Deduction

```
POST /undertime-tardiness
```

**Body**

```json
{
  "employee_id": 5,
  "undertime_points": 0.5,
  "tardiness_points": 0.25,
  "deduction_date": "2026-03-31",
  "remarks": "March 2026"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `employee_id` | int | ✅ | Must be a NON_TEACHING employee |
| `undertime_points` | decimal | ✅ | Days accumulated from undertime |
| `tardiness_points` | decimal | ✅ | Days accumulated from tardiness |
| `deduction_date` | string | ✅ | YYYY-MM-DD |
| `remarks` | string | ❌ | Optional notes |

`total = undertime_points + tardiness_points` — this is the amount deducted from VL.

**Response `201`**

```json
{
  "statusCode": 201,
  "message": "Undertime/tardiness deduction created and VL balance updated",
  "data": {
    "id": 1,
    "application_number": "UTD-A1B2C3D4",
    "employee_id": 5,
    "first_name": "Pedro",
    "last_name": "Reyes",
    "employee_number": "EMP-2024-0005",
    "undertime_points": 0.5,
    "tardiness_points": 0.25,
    "total_points": 0.75,
    "vl_deducted": 0.75,
    "deduction_date": "2026-03-31",
    "remarks": "March 2026",
    "is_deleted": 0,
    "created_at": "2026-07-02T10:00:00"
  }
}
```

**Error responses**

| Status | Message |
|---|---|
| `400` | `employee_id is required` |
| `400` | `undertime_points and tardiness_points must be non-negative` |
| `400` | `Undertime/tardiness deductions are only applicable to NON_TEACHING employees` |
| `404` | `Employee not found or inactive` |

---

## Get All (Paginated)

```
GET /undertime-tardiness?page=1&limit=10
```

**Response `200`**

```json
{
  "statusCode": 200,
  "count": 10,
  "total": 42,
  "page": 1,
  "limit": 10,
  "data": [ ...deductions ]
}
```

---

## Get by ID

```
GET /undertime-tardiness/<id>
```

**Response `200`**

```json
{
  "statusCode": 200,
  "data": { ...deduction }
}
```

---

## Search

Search by application number, employee first name, last name, or employee number.

```
GET /undertime-tardiness/search?query=UTD-A1B2&page=1&limit=10
```

| Param | Required | Description |
|---|---|---|
| `query` | ✅ | Keyword to search |
| `page` | ❌ | Default `1` |
| `limit` | ❌ | Default `10` |

**Response `200`** — same shape as paginated list.

**Response `404`** — no matching records found.

---

## Filter

```
GET /undertime-tardiness/filter?year=2026&date_from=2026-01-01&date_to=2026-06-30&employee_id=5
```

| Param | Type | Description |
|---|---|---|
| `year` | int | Calendar year of `deduction_date` |
| `date_from` | string | Lower bound (YYYY-MM-DD) |
| `date_to` | string | Upper bound (YYYY-MM-DD) |
| `employee_id` | int | Filter by specific employee |
| `page` | int | Default `1` |
| `limit` | int | Default `10` |

All params are optional and combinable.

**Response `200`**

```json
{
  "statusCode": 200,
  "count": 3,
  "total": 3,
  "page": 1,
  "limit": 10,
  "filters": { "year": 2026, "employee_id": 5 },
  "data": [ ...deductions ]
}
```

---

## Delete (Soft Delete)

Marks the record as deleted and **reverses the VL deduction** — the balance is restored.  
ADMIN only.

```
DELETE /undertime-tardiness/<id>
```

**Response `200`**

```json
{
  "statusCode": 200,
  "message": "Deduction deleted and VL balance restored"
}
```

**Response `404`** — record not found.  
**Response `409`** — already deleted.

---

## Running Balance

Deductions appear automatically in the leave card when calling:

```
GET /leave-applications/employee/<id>/year/<year>
```

The response includes an `undertime_tardiness_deductions` array. Each item shows the VL balance **after** the deduction, computed in the same timeline as leave applications.

```json
{
  "undertime_tardiness_deductions": [
    {
      "id": 1,
      "application_number": "UTD-A1B2C3D4",
      "undertime_points": 0.5,
      "tardiness_points": 0.25,
      "total_points": 0.75,
      "vl_deducted": 0.75,
      "deduction_date": "2026-03-31",
      "remarks": "March 2026",
      "balance_after": 14.25
    }
  ]
}
```

`balance_after` is the VL balance immediately after this deduction was applied.
