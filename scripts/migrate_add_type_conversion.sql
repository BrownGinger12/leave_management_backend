-- ============================================================
-- Migration: Add TYPE_CONVERSION support
-- Run this on existing databases that already have all tables.
-- Safe to run multiple times — uses IF NOT EXISTS where possible.
-- ============================================================

USE leave_management;

-- Step 1: Extend the source_type ENUM on the ledger table to include
--         TYPE_CONVERSION.  MySQL requires the full ENUM list on MODIFY.
ALTER TABLE leave_credit_transactions
    MODIFY COLUMN source_type ENUM(
        'SPECIAL_ORDER',
        'LEAVE_APPLICATION',
        'MANUAL_ADJUSTMENT',
        'SYSTEM_ADJUSTMENT',
        'HOLIDAY_REFUND',
        'MONETIZATION',
        'FORWARDED_BALANCE',
        'UNDERTIME_TARDINESS',
        'TYPE_CONVERSION'
    ) NOT NULL;

-- Step 2: Allow conversion entries in VSC balance tables (no SCA needed).
--         NULL service_credit_application_id = balance transfer from type conversion.
ALTER TABLE vsc_old_credit_balances
    MODIFY COLUMN service_credit_application_id INT NULL,
    ADD COLUMN remarks VARCHAR(255) DEFAULT NULL;

ALTER TABLE vsc_new_credit_balances
    MODIFY COLUMN service_credit_application_id INT NULL,
    ADD COLUMN remarks VARCHAR(255) DEFAULT NULL;

-- Step 3: Create the personnel type conversion audit table.
CREATE TABLE IF NOT EXISTS employee_type_conversions (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    conversion_number       VARCHAR(20)  NOT NULL UNIQUE,
    employee_id             INT NOT NULL,
    from_type               ENUM('TEACHING', 'NON_TEACHING') NOT NULL,
    to_type                 ENUM('TEACHING', 'NON_TEACHING') NOT NULL,

    -- TEACHING → NON_TEACHING fields
    vsc_balance_before      DECIMAL(10, 4) DEFAULT NULL,
    total_credits_converted DECIMAL(10, 4) DEFAULT NULL,
    vl_balance_after        DECIMAL(10, 4) DEFAULT NULL,

    -- NON_TEACHING → TEACHING fields (or 0 for TEACHING→NON_TEACHING)
    sl_balance_after        DECIMAL(10, 4) DEFAULT NULL,
    vl_balance_before       DECIMAL(10, 4) DEFAULT NULL,
    sl_balance_before       DECIMAL(10, 4) DEFAULT NULL,
    vsc_balance_after       DECIMAL(10, 4) DEFAULT NULL,

    conversion_date         DATE NOT NULL,
    remarks                 TEXT DEFAULT NULL,
    created_by              INT DEFAULT NULL,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_etc_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_etc_created_by
        FOREIGN KEY (created_by) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE
);
