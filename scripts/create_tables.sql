-- ============================================================
-- DepEd Leave Management System — Table Creation Script
-- Database: leave_management
-- ============================================================

CREATE DATABASE IF NOT EXISTS leave_management;
USE leave_management;

-- ============================================================
-- 1. employees
--    Stores employee profile and classification.
-- ============================================================

CREATE TABLE IF NOT EXISTS employees (
    id                  INT AUTO_INCREMENT PRIMARY KEY,                          -- unique row identifier
    leave_card_number   VARCHAR(20)  NOT NULL UNIQUE,                            -- system-generated leave card number (e.g. LC-A1B2C3D4)
    employee_number     VARCHAR(50)  NOT NULL UNIQUE,                            -- DepEd-assigned employee number
    first_name          VARCHAR(100) NOT NULL,                                   -- employee first name
    last_name           VARCHAR(100) NOT NULL,                                   -- employee last name
    middle_name         VARCHAR(100) DEFAULT NULL,                               -- employee middle name, optional
    email               VARCHAR(150) NOT NULL UNIQUE,                            -- employee email address
    employee_type       ENUM('TEACHING', 'NON_TEACHING') NOT NULL,              -- classification of the employee
    employment_status   ENUM('PERMANENT', 'TEMPORARY', 'CASUAL', 'CONTRACT_OF_SERVICE') NOT NULL,  -- employment status
    school_id           INT NOT NULL,                                            -- ID of the school or office the employee belongs to
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,                      -- record creation timestamp
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- record last update timestamp
);

-- ============================================================
-- 2. leave_types
--    Defines all leave categories available in the system.
-- ============================================================

CREATE TABLE IF NOT EXISTS leave_types (
    id              INT AUTO_INCREMENT PRIMARY KEY,                              -- unique row identifier
    code            VARCHAR(10)  NOT NULL UNIQUE,                               -- short leave code (e.g. VL, SL, CTO)
    name            VARCHAR(100) NOT NULL,                                      -- full descriptive name of the leave type
    balance_type    ENUM('SELF', 'CHARGED_TO_VL', 'NONE') NOT NULL,            -- how the balance is sourced: own, deducted from VL, or not required
    is_active       TINYINT(1) NOT NULL DEFAULT 1,                              -- 1 = active and available for application, 0 = disabled
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,                         -- record creation timestamp
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- record last update timestamp
);

-- ============================================================
-- 3. leave_applications
--    Stores all employee leave requests.
-- ============================================================

CREATE TABLE IF NOT EXISTS leave_applications (
    id                      INT AUTO_INCREMENT PRIMARY KEY,                     -- unique row identifier
    application_number      VARCHAR(20)  NOT NULL UNIQUE,                       -- system-generated application number (e.g. LA-A1B2C3D4)
    employee_id             INT NOT NULL,                                       -- FK to employees.id
    leave_type_id           INT NOT NULL,                                       -- FK to leave_types.id
    date_filed              DATE NOT NULL,                                      -- date the application was submitted
    start_date              DATE NOT NULL,                                      -- first day of the leave
    end_date                DATE NOT NULL,                                      -- last day of the leave
    total_days              DECIMAL(5, 2) NOT NULL,                             -- computed number of leave days (supports half-days)
    reason                  TEXT NOT NULL,                                      -- reason stated by the employee for the leave
    other_leave_description VARCHAR(255) DEFAULT NULL,                          -- additional description when leave type is "Others"
    status                  ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED') NOT NULL DEFAULT 'PENDING',  -- current status in the workflow
    with_pay                TINYINT(1) NOT NULL DEFAULT 1,                          -- 1 = leave with pay, 0 = leave without pay
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,                 -- record creation timestamp
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_application_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                   -- prevent deletion of employee with existing applications

    CONSTRAINT fk_application_leave_type
        FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
        ON DELETE RESTRICT ON UPDATE CASCADE                                    -- prevent deletion of a leave type in use
);

-- ============================================================
-- 4. leave_approvals
--    Tracks each step in the multi-level approval workflow.
-- ============================================================

CREATE TABLE IF NOT EXISTS leave_approvals (
    id                      INT AUTO_INCREMENT PRIMARY KEY,                     -- unique row identifier
    leave_application_id    INT NOT NULL,                                       -- FK to leave_applications.id
    approver_id             INT NOT NULL,                                       -- FK to employees.id (the approver)
    level                   INT NOT NULL,                                       -- approval level (1 = immediate supervisor, 2 = HR, etc.)
    status                  ENUM('PENDING', 'APPROVED', 'REJECTED') NOT NULL DEFAULT 'PENDING',  -- decision at this approval level
    remarks                 TEXT DEFAULT NULL,                                  -- optional remarks from the approver
    approved_at             DATETIME DEFAULT NULL,                              -- timestamp when the decision was made
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,                 -- record creation timestamp
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_approval_application
        FOREIGN KEY (leave_application_id) REFERENCES leave_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE,                                    -- cascade delete approvals when application is deleted

    CONSTRAINT fk_approval_approver
        FOREIGN KEY (approver_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE                                    -- prevent deletion of an employee who is an approver
);

-- ============================================================
-- 5. employee_leave_balances
--    Cached current leave balance per employee per leave type.
--    Source of truth is leave_credit_transactions (ledger).
-- ============================================================

CREATE TABLE IF NOT EXISTS employee_leave_balances (
    id              INT AUTO_INCREMENT PRIMARY KEY,                             -- unique row identifier
    employee_id     INT NOT NULL,                                               -- FK to employees.id
    leave_type_id   INT NOT NULL,                                               -- FK to leave_types.id
    balance         DECIMAL(8, 2) NOT NULL DEFAULT 0.00,                        -- current cached balance in days
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,                         -- record creation timestamp
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT uq_employee_leave_balance
        UNIQUE (employee_id, leave_type_id),                                    -- one balance row per employee per leave type

    CONSTRAINT fk_balance_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE CASCADE ON UPDATE CASCADE,                                    -- cascade delete balances when employee is deleted

    CONSTRAINT fk_balance_leave_type
        FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
        ON DELETE RESTRICT ON UPDATE CASCADE                                    -- prevent deletion of a leave type with existing balances
);

-- ============================================================
-- 6. leave_credit_transactions  (LEDGER — source of truth)
--    Records every leave credit and debit movement.
-- ============================================================

CREATE TABLE IF NOT EXISTS leave_credit_transactions (
    id                      INT AUTO_INCREMENT PRIMARY KEY,                     -- unique row identifier
    transaction_number      VARCHAR(20)  NOT NULL UNIQUE,                       -- system-generated transaction number (e.g. TXN-A1B2C3D4)
    employee_id             INT NOT NULL,                                       -- FK to employees.id
    leave_type_id           INT NOT NULL,                                       -- FK to leave_types.id
    transaction_type        ENUM('CREDIT', 'DEBIT') NOT NULL,                  -- CREDIT = balance increase, DEBIT = balance decrease
    amount                  DECIMAL(8, 2) NOT NULL,                             -- number of days credited or debited
    source_type             ENUM('SPECIAL_ORDER', 'LEAVE_APPLICATION', 'MANUAL_ADJUSTMENT', 'SYSTEM_ADJUSTMENT') NOT NULL,  -- origin of the transaction
    source_id               INT NOT NULL,                                       -- ID of the source record (e.g. leave_application.id)
    transaction_date        DATE NOT NULL,                                      -- date the transaction took effect
    balance_snapshot_after  DECIMAL(8, 2) NOT NULL,                             -- employee's balance immediately after this transaction
    remarks                 TEXT DEFAULT NULL,                                  -- optional notes for manual or system adjustments
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,                 -- record creation timestamp

    CONSTRAINT fk_transaction_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                   -- prevent deletion of employee with transaction history

    CONSTRAINT fk_transaction_leave_type
        FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
        ON DELETE RESTRICT ON UPDATE CASCADE                                    -- prevent deletion of leave type with transaction history
);

-- ============================================================
-- SEED DATA — leave_types
--    Standard DepEd leave types with their balance rules.
-- ============================================================

-- ============================================================
-- 7. cto_applications
--    Records activities/events rendered by employees as basis for CTO credits.
--    When approved, a CREDIT is posted to the ledger referencing the special order.
-- ============================================================

CREATE TABLE IF NOT EXISTS cto_applications (
    id                       INT AUTO_INCREMENT PRIMARY KEY,                     -- unique row identifier
    application_number       VARCHAR(20)  NOT NULL UNIQUE,                       -- system-generated number (e.g. CTO-A1B2C3D4)
    employee_id              INT NOT NULL,                                       -- FK to employees.id
    activity_name            VARCHAR(255) NOT NULL,                              -- name of the activity or event participated in
    activity_start_date      DATE NOT NULL,                                      -- date the activity started
    activity_end_date        DATE NOT NULL,                                      -- date the activity ended
    participation_start_date DATE NOT NULL,                                      -- first day the employee participated in the activity
    participation_end_date   DATE NOT NULL,                                      -- last day the employee participated in the activity
    days_rendered            DECIMAL(5, 2) NOT NULL,                             -- total CTO days earned from participation
    special_order_number     VARCHAR(50)  DEFAULT NULL,                          -- special order number issued for this activity
    date_filed               DATE NOT NULL,                                      -- date the application was submitted
    status                   ENUM('PENDING', 'APPROVED', 'REJECTED') NOT NULL DEFAULT 'PENDING',  -- current status of the CTO application
    approved_by              INT DEFAULT NULL,                                   -- FK to employees.id (the approver)
    approved_at              DATETIME DEFAULT NULL,                              -- timestamp when the decision was made
    remarks                  TEXT DEFAULT NULL,                                  -- optional remarks from the approver
    created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,                 -- record creation timestamp
    updated_at               DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_cto_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                    -- prevent deletion of employee with CTO records

    CONSTRAINT fk_cto_approved_by
        FOREIGN KEY (approved_by) REFERENCES employees(id)
        ON DELETE SET NULL ON UPDATE CASCADE                                     -- allow approver deletion without breaking records
);

-- ============================================================
-- SEED DATA — leave_types
--    Standard DepEd leave types with their balance rules.
-- ============================================================

-- ============================================================
-- ALTER: add date_filed to existing cto_applications table
--        Run this if the table was created before this column was added.
-- ============================================================

ALTER TABLE cto_applications
    ADD COLUMN date_filed DATE NOT NULL AFTER special_order_number;

INSERT INTO leave_types (code, name, balance_type, is_active) VALUES
    ('VL',  'Vacation Leave',                  'SELF',           1),  -- deducted from own VL balance
    ('SL',  'Sick Leave',                      'SELF',           1),  -- deducted from own SL balance
    ('SPL', 'Special Privilege Leave',         'SELF',           1),  -- deducted from own SPL balance
    ('FL',  'Forced Leave',                    'CHARGED_TO_VL',  1),  -- charged against VL balance
    ('ML',  'Maternity Leave',                 'NONE',           1),  -- no balance deduction required
    ('PL',  'Paternity Leave',                 'NONE',           1),  -- no balance deduction required
    ('SLB', 'Solo Parent Leave',               'NONE',           1),  -- no balance deduction required
    ('VAWC','VAWC Leave',                      'NONE',           1),  -- no balance deduction required
    ('CTO', 'Compensatory Time Off',           'SELF',           1),  -- deducted from own CTO balance
    ('VSC', 'Vacation Service Credits',        'SELF',           1),  -- deducted from own VSC balance
    ('OL',  'Others',                          'NONE',           1);  -- miscellaneous leave with no balance requirement
