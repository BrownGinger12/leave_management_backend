# Deped Leave Management System

## Stack

- Python Flask and MySQL

## Architecture

Use **HMG (Handler, Model, Gateway)** architecture:

- **Handler** — request entry point that receives and returns the API event
- **Model** — defines payload structure and attributes using Pydantic
- **Gateway** — initializes the service/resource(MYSQL etc.) and contains# DepEd Leave Management System

## Stack

- Python Flask (API Layer)
- MySQL (Database)
- Optional: AWS (SES, Lambda later if needed)

---

## Architecture (HMG Pattern)

Use **HMG (Handler, Model, Gateway)** architecture:

### Handler

- Entry point of the API
- Receives HTTP requests
- Calls services/gateways
- Returns responses only

### Model

- Defines request/response structure
- Uses Pydantic for validation
- Ensures data consistency before processing

### Gateway

- Handles database interactions (MySQL)
- Initializes external services (future AWS integration)
- Contains ONLY explicitly defined functions (no hidden logic)

---

## Code Style Rules

- Add a **docstring to every function**
  - Purpose
  - Parameters
  - Return value

- Add **inline comments per line**
  - Brief explanation of what each line does

---

## System Overview (Functional Summary)

The system manages **DepEd employee leave processing** including:

### 1. Employee Management

- Stores employee profile
- Tracks employee type (TEACHING / NON_TEACHING)
- Assigns unique leave card number
- Links employees to leave balances

---

### 2. Leave Application

- Employees submit leave requests
- Includes:
  - Leave type (VL, SL, FL, CTO, VSC, etc.)
  - Start and end dates
  - Date filed
  - Reason and special notes (e.g., “Others”)

- System calculates:
  - Total leave days
  - Required balance deduction (if applicable)

- Routes request through approval workflow

---

### 3. Approval Workflow

- Each approval step is tracked separately
- Final approval triggers ledger posting and balance updates

---

### 4. Leave Balance System

- Tracks per-employee leave balances per leave type
- Supports:
  - Vacation Leave (VL)
  - Sick Leave (SL)
  - Special Privilege Leave (SPL)
  - CTO (Compensatory Time Off)
  - VSC (Vacation Service Credits)

- Supports different rules:
  - SELF (own balance)
  - CHARGED_TO_VL (deduct from VL)
  - NONE (no balance required)

---

### 5. Ledger System (Core Engine)

- Stores all leave credits and debits
- Acts as **source of truth**
- Enables full audit trail

Includes:

- CTO credits (via Special Order)
- VSC credits
- Leave deductions (approved applications)
- Manual/system adjustments

Each transaction includes:

- Source reference (application or special order)
- Balance snapshot after transaction

---

## Current Database Structure

### 1. employees

Stores employee profile and classification.

Key fields:

- id (PK)
- leave_card_number
- employee_number
- employee_type (TEACHING / NON_TEACHING)
- email, name fields
- employment_status
- school_id

---

### 2. leave_types

Defines all leave categories.

Key fields:

- id (PK)
- code (VL, SL, CTO, VSC, etc.)
- name
- balance_type:
  - SELF
  - CHARGED_TO_VL
  - NONE
- is_active

---

### 3. leave_applications

Stores leave requests.

Key fields:

- id (PK)
- application_number
- employee_id (FK)
- leave_type_id (FK)
- date_filed
- start_date / end_date
- total_days
- reason
- status (PENDING / APPROVED / REJECTED / CANCELLED)
- other_leave_description

---

### 4. leave_approvals

Tracks multi-level approval workflow.

Key fields:

- id (PK)
- leave_application_id (FK)
- approver_id (FK)
- level (1, 2, 3...)
- status
- remarks
- approved_at

---

### 5. employee_leave_balances

Stores cached current balances per employee.

Key fields:

- id (PK)
- employee_id (FK)
- leave_type_id (FK)
- balance
- UNIQUE(employee_id, leave_type_id)

---

### 6. leave_credit_transactions (LEDGER)

Source of truth for all leave movements.

Key fields:

- id (PK)
- transaction_number
- employee_id (FK)
- leave_type_id (FK)
- transaction_type (CREDIT / DEBIT)
- amount
- source_type:
  - SPECIAL_ORDER
  - LEAVE_APPLICATION
  - MANUAL_ADJUSTMENT
  - SYSTEM_ADJUSTMENT
- source_id (reference to origin record)
- transaction_date
- balance_snapshot_after

---

## Core Business Flow

### Leave Application Flow

1. Employee submits leave application
2. System validates leave type rules
3. Approval workflow starts
4. Once approved:
   - Ledger DEBIT is created (if required)
   - Balance is updated

---

### CTO / VSC Credit Flow

1. Special Order is created
2. System converts SO into credit transaction
3. Ledger CREDIT is inserted
4. Balance is updated automatically

---

## Key Design Principles

- Ledger is the **single source of truth**
- Balance table is only a **cache**
- All changes must go through **transaction service**
- Every transaction must be traceable via `source_type + source_id`
- Approval does NOT directly modify balances

---

## Next Suggested Improvements

- Idempotency protection for API requests
- Leave computation engine (business rules per leave type)
- Redis caching for balance reads
- Audit dashboard for HR
- Leave expiration handling (CTO, SPL rules)

--- only explicitly mentioned functions; do not add unlisted functions

## Code Style

- Add a docstring to every function documenting what it does and its parameters
- Add an inline comment on each line briefly explaining what it does
