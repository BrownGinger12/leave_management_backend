# Authentication & Role-Based Access Control

Base URL: `http://localhost:5000`

---

## Overview

All API endpoints (except `POST /auth/login`) require authentication via a **JWT Bearer token**. Access to specific endpoints is further restricted by the authenticated user's **role**.

There are three roles:

| Role | Description |
|---|---|
| `ADMIN` | Full access to all system functions |
| `DIVISION_PERSONNEL` | Access to most functions — cannot manage employees or post credits |
| `TEACHING_PERSONNEL` | Can submit and view leave applications for their own school only |

---

## Authentication Flow

### 1. Login

```
POST /auth/login
```

Send credentials, receive a JWT token valid for **8 hours**.

**Request body**

```json
{
  "username": "jdelacruz",
  "password": "your_password"
}
```

**Response `200`**

```json
{
  "statusCode": 200,
  "message": "Login successful",
  "token": "<jwt>",
  "user": {
    "id": 1,
    "employee_id": 12,
    "username": "jdelacruz",
    "role": "DIVISION_PERSONNEL",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001"
  }
}
```

### 2. Use the token

Include the token in the `Authorization` header on every subsequent request:

```
Authorization: Bearer <token>
```

### 3. Check current user

```
GET /auth/me
Authorization: Bearer <token>
```

Returns the full profile of the currently logged-in user.

---

## Error Responses

| Status | Message | Cause |
|---|---|---|
| `401` | `Authorization header missing or invalid` | No `Bearer` token in the header |
| `401` | `Token is invalid or expired` | Token tampered with, malformed, or older than 8 hours |
| `403` | `You do not have permission to perform this action` | Valid token but wrong role for the endpoint |
| `403` | `You can only access records from your own school` | TEACHING_PERSONNEL accessing a different school's records |
| `403` | `This account has been deactivated` | Account `is_active = 0` — contact admin |

---

## JWT Payload

The token embeds these claims:

| Claim | Type | Description |
|---|---|---|
| `user_id` | int | Primary key of the user account |
| `employee_id` | int | Linked employee (used for school-scoping) |
| `role` | string | `ADMIN`, `DIVISION_PERSONNEL`, or `TEACHING_PERSONNEL` |
| `username` | string | Login username |
| `exp` | int | Unix timestamp when the token expires (8 hours from login) |

---

## Roles In Detail

### ADMIN

Full unrestricted access to every endpoint. This includes:

- Creating, updating, and deleting employee records
- Uploading employee photos
- Posting manual leave credits and forwarded balances
- Posting monthly leave credits
- Creating and managing Special Orders
- Deciding (approving/rejecting) CTO applications
- Setting and managing calendar events (holidays)
- Managing user accounts (create, view)
- All read and write operations on leave applications, approvals, monetizations, VSC/CTO applications, and ledger transactions

### DIVISION_PERSONNEL

Access to operational functions. Restrictions versus ADMIN:

- **Cannot** create, update, or delete employee records
- **Cannot** upload employee photos
- **Cannot** post manual leave credits or forwarded balances
- **Cannot** post monthly leave credits
- **Cannot** create Special Orders
- **Cannot** decide (approve/reject) CTO applications
- **Cannot** create or manage calendar events (view only)
- **Cannot** access user management

Everything else is accessible: leave applications, approvals, VSC/SO applications, CTO viewing, leave monetizations, ledger transactions, special order viewing, leave balances, and more.

### TEACHING_PERSONNEL

Minimal access scoped to their own school:

- **Can** submit leave applications for employees in their school
- **Can** view leave applications for employees in their school
- **Can** view a specific employee's profile and leave balances if that employee belongs to the same school
- **Can** update their own leave application (status must be `FOR HRMO ACTION`)
- **Can** view leave types, schools, and calendar events
- **Cannot** access any other endpoints

#### School Scoping

When a `TEACHING_PERSONNEL` user accesses any employee-level endpoint, the backend checks:

1. Reads `school_id` from the current user's linked employee record
2. Reads `school_id` from the target employee being accessed
3. If they differ → `403 You can only access records from your own school`

ADMIN and DIVISION_PERSONNEL are never subject to this school check.

---

## User Account Management

All user management endpoints require an `ADMIN` token.

### Create a user account

```
POST /users
Authorization: Bearer <admin-token>
```

```json
{
  "employee_id": 12,
  "username": "jdelacruz",
  "password": "SecurePassword123",
  "role": "TEACHING_PERSONNEL"
}
```

- One account per employee — returns `409` if the employee already has an account
- Username must be unique — returns `409` if already taken
- `role` must be one of: `ADMIN`, `DIVISION_PERSONNEL`, `TEACHING_PERSONNEL`

**Response `201`**

```json
{
  "statusCode": 201,
  "message": "User account created",
  "data": {
    "id": 5,
    "employee_id": 12,
    "username": "jdelacruz",
    "role": "TEACHING_PERSONNEL",
    "is_active": 1,
    "last_login_at": null,
    "created_at": "2026-07-01T09:00:00",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "employee_number": "EMP-2024-0001"
  }
}
```

### List all users (paginated)

```
GET /users?page=1&limit=10
Authorization: Bearer <admin-token>
```

### Get user by ID

```
GET /users/<user_id>
Authorization: Bearer <admin-token>
```

---

## Full Endpoint Permission Matrix

`✅` = allowed  `❌` = not allowed  `🏫` = allowed for same school only

### Employees

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /employees` | ✅ | ❌ | ❌ |
| `GET /employees` (paginated) | ✅ | ✅ | ❌ |
| `GET /employees/my-school` | ✅ | ✅ | ✅ |
| `GET /employees/my-school/search` | ✅ | ✅ | ✅ |
| `GET /employees/<id>` | ✅ | ✅ | 🏫 |
| `GET /employees/search` | ✅ | ✅ | ❌ |
| `GET /employees/pages` | ✅ | ✅ | ❌ |
| `GET /employees/count` | ✅ | ✅ | ❌ |
| `PUT /employees/<id>` | ✅ | ❌ | ❌ |
| `DELETE /employees/<id>` | ✅ | ❌ | ❌ |
| `POST /employees/<id>/photo` | ✅ | ❌ | ❌ |
| `GET /employees/<id>/leave-balances` | ✅ | ✅ | 🏫 |

### Leave Applications

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /leave-applications` | ✅ | ✅ | 🏫 |
| `GET /leave-applications/my-school` | ✅ | ✅ | ✅ |
| `GET /leave-applications` | ✅ | ✅ | ❌ |
| `GET /leave-applications/all` | ✅ | ✅ | ❌ |
| `GET /leave-applications/cto-vsc` | ✅ | ✅ | ❌ |
| `GET /leave-applications/search` | ✅ | ✅ | ❌ |
| `GET /leave-applications/<id>` | ✅ | ✅ | 🏫 |
| `GET /leave-applications/number/<number>` | ✅ | ✅ | ❌ |
| `GET /leave-applications/employee/<id>` | ✅ | ✅ | 🏫 |
| `GET /leave-applications/employee/<id>/year/<year>` | ✅ | ✅ | 🏫 |
| `GET /leave-applications/cto-vsc/employee/<id>` | ✅ | ✅ | ❌ |
| `PUT /leave-applications/<id>` | ✅ | ✅ | ✅ |
| `DELETE /leave-applications/<id>` | ✅ | ✅ | ❌ |

### Leave Approvals

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /leave-approvals` | ✅ | ✅ | ❌ |
| `GET /leave-approvals/application/<id>` | ✅ | ✅ | ❌ |

### Leave Credits

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /leave-credits` | ✅ | ❌ | ❌ |
| `POST /leave-credits/forwarded-balance` | ✅ | ❌ | ❌ |
| `POST /monthly-leave-credits` | ✅ | ❌ | ❌ |
| `GET /monthly-leave-credits/employee/<id>/year/<year>` | ✅ | ✅ | ❌ |

### Leave Credit Transactions (Ledger)

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `GET /leave-credit-transactions/employee/<id>` | ✅ | ✅ | ❌ |
| `GET /leave-credit-transactions/employee/<id>/year/<year>` | ✅ | ✅ | ❌ |

### Leave Monetization

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /leave-monetizations` | ✅ | ✅ | ❌ |
| `GET /leave-monetizations` | ✅ | ✅ | ❌ |
| `GET /leave-monetizations/<id>` | ✅ | ✅ | ❌ |
| `GET /leave-monetizations/employee/<id>` | ✅ | ✅ | ❌ |
| `DELETE /leave-monetizations/<id>` | ✅ | ✅ | ❌ |

### Special Orders

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /special-orders` | ✅ | ❌ | ❌ |
| `GET /special-orders` | ✅ | ✅ | ❌ |
| `GET /special-orders/<id>` | ✅ | ✅ | ❌ |
| `GET /special-orders/search` | ✅ | ✅ | ❌ |
| `GET /special-orders/filter` | ✅ | ✅ | ❌ |

### CTO Applications

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /cto-applications` | ✅ | ✅ | ❌ |
| `POST /cto-applications/decide` | ✅ | ❌ | ❌ |
| `GET /cto-applications` | ✅ | ✅ | ❌ |
| `GET /cto-applications/<id>` | ✅ | ✅ | ❌ |
| `GET /cto-applications/employee/<id>` | ✅ | ✅ | ❌ |

### Service Credit Applications (VSC / CTO via SO)

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /service-credit-applications` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/<id>` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/number/<number>` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/search` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/employee/<id>` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/special-order/<id>` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/special-order/<id>/search` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/employee/<id>/vsc-old-leave-summary` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/employee/<id>/vsc-new-leave-summary` | ✅ | ✅ | ❌ |
| `GET /service-credit-applications/employee/<id>/cto-leave-summary` | ✅ | ✅ | ❌ |

### Calendar Events

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `GET /calendar-events` | ✅ | ✅ | ✅ |
| `GET /calendar-events/current-month` | ✅ | ✅ | ✅ |
| `POST /calendar-events` | ✅ | ❌ | ❌ |
| `PUT /calendar-events/<id>` | ✅ | ❌ | ❌ |
| `DELETE /calendar-events/<id>` | ✅ | ❌ | ❌ |

### Leave Types

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `GET /leave-types` | ✅ | ✅ | ✅ |
| `GET /leave-types/teaching/<employee_id>` | ✅ | ✅ | ✅ |

### Schools

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `GET /schools` | ✅ | ✅ | ✅ |

### Positions

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `GET /positions` | ✅ | ✅ | ❌ |

### Undertime / Tardiness Deductions

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /undertime-tardiness` | ✅ | ❌ | ❌ |
| `GET /undertime-tardiness` | ✅ | ✅ | ❌ |
| `GET /undertime-tardiness/search` | ✅ | ✅ | ❌ |
| `GET /undertime-tardiness/filter` | ✅ | ✅ | ❌ |
| `GET /undertime-tardiness/<id>` | ✅ | ✅ | ❌ |
| `DELETE /undertime-tardiness/<id>` | ✅ | ❌ | ❌ |

### Users _(ADMIN only)_

| Endpoint | ADMIN | DIVISION | TEACHING |
|---|---|---|---|
| `POST /users` | ✅ | ❌ | ❌ |
| `GET /users` | ✅ | ❌ | ❌ |
| `GET /users/<id>` | ✅ | ❌ | ❌ |
| `PATCH /users/<id>/role` | ✅ | ❌ | ❌ |
| `PATCH /users/<id>/deactivate` | ✅ | ❌ | ❌ |
| `PATCH /users/<id>/activate` | ✅ | ❌ | ❌ |
| `DELETE /users/<id>` | ✅ | ❌ | ❌ |
| `PATCH /users/<id>/reset-password` | ✅ | ❌ | ❌ |

### Authentication

| Endpoint | Auth required |
|---|---|
| `POST /auth/login` | ❌ No token needed |
| `GET /auth/me` | ✅ Any valid token |

---

## Implementation Notes

### Token storage (frontend)

Store the JWT in `localStorage` or `sessionStorage`. On every API call, include:

```
Authorization: Bearer <token>
```

### Token expiry

Tokens expire after **8 hours**. When the server returns `401 Token is invalid or expired`, redirect the user to the login screen and clear the stored token.

### Decorators used (backend)

| Decorator | File | Effect |
|---|---|---|
| `@require_auth` | `gateway/auth_gateway.py` | Valid JWT required; role unrestricted |
| `@require_role("ADMIN")` | `gateway/auth_gateway.py` | Valid JWT + must be ADMIN |
| `@require_role("ADMIN", "DIVISION_PERSONNEL")` | `gateway/auth_gateway.py` | Valid JWT + must be ADMIN or DIVISION |
| `check_school_access(employee_id)` | `gateway/auth_gateway.py` | Called inline for TEACHING — returns 403 if different school |
