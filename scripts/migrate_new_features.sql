-- ============================================================
-- Migration: new features
--   1. Application number sequences table (YY-NNNNNN format)
--   2. implementing_unit column on employees
--   3. school_type column on schools
--   4. ANNUAL_CREDIT source_type on leave_credit_transactions
-- Run once against an existing database.
-- ============================================================

USE leave_management;

-- 1. Sequence counter table for application number generation
CREATE TABLE IF NOT EXISTS application_number_sequences (
    year      INT         NOT NULL,              -- calendar year (e.g. 2026)
    seq_type  VARCHAR(20) NOT NULL,              -- 'LEAVE' or 'CTO'
    last_seq  INT         NOT NULL DEFAULT 0,    -- last issued sequence number for this year/type
    PRIMARY KEY (year, seq_type)                  -- one row per year per type
);

-- 2. Implementing Unit field on employees — FK to schools.id (nullable)
ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS implementing_unit INT NULL
    AFTER school_id;

ALTER TABLE employees
    ADD CONSTRAINT IF NOT EXISTS fk_emp_implementing_unit
    FOREIGN KEY (implementing_unit) REFERENCES schools (id)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- 2b. Sex field on employees (nullable — MALE or FEMALE)
ALTER TABLE employees
    ADD COLUMN IF NOT EXISTS sex ENUM('MALE', 'FEMALE') NULL
    AFTER middle_name;

-- 3. School type classification (REGULAR / IU / SHS)
ALTER TABLE schools
    ADD COLUMN IF NOT EXISTS school_type ENUM('REGULAR', 'IU', 'SHS') NOT NULL DEFAULT 'REGULAR'
    AFTER name;

-- 4. Expand source_type ENUM to include ANNUAL_CREDIT and MANUAL_DEDUCTION
ALTER TABLE leave_credit_transactions
    MODIFY COLUMN source_type ENUM(
        'SPECIAL_ORDER',
        'LEAVE_APPLICATION',
        'MANUAL_ADJUSTMENT',
        'SYSTEM_ADJUSTMENT',
        'FORWARDED_BALANCE',
        'HOLIDAY_REFUND',
        'TYPE_CONVERSION',
        'ANNUAL_CREDIT',
        'MANUAL_DEDUCTION',
        'MONETIZATION',
        'UNDERTIME_TARDINESS',
        'MONTHLY_CREDIT'
    ) NOT NULL;

-- 5b. submitted_by (user who filed the application) on leave_applications
ALTER TABLE leave_applications
    ADD COLUMN IF NOT EXISTS submitted_by INT NULL
    AFTER status;

ALTER TABLE leave_applications
    ADD CONSTRAINT IF NOT EXISTS fk_app_submitted_by
    FOREIGN KEY (submitted_by) REFERENCES users (id)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- 7. Add reason column to leave_approvals and remarks column to leave_applications
ALTER TABLE leave_approvals
    ADD COLUMN IF NOT EXISTS reason TEXT NULL AFTER remarks;

ALTER TABLE leave_applications
    ADD COLUMN IF NOT EXISTS remarks TEXT NULL AFTER reason;

-- (original note below)

-- 6. Rename hours_rendered → days_rendered on service_credit_applications (1:1 credit, no 1.5x multiplier)
ALTER TABLE service_credit_applications
    CHANGE COLUMN hours_rendered days_rendered DECIMAL(10, 4) NOT NULL;

-- 5a. Add remarks column to VSC balance tables (used by forwarded balance entries)
ALTER TABLE vsc_old_credit_balances
    ADD COLUMN IF NOT EXISTS remarks TEXT NULL
    AFTER remaining_balance;

ALTER TABLE vsc_new_credit_balances
    ADD COLUMN IF NOT EXISTS remarks TEXT NULL
    AFTER remaining_balance;

-- 5. Manual balance deductions history table
CREATE TABLE IF NOT EXISTS manual_balance_deductions (
    id               INT                     NOT NULL AUTO_INCREMENT,
    deduction_number VARCHAR(20)             NOT NULL,                 -- unique reference number (YY-NNNNNN)
    employee_id      INT                     NOT NULL,                 -- FK to employees (NON_TEACHING only)
    leave_type_id    INT                     NOT NULL,                 -- FK to leave_types (VL or SL only)
    transaction_type ENUM('DEBIT','CREDIT')  NOT NULL DEFAULT 'DEBIT', -- DEBIT = deduction, CREDIT = crediting
    amount           DECIMAL(10, 4)          NOT NULL,                 -- days adjusted
    deduction_date   DATE                    NOT NULL,                 -- effective date of the adjustment
    remarks          TEXT                    NULL,                     -- optional notes from admin
    is_deleted       TINYINT(1)              NOT NULL DEFAULT 0,       -- soft delete flag
    created_at       TIMESTAMP               NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_deduction_number (deduction_number),
    CONSTRAINT fk_mbd_employee   FOREIGN KEY (employee_id)  REFERENCES employees  (id),
    CONSTRAINT fk_mbd_leave_type FOREIGN KEY (leave_type_id) REFERENCES leave_types (id)
);
