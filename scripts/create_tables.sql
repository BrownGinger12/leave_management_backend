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
    division            VARCHAR(100) DEFAULT NULL,                               -- division name, optional
    original_appointment DATE DEFAULT NULL,                                      -- date of original appointment, optional
    latest_appointment  DATE DEFAULT NULL,                                       -- date of latest appointment, optional
    position            VARCHAR(150) DEFAULT NULL,                               -- job position or title, optional
    salary              DECIMAL(12, 2) DEFAULT NULL,                             -- monthly salary, optional
    contact_number      VARCHAR(20) DEFAULT NULL,                                -- contact number, optional
    is_active           TINYINT(1) NOT NULL DEFAULT 1,                           -- 1 = active, 0 = soft-deleted
    photo               VARCHAR(255) DEFAULT NULL,                               -- path/URL to the employee's photo, optional
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
    reason                  TEXT NOT NULL,                                      -- reason stated by the employee for the leave
    other_leave_description VARCHAR(255) DEFAULT NULL,                          -- additional description when leave type is "Others"
    status                  ENUM('FOR HRMO ACTION', 'FOR APPROVAL', 'RETURNED', 'DISAPPROVED', 'APPROVED') NOT NULL DEFAULT 'FOR HRMO ACTION',  -- current status in the workflow
    status_updated_by       INT DEFAULT NULL,                                   -- FK to employees.id; the approver who last changed the status
    is_deleted              TINYINT(1) NOT NULL DEFAULT 0,                      -- 1 = soft-deleted; excluded from all queries
    deleted_at              DATETIME DEFAULT NULL,                              -- timestamp when the record was soft-deleted
    deleted_by              INT DEFAULT NULL,                                   -- FK to users.id; the user who performed the soft delete
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,                 -- record creation timestamp
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_application_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                   -- prevent deletion of employee with existing applications

    CONSTRAINT fk_application_leave_type
        FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                   -- prevent deletion of a leave type in use

    CONSTRAINT fk_app_status_updated_by
        FOREIGN KEY (status_updated_by) REFERENCES employees(id)
        ON DELETE SET NULL ON UPDATE CASCADE                                    -- nullify if the employee record is deleted
);

-- ============================================================
-- 4. leave_application_dates
--    Stores each individual leave date for a leave application.
--    Replaces start_date/end_date/total_days on the header table.
--    duration_type: FULL_DAY (1.0 day) or HALF_DAY (0.5 day).
--    half_day_period: AM or PM (NULL for FULL_DAY).
--    is_paid: whether the employee is paid for this specific date.
-- ============================================================

CREATE TABLE IF NOT EXISTS leave_application_dates (
    id                      INT AUTO_INCREMENT PRIMARY KEY,                          -- unique row identifier
    leave_application_id    INT NOT NULL,                                            -- FK to leave_applications.id
    leave_date              DATE NOT NULL,                                           -- the specific leave date
    duration_type           ENUM('FULL_DAY', 'HALF_DAY') NOT NULL,                  -- FULL_DAY = 1.0, HALF_DAY = 0.5
    half_day_period         ENUM('AM', 'PM') NULL DEFAULT NULL,                     -- AM or PM; NULL for FULL_DAY entries
    is_paid                 TINYINT(1) NOT NULL DEFAULT 1,                          -- 1 = paid leave for this date, 0 = no-pay
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,                      -- record creation timestamp
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_lad_application
        FOREIGN KEY (leave_application_id) REFERENCES leave_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE                                          -- remove dates when application is deleted
);

-- ============================================================
-- 5. leave_approvals
--    Tracks each step in the multi-level approval workflow.
-- ============================================================

CREATE TABLE IF NOT EXISTS leave_approvals (
    id                      INT AUTO_INCREMENT PRIMARY KEY,                     -- unique row identifier
    leave_application_id    INT NOT NULL,                                       -- FK to leave_applications.id
    approver_id             INT NOT NULL,                                       -- FK to employees.id (the approver)
    level                   INT NOT NULL,                                       -- approval level (1 = immediate supervisor, 2 = HR, etc.)
    status                  ENUM('FOR APPROVAL', 'APPROVED', 'RETURNED', 'DISAPPROVED') NOT NULL,  -- decision at this approval level
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
-- 7. special_orders
--    Stores Special Orders that authorize CTO and VSC service credits.
--    Each Special Order is referenced by one or more service_credit_applications.
-- ============================================================

CREATE TABLE IF NOT EXISTS special_orders (
    id               INT AUTO_INCREMENT PRIMARY KEY,                              -- unique row identifier
    special_order    VARCHAR(100) NOT NULL UNIQUE,                                -- Special Order number (e.g. SO-2026-001)
    activity_name    VARCHAR(255) NOT NULL,                                       -- name or description of the activity covered by this SO
    reference        VARCHAR(100) DEFAULT NULL,                                   -- reference document identifier
    date_of_activity DATE NOT NULL,                                               -- date the activity took place
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,                          -- record creation timestamp
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- record last update timestamp
);

-- ============================================================
-- 8. service_credit_applications
--    Records CTO and VSC credit applications for hours rendered by employees.
--    CTO credits expire 1 year from the latest participation date.
--    VSC credits do not expire (expiration_date is NULL).
--    When approved, a CREDIT is posted to the ledger for the appropriate leave type.
-- ============================================================

DROP TABLE IF EXISTS cto_applications;                                           -- remove the old cto_applications table (replaced by service_credit_applications)

CREATE TABLE IF NOT EXISTS service_credit_applications (
    id                  INT AUTO_INCREMENT PRIMARY KEY,                          -- unique row identifier
    application_number  VARCHAR(20)  NOT NULL UNIQUE,                            -- system-generated number (e.g. SC-A1B2C3D4)
    employee_id         INT NOT NULL,                                            -- FK to employees.id
    special_order_id    INT NOT NULL,                                            -- FK to special_orders.id; the SO authorizing this credit
    type                ENUM('CTO', 'VSC') NOT NULL,                             -- credit type: CTO (Compensatory Time Off) or VSC (Vacation Service Credits)
    hours_rendered      DECIMAL(6, 2) NOT NULL,                                  -- total hours rendered by the employee
    balance_earned      DECIMAL(6, 2) NOT NULL,                                  -- computed credit: hours_rendered / 8 * 1.5
    valid_until         DATE DEFAULT NULL,                                        -- expiry date: auto (latest date + 1 yr) or manual for CTO; NULL for VSC
    date_filed          DATE NOT NULL,                                            -- date the application was submitted
    date_of_upload      DATE DEFAULT NULL,                                        -- date the supporting document was uploaded
    uploaded_by         INT DEFAULT NULL,                                         -- FK to employees.id; the employee who uploaded the supporting document
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,                       -- record creation timestamp
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_sc_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                     -- prevent deletion of employee with service credit records

    CONSTRAINT fk_sc_special_order
        FOREIGN KEY (special_order_id) REFERENCES special_orders(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                     -- prevent deletion of a special order referenced by an application

    CONSTRAINT fk_sc_uploaded_by
        FOREIGN KEY (uploaded_by) REFERENCES employees(id)
        ON DELETE SET NULL ON UPDATE CASCADE                                      -- nullify if the uploader employee is deleted
);

-- ============================================================
-- 8. service_credit_dates
--    Stores individual participation dates for each service credit application.
--    Replaces the old participation_start_date / participation_end_date range.
-- ============================================================

CREATE TABLE IF NOT EXISTS service_credit_dates (
    id                              INT AUTO_INCREMENT PRIMARY KEY,               -- unique row identifier
    service_credit_application_id   INT NOT NULL,                                 -- FK to service_credit_applications.id
    date                            DATE NOT NULL,                                -- one participation date

    CONSTRAINT fk_sc_dates_application
        FOREIGN KEY (service_credit_application_id) REFERENCES service_credit_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE                                       -- cascade delete dates when the parent application is deleted
);

-- ============================================================
-- 9. cto_credit_balances
--    Tracks the remaining spendable balance of each CTO service
--    credit application. Populated when a CTO application is
--    submitted; debited when a CTO leave application is approved.
--    VSC credits are NOT tracked here (no expiry, different rules).
-- ============================================================

CREATE TABLE IF NOT EXISTS cto_credit_balances (
    id                              INT AUTO_INCREMENT PRIMARY KEY,               -- unique row identifier
    service_credit_application_id   INT NOT NULL,                                 -- FK to the source CTO service credit application
    employee_id                     INT NOT NULL,                                 -- FK to employees.id (denormalized for fast lookup)
    original_balance                DECIMAL(10,2) NOT NULL,                       -- credit amount at time of application submission
    remaining_balance               DECIMAL(10,2) NOT NULL,                       -- days still available for leave deduction
    valid_until                     DATE NOT NULL,                                -- expiry date (latest participation date + 1 year)
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,          -- record creation timestamp
    updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- last update timestamp

    UNIQUE KEY uq_sca (service_credit_application_id),                            -- one balance record per CTO application

    CONSTRAINT fk_cto_bal_sca
        FOREIGN KEY (service_credit_application_id) REFERENCES service_credit_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE,                                       -- remove balance when parent application is deleted

    CONSTRAINT fk_cto_bal_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE CASCADE ON UPDATE CASCADE                                        -- remove balance when employee is deleted
);

-- ============================================================
-- 10. cto_deduction_log
--     Audit log for each partial CTO deduction applied against
--     a leave application. Required for clean balance restoration
--     when a CTO leave is RETURNED or DISAPPROVED.
-- ============================================================

CREATE TABLE IF NOT EXISTS cto_deduction_log (
    id                      INT AUTO_INCREMENT PRIMARY KEY,                       -- unique row identifier
    cto_credit_balance_id   INT NOT NULL,                                         -- FK to the credit record that was debited
    leave_application_id    INT NOT NULL,                                         -- FK to the leave application that consumed the credit
    amount_deducted         DECIMAL(10,2) NOT NULL,                               -- days taken from this specific credit
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                  -- when the deduction was recorded

    CONSTRAINT fk_deduct_log_balance
        FOREIGN KEY (cto_credit_balance_id) REFERENCES cto_credit_balances(id)
        ON DELETE CASCADE ON UPDATE CASCADE,                                       -- remove log when credit record is deleted

    CONSTRAINT fk_deduct_log_application
        FOREIGN KEY (leave_application_id) REFERENCES leave_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE                                        -- remove log when leave application is deleted
);

-- ============================================================
-- 11. users
--    System login accounts linked to employee records.
--    Passwords are hashed with bcrypt before storage.
--    Roles: ADMIN, DIVISION_PERSONNEL, TEACHING_PERSONNEL
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,                               -- unique row identifier
    employee_id     INT NOT NULL UNIQUE,                                          -- FK to employees.id; one account per employee
    username        VARCHAR(100) NOT NULL UNIQUE,                                 -- unique login username
    password_hash   VARCHAR(255) NOT NULL,                                        -- bcrypt hash of the password; never store plain text
    role            ENUM('ADMIN', 'DIVISION_PERSONNEL', 'TEACHING_PERSONNEL') NOT NULL,  -- access level
    is_active       TINYINT(1) NOT NULL DEFAULT 1,                                -- 1 = active, 0 = deactivated
    last_login_at   DATETIME DEFAULT NULL,                                        -- timestamp of the most recent successful login
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,                           -- record creation timestamp
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- record last update timestamp

    CONSTRAINT fk_user_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE                                      -- prevent deletion of employee with an existing account
);

-- ============================================================
-- 10. monthly_leave_credits
--     Tracks one VL or SL credit entry per employee per month.
--     The UNIQUE constraint prevents double-crediting the same
--     employee for the same leave type in the same month/year.
--     Each record links back to the leave_credit_transactions ledger.
-- ============================================================

CREATE TABLE IF NOT EXISTS monthly_leave_credits (
    id              INT AUTO_INCREMENT PRIMARY KEY,                               -- unique row identifier
    employee_id     INT NOT NULL,                                                 -- FK to employees.id
    leave_type_id   INT NOT NULL,                                                 -- FK to leave_types.id (VL or SL only)
    year            SMALLINT NOT NULL,                                            -- calendar year of the credit
    month           TINYINT NOT NULL,                                             -- calendar month of the credit (1–12)
    amount          DECIMAL(6, 2) NOT NULL,                                       -- number of days credited
    transaction_id  INT NOT NULL,                                                 -- FK to leave_credit_transactions.id
    credited_at     DATETIME DEFAULT CURRENT_TIMESTAMP,                           -- timestamp when the credit was applied

    CONSTRAINT uq_monthly_credit
        UNIQUE (employee_id, leave_type_id, year, month),                         -- one credit per employee per leave type per month

    CONSTRAINT fk_mlc_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                     -- prevent deletion of employee with credit history

    CONSTRAINT fk_mlc_leave_type
        FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,                                     -- prevent deletion of leave type with credit history

    CONSTRAINT fk_mlc_transaction
        FOREIGN KEY (transaction_id) REFERENCES leave_credit_transactions(id)
        ON DELETE RESTRICT ON UPDATE CASCADE                                      -- prevent deletion of ledger record tied to a monthly credit
);

-- ============================================================
-- 12. schools
--     Reference table of all schools in the division.
--     Used for employee assignment and reporting.
-- ============================================================

CREATE TABLE IF NOT EXISTS schools (
    id          INT AUTO_INCREMENT PRIMARY KEY,              -- unique row identifier
    name        VARCHAR(255) NOT NULL,                       -- official school name
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP          -- record creation timestamp
);

INSERT IGNORE INTO schools (name) VALUES
    ('Agudo E/S'),
    ('Alimatoc E/S'),
    ('Alingating E/S'),
    ('Aluyan E/S'),
    ('Andres Bonifacio E/S'),
    ('Balandra E/S'),
    ('Banquerohan NHS'),
    ('Bayabas E/S'),
    ('Burgos E/S'),
    ('Burgos NHS'),
    ('Cabahug E/S'),
    ('Cadiz East I E/S'),
    ('Cadiz East II E/S'),
    ('Cadiz Viejo E/S'),
    ('Cadiz Viejo NHS'),
    ('Cadiz West I E/S'),
    ('Cadiz West II E/S'),
    ('Caduha-an E/S'),
    ('Caduha-an NHS'),
    ('CNHS - A. Bonifacio Ext.'),
    ('CNHS - Luna Ext. HS'),
    ('CNHS - Tagbanon Ext. HS'),
    ('Cotcot E/S'),
    ('Daga E/S'),
    ('Don Luis Consing E/S'),
    ('Don R. Jesena E/S'),
    ('Dr. VF Gustilo E/S'),
    ('Dr. Vicente F. Gustilo Memorial NHS'),
    ('DVFGMNHS - Daga Ext. HS'),
    ('Egido Fernandez E/S'),
    ('Escolastica E/S'),
    ('F.M. Cabras E/S'),
    ('Floro Reboton E/S'),
    ('Gen A. Lacson E/S'),
    ('Hiyang-Hiyang E/S'),
    ('Hon P. Villena E/S'),
    ('Igcamalig E/S'),
    ('Jerusalem NHS'),
    ('Luis Uy Chiat E/S'),
    ('M.J Escalante E/S'),
    ('M.V. Gamboa E/S'),
    ('Mabini E/S'),
    ('Mabini NHS'),
    ('Manara E/S'),
    ('Martin A. Quiachon E/S'),
    ('MNHS - Alimatoc Ext'),
    ('Paniqui-on E/S'),
    ('Pedro E. Ramos E/S'),
    ('Pedro Pitogo E/S'),
    ('Progreso E/S'),
    ('San Andres E/S'),
    ('San Rafael E/S'),
    ('Sangay E/S'),
    ('Severino Escaro E/S'),
    ('Sewahon E/S'),
    ('Sicaba NHS'),
    ('Sombito E/S'),
    ('SPED HS'),
    ('SPED Training Center'),
    ('Tagbanon E/S'),
    ('Tiglawigan E/S'),
    ('Tiglawigan NHS'),
    ('TNHS - Magsaysay Ext. HS'),
    ('Tres Andanas E/S'),
    ('Vicente Patricio E/S'),
    ('Villacin E/S'),
    ('Villacin NHS'),
    ('VNHS - Sewahon Ext.'),
    ('Yee-On E/S');

-- ============================================================
-- 13. positions
--     Reference table of all teaching and non-teaching positions
--     in the division. type: TEACHING or NON_TEACHING.
-- ============================================================

CREATE TABLE IF NOT EXISTS positions (
    id          INT AUTO_INCREMENT PRIMARY KEY,                              -- unique row identifier
    name        VARCHAR(255) NOT NULL,                                       -- official position name
    type        ENUM('TEACHING', 'NON_TEACHING') NOT NULL,                  -- employee classification this position belongs to
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP                          -- record creation timestamp
);

INSERT IGNORE INTO positions (name, type) VALUES
    -- Non-Teaching positions
    ('Casual',                              'NON_TEACHING'),
    ('Watchman',                            'NON_TEACHING'),
    ('Security Guard',                      'NON_TEACHING'),
    ('Chief Education Supervisor - SGOD',   'NON_TEACHING'),
    ('Chief Education Supervisor - CID',    'NON_TEACHING'),
    ('Public Schools District Supervisor',  'NON_TEACHING'),
    ('Education Program Supervisor',        'NON_TEACHING'),
    ('Senior Education Program Specialist', 'NON_TEACHING'),
    ('Education Program Specialist II',     'NON_TEACHING'),
    ('Librarian II',                        'NON_TEACHING'),
    ('Guidance Counselor III',              'NON_TEACHING'),
    ('Guidance Counselor II',               'NON_TEACHING'),
    ('Guidance Counselor I',                'NON_TEACHING'),
    ('Registrar I',                         'NON_TEACHING'),
    ('Teacher-In-Charge',                   'NON_TEACHING'),
    ('Head Teacher I',                      'NON_TEACHING'),
    ('Head Teacher II',                     'NON_TEACHING'),
    ('Head Teacher III',                    'NON_TEACHING'),
    ('School Principal I',                  'NON_TEACHING'),
    ('School Principal II',                 'NON_TEACHING'),
    ('School Principal III',                'NON_TEACHING'),
    ('School Principal IV',                 'NON_TEACHING'),
    ('Assistant School Principal II',       'NON_TEACHING'),
    ('Information Technology Officer I',    'NON_TEACHING'),
    ('Administrative Officer V',            'NON_TEACHING'),
    ('Administrative Officer IV',           'NON_TEACHING'),
    ('Project Development Officer II',      'NON_TEACHING'),
    ('Nurse II',                            'NON_TEACHING'),
    ('Project Development Officer I',       'NON_TEACHING'),
    ('Administrative Officer II',           'NON_TEACHING'),
    ('Administrative Assistant III',        'NON_TEACHING'),
    ('Administrative Assistant II',         'NON_TEACHING'),
    ('Administrative Assistant I',          'NON_TEACHING'),
    ('Administrative Aide VI (Clerk III)',   'NON_TEACHING'),
    ('Administrative Aide IV (Driver)',      'NON_TEACHING'),
    ('Administrative Aide III (Driver)',     'NON_TEACHING'),
    ('Dentist II',                           'NON_TEACHING'),
    ('Administrative Aide I',               'NON_TEACHING'),
    ('Administrative Aide IV (Clerk II)',    'NON_TEACHING'),
    ('Administrative Aide III (Clerk I)',    'NON_TEACHING'),
    -- Teaching positions
    ('Teacher I',                   'TEACHING'),
    ('Teacher II',                  'TEACHING'),
    ('Teacher III',                 'TEACHING'),
    ('Teacher IV',                  'TEACHING'),
    ('Teacher VI',                  'TEACHING'),
    ('Teacher VII',                 'TEACHING'),
    ('Master Teacher I',            'TEACHING'),
    ('Master Teacher II',           'TEACHING'),
    ('Master Teacher III',          'TEACHING'),
    ('Master Teacher IV',           'TEACHING'),
    ('Master Teacher V',            'TEACHING'),
    ('Special Education Teacher I', 'TEACHING'),
    ('Special Science Teacher I',   'TEACHING');

-- ============================================================
-- 14. vsc_old_credit_balances
--     Tracks VSC service credits earned from activities with
--     date_of_activity < 2024-10-01 (on or before 2024-09-20).
--     One row per VSC service credit application in this period.
-- ============================================================

CREATE TABLE IF NOT EXISTS vsc_old_credit_balances (
    id                              INT AUTO_INCREMENT PRIMARY KEY,               -- unique row identifier
    service_credit_application_id   INT NOT NULL,                                 -- FK to the source VSC service credit application
    employee_id                     INT NOT NULL,                                 -- FK to employees.id (denormalized for fast lookup)
    original_balance                DECIMAL(10,2) NOT NULL,                       -- credit amount at time of application submission
    remaining_balance               DECIMAL(10,2) NOT NULL,                       -- days still available (mirrors original; no per-credit deduction tracking)
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,          -- record creation timestamp
    updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- last update timestamp

    UNIQUE KEY uq_vsc_old_sca (service_credit_application_id),                   -- one balance record per VSC application

    CONSTRAINT fk_vsc_old_sca
        FOREIGN KEY (service_credit_application_id) REFERENCES service_credit_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE,                                       -- remove balance when parent application is deleted

    CONSTRAINT fk_vsc_old_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE CASCADE ON UPDATE CASCADE                                        -- remove balance when employee is deleted
);

-- ============================================================
-- 14. vsc_new_credit_balances
--     Tracks VSC service credits earned from activities with
--     date_of_activity >= 2024-10-01.
--     One row per VSC service credit application in this period.
-- ============================================================

CREATE TABLE IF NOT EXISTS vsc_new_credit_balances (
    id                              INT AUTO_INCREMENT PRIMARY KEY,               -- unique row identifier
    service_credit_application_id   INT NOT NULL,                                 -- FK to the source VSC service credit application
    employee_id                     INT NOT NULL,                                 -- FK to employees.id (denormalized for fast lookup)
    original_balance                DECIMAL(10,2) NOT NULL,                       -- credit amount at time of application submission
    remaining_balance               DECIMAL(10,2) NOT NULL,                       -- days still available (mirrors original; no per-credit deduction tracking)
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,          -- record creation timestamp
    updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- last update timestamp

    UNIQUE KEY uq_vsc_new_sca (service_credit_application_id),                   -- one balance record per VSC application

    CONSTRAINT fk_vsc_new_sca
        FOREIGN KEY (service_credit_application_id) REFERENCES service_credit_applications(id)
        ON DELETE CASCADE ON UPDATE CASCADE,                                       -- remove balance when parent application is deleted

    CONSTRAINT fk_vsc_new_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE CASCADE ON UPDATE CASCADE                                        -- remove balance when employee is deleted
);

-- ============================================================
-- 15. calendar_events
--     Tracks holidays and special days that affect leave rules.
--     blocks_leave = 1: cannot apply leave on this date (holiday).
--     is_paid = 0: leave applied on this date is no-pay.
--     Each date can only have one entry (UNIQUE constraint on date).
-- ============================================================

CREATE TABLE IF NOT EXISTS calendar_events (
    id           INT AUTO_INCREMENT PRIMARY KEY,                              -- unique row identifier
    date         DATE NOT NULL UNIQUE,                                        -- one ruling per calendar date
    name         VARCHAR(255) NOT NULL,                                       -- display name (e.g. "Christmas Day")
    blocks_leave TINYINT(1) NOT NULL DEFAULT 0,                              -- 1 = holiday: leave application blocked on this date
    period       ENUM('FULL', 'AM', 'PM') NOT NULL DEFAULT 'FULL',          -- FULL = full day; AM or PM = half day
    created_by   INT NULL,                                                    -- FK to users.id (admin who set this event)
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,                         -- record creation timestamp
    FOREIGN KEY (created_by) REFERENCES users(id)                            -- link to the admin user
);

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
    ('OL',  'Others',                          'NONE',           1),  -- miscellaneous leave with no balance requirement
    ('WL',  'Wellness Leave',                  'SELF',           1);  -- deducted from own WL balance
