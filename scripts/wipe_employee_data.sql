-- ============================================================================
-- FULL RESET — wipe everything except the admin employee and their login.
--
-- KEEPS exactly two rows of identity:
--     employees  where id = @keep
--     users      where employee_id = @keep
--
-- KEEPS reference data the system cannot run without:
--     leave_types   — code looks these up by code ('VL', 'SL', ...)
--     schools       — the admin's employees row points at one
--     positions     — same
--
-- DELETES everything else, including the admin's own leave history:
--     all leave applications, dates, approvals, refunds
--     the entire ledger, balances, monthly credits, manual deductions
--     all service credits, CTO/VSC pools and deduction logs
--     undertime/tardiness, type conversions
--     special orders and calendar events (holidays)
--     every other employee and every other login
--     the application-number counters, so numbering restarts at 000001
--
-- FOREIGN_KEY_CHECKS is disabled for the wipe so delete order cannot bite.
-- Everything runs in one transaction and rolls back as a unit on error.
--
-- Run the whole file in one session so @keep stays in scope.
-- ============================================================================

SET @keep = 1;   -- <<< admin employee id to preserve

SET FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

-- ── Leave applications and everything hanging off them ──────────────────────
DELETE FROM vsc_deduction_log;
DELETE FROM cto_deduction_log;
DELETE FROM leave_refunded_dates;
DELETE FROM leave_approvals;
DELETE FROM leave_application_dates;
DELETE FROM leave_applications;

-- ── Service credits and the CTO/VSC pools ───────────────────────────────────
DELETE FROM service_credit_dates;
DELETE FROM service_credit_applications;
DELETE FROM cto_credit_balances;
DELETE FROM vsc_old_credit_balances;
DELETE FROM vsc_new_credit_balances;

-- ── Ledger and everything derived from it ───────────────────────────────────
DELETE FROM monthly_leave_credits;
DELETE FROM manual_balance_deductions;
DELETE FROM undertime_tardiness_deductions;
DELETE FROM employee_type_conversions;
DELETE FROM leave_credit_transactions;
DELETE FROM employee_leave_balances;

-- ── Operational configuration ───────────────────────────────────────────────
DELETE FROM special_orders;
DELETE FROM calendar_events;           -- holidays will need re-entering
DELETE FROM application_number_sequences;  -- INSERT IGNORE recreates rows on demand

-- ── Identity: keep only the admin and their account ─────────────────────────
DELETE FROM users     WHERE employee_id <> @keep;
DELETE FROM employees WHERE id          <> @keep;

COMMIT;

SET FOREIGN_KEY_CHECKS = 1;

-- ── Restart auto-increment counters ─────────────────────────────────────────
-- ALTER causes an implicit commit, so these must follow COMMIT.

ALTER TABLE leave_applications             AUTO_INCREMENT = 1;
ALTER TABLE leave_application_dates        AUTO_INCREMENT = 1;
ALTER TABLE leave_approvals                AUTO_INCREMENT = 1;
ALTER TABLE leave_refunded_dates           AUTO_INCREMENT = 1;
ALTER TABLE leave_credit_transactions      AUTO_INCREMENT = 1;
ALTER TABLE employee_leave_balances        AUTO_INCREMENT = 1;
ALTER TABLE monthly_leave_credits          AUTO_INCREMENT = 1;
ALTER TABLE manual_balance_deductions      AUTO_INCREMENT = 1;
ALTER TABLE undertime_tardiness_deductions AUTO_INCREMENT = 1;
ALTER TABLE employee_type_conversions      AUTO_INCREMENT = 1;
ALTER TABLE service_credit_applications    AUTO_INCREMENT = 1;
ALTER TABLE service_credit_dates           AUTO_INCREMENT = 1;
ALTER TABLE cto_credit_balances            AUTO_INCREMENT = 1;
ALTER TABLE cto_deduction_log              AUTO_INCREMENT = 1;
ALTER TABLE vsc_old_credit_balances        AUTO_INCREMENT = 1;
ALTER TABLE vsc_new_credit_balances        AUTO_INCREMENT = 1;
ALTER TABLE vsc_deduction_log              AUTO_INCREMENT = 1;
ALTER TABLE special_orders                 AUTO_INCREMENT = 1;
ALTER TABLE calendar_events                AUTO_INCREMENT = 1;

-- ── Verify ──────────────────────────────────────────────────────────────────
-- Every row must read 0, except employees and users which must read 1.

SELECT 'leave_applications'             AS t, COUNT(*) AS n FROM leave_applications
UNION ALL SELECT 'leave_application_dates',        COUNT(*) FROM leave_application_dates
UNION ALL SELECT 'leave_approvals',                COUNT(*) FROM leave_approvals
UNION ALL SELECT 'leave_refunded_dates',           COUNT(*) FROM leave_refunded_dates
UNION ALL SELECT 'leave_credit_transactions',      COUNT(*) FROM leave_credit_transactions
UNION ALL SELECT 'employee_leave_balances',        COUNT(*) FROM employee_leave_balances
UNION ALL SELECT 'monthly_leave_credits',          COUNT(*) FROM monthly_leave_credits
UNION ALL SELECT 'manual_balance_deductions',      COUNT(*) FROM manual_balance_deductions
UNION ALL SELECT 'undertime_tardiness_deductions', COUNT(*) FROM undertime_tardiness_deductions
UNION ALL SELECT 'employee_type_conversions',      COUNT(*) FROM employee_type_conversions
UNION ALL SELECT 'service_credit_applications',    COUNT(*) FROM service_credit_applications
UNION ALL SELECT 'service_credit_dates',           COUNT(*) FROM service_credit_dates
UNION ALL SELECT 'cto_credit_balances',            COUNT(*) FROM cto_credit_balances
UNION ALL SELECT 'cto_deduction_log',              COUNT(*) FROM cto_deduction_log
UNION ALL SELECT 'vsc_old_credit_balances',        COUNT(*) FROM vsc_old_credit_balances
UNION ALL SELECT 'vsc_new_credit_balances',        COUNT(*) FROM vsc_new_credit_balances
UNION ALL SELECT 'vsc_deduction_log',              COUNT(*) FROM vsc_deduction_log
UNION ALL SELECT 'special_orders',                 COUNT(*) FROM special_orders
UNION ALL SELECT 'calendar_events',                COUNT(*) FROM calendar_events
UNION ALL SELECT 'application_number_sequences',   COUNT(*) FROM application_number_sequences
UNION ALL SELECT '-- kept below --',               NULL
UNION ALL SELECT 'employees (expect 1)',           COUNT(*) FROM employees
UNION ALL SELECT 'users (expect 1)',               COUNT(*) FROM users
UNION ALL SELECT 'leave_types (reference)',        COUNT(*) FROM leave_types
UNION ALL SELECT 'schools (reference)',            COUNT(*) FROM schools
UNION ALL SELECT 'positions (reference)',          COUNT(*) FROM positions;
