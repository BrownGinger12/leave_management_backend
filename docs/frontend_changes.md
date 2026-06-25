# Backend Changes Summary — DepEd Leave Management System

> Use this document to update the frontend based on recent backend changes.

---

## 1. Authentication & Users (New)

- **POST `/auth/login`** — returns `access_token` (JWT). All protected routes require `Authorization: Bearer <token>` header.
- **GET `/auth/me`** — returns the currently logged-in user's details.
- **POST `/users`** _(admin only)_ — creates a system login account linked to an employee.
- **GET `/users`** _(admin only)_ — lists all user accounts.
- **GET `/users/<id>`** _(admin only)_ — get a single user account.

---

## 2. Employee Model — New Fields

The employee object now includes these additional fields:

| Field                  | Type    | Notes                           |
| ---------------------- | ------- | ------------------------------- |
| `division`             | string  | Replaces old `department` field |
| `original_appointment` | date    | YYYY-MM-DD                      |
| `latest_appointment`   | date    | YYYY-MM-DD                      |
| `position`             | string  | Job title                       |
| `salary`               | decimal | Monthly salary                  |
| `contact_number`       | string  |                                 |
| `is_active`            | boolean | Soft-delete flag                |

**Breaking change:** `department` is gone, replaced by `division`.

New employee endpoints:

- **POST `/employees/<id>/photo`** — upload employee photo (multipart/form-data).
- **GET `/employees/<id>/photo`** — get a signed (expiring) photo URL.
- **GET `/employees/<id>/leave-balances`** — get all current leave balances for an employee.

---

## 3. Leave Types — Wellness Leave Added

A new leave type is now available:

| code | name           | balance_type |
| ---- | -------------- | ------------ |
| `WL` | Wellness Leave | SELF         |

Include `WL` wherever leave types are listed or selected.

---

## 4. Leave Credits — Restriction Removed

**`POST /leave-credits`** now accepts **any active leave type**, not just VL and SL. The frontend can allow crediting CTO, VSC, SPL, WL, etc. through this endpoint.

---

## 5. Monthly Leave Credits (New Feature)

Tracks monthly VL/SL accrual with idempotency — prevents double-crediting the same employee for the same leave type in the same month.

- **POST `/monthly-leave-credits`** — credit VL or SL for a specific month/year.

  Request body:

  ```json
  {
    "employee_id": 1,
    "leave_type_id": 1,
    "year": 2026,
    "month": 6,
    "amount": 1.25,
    "transaction_date": "2026-06-30",
    "remarks": "June 2026 monthly credit"
  }
  ```

  Returns `409 Conflict` if already credited for that month.

- **GET `/monthly-leave-credits/employee/<id>/year/<year>`** — get all monthly credits for an employee in a year, each with embedded ledger data.

---

## 6. Leave Applications — Year Filter

- **GET `/leave-applications/employee/<id>/year/<year>`** — returns all leave applications for an employee in a given year. Each application includes a `ledger` array with all associated ledger entries (debits posted on approval).

---

## 7. Leave Credit Transactions — Year Filter

- **GET `/leave-credit-transactions/employee/<id>/year/<year>`** — returns all ledger entries for an employee in a given year.

---

## 8. FL (Forced Leave) — Dual Debit on Approval

When a Forced Leave application is approved, the system now posts **two separate DEBIT entries**:

1. Deduction from the **FL** balance
2. Deduction from the **VL** balance

The ledger view should expect two ledger rows per FL approval — one per leave type.

---

## 9. Leave Application Status Values — Updated

Leave application statuses have changed. Update all status labels, filters, and badge colors.

| Old | New |
|---|---|
| `PENDING` | `FOR HRMO ACTION` |
| *(none)* | `FOR APPROVAL` |
| `REJECTED` | `RETURNED` or `DISAPPROVED` |
| `APPROVED` | `APPROVED` |
| `CANCELLED` | *(removed)* |

`POST /leave-approvals` — `status` field in request body now accepts:

- `FOR APPROVAL` — passes to the next approval level
- `APPROVED` — final approval
- `RETURNED` — returned to employee (balance is restored automatically)
- `DISAPPROVED` — final rejection (balance is restored automatically)

---

## 10. Balance Deducted on Submission (Breaking Change)

Balance is now deducted **immediately when a leave application is submitted**, not on approval.

- On submit → status `FOR HRMO ACTION`, balance deducted
- On `APPROVED` → status updated only, no balance change
- On `RETURNED` or `DISAPPROVED` → status updated + balance **restored** (credit reversal in ledger)

The ledger will show a DEBIT on every submission and a matching CREDIT reversal on every return/disapproval. Display deducted balance as soon as a leave is submitted.

---

## 11. Leave Ledger Balance — Cascading Recalculation

`balance_snapshot_after` is always recomputed in chronological order (`start_date` of the leave) like an Excel running total whenever any entry is posted or reversed.

- Safe to display `balance_snapshot_after` as the running balance per row, sorted by `transaction_date ASC`.
- Monthly credits are dated at end of month; leave DEBITs are dated at `start_date` — so debits always appear after the credits that precede them.

---

## 12. CTO Applications → Service Credit Applications (Renamed)

The CTO applications feature has been renamed and expanded to handle both CTO and VSC credits.

- **Removed:** `/cto-applications`
- **New:** `/service-credit-applications` — handles both `CTO` and `VSC` types via a `type` field.

All frontend references to CTO applications must be updated to use the new endpoint and include the `type` field (`"CTO"` or `"VSC"`).

---

## Endpoint Change Reference

| Change        | Old                 | New                                                    |
| ------------- | ------------------- | ------------------------------------------------------ |
| Renamed       | `/cto-applications` | `/service-credit-applications`                         |
| New           | —                   | `/auth/login`, `/auth/me`                              |
| New           | —                   | `/users`                                               |
| New           | —                   | `/monthly-leave-credits`                               |
| New           | —                   | `/employees/<id>/photo`                                |
| New           | —                   | `/employees/<id>/leave-balances`                       |
| New filter    | —                   | `/leave-applications/employee/<id>/year/<year>`        |
| New filter    | —                   | `/leave-credit-transactions/employee/<id>/year/<year>` |
| Field renamed | `department`        | `division` (on employees)                              |
