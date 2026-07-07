-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jul 07, 2026 at 08:05 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 7.4.10

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `leave_management`
--

-- --------------------------------------------------------

--
-- Table structure for table `calendar_events`
--

CREATE TABLE `calendar_events` (
  `id` int(11) NOT NULL,
  `date` date NOT NULL,
  `name` varchar(255) NOT NULL,
  `blocks_leave` tinyint(1) NOT NULL DEFAULT 0,
  `period` enum('FULL','AM','PM') NOT NULL DEFAULT 'FULL',
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Dumping data for table `calendar_events`
--

INSERT INTO `calendar_events` (`id`, `date`, `name`, `blocks_leave`, `period`, `created_by`, `created_at`) VALUES
(1, '2026-06-30', 'new year', 1, 'FULL', 1, '2026-06-29 11:48:25'),
(2, '2026-06-25', 'sadsdasd', 1, 'FULL', 1, '2026-06-29 13:40:40'),
(3, '2026-08-22', 'holiday', 1, 'FULL', 1, '2026-06-29 14:21:14'),
(4, '2026-07-30', 'holiday', 1, 'FULL', 1, '2026-07-06 14:43:58');

-- --------------------------------------------------------

--
-- Table structure for table `cto_credit_balances`
--

CREATE TABLE `cto_credit_balances` (
  `id` int(11) NOT NULL,
  `service_credit_application_id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `original_balance` decimal(10,2) NOT NULL,
  `remaining_balance` decimal(10,2) NOT NULL,
  `valid_until` date NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `cto_deduction_log`
--

CREATE TABLE `cto_deduction_log` (
  `id` int(11) NOT NULL,
  `cto_credit_balance_id` int(11) NOT NULL,
  `leave_application_id` int(11) NOT NULL,
  `amount_deducted` decimal(10,2) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `employees`
--

CREATE TABLE `employees` (
  `id` int(11) NOT NULL,
  `leave_card_number` varchar(20) NOT NULL,
  `employee_number` varchar(50) NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `middle_name` varchar(100) DEFAULT NULL,
  `email` varchar(150) NOT NULL,
  `employee_type` enum('TEACHING','NON_TEACHING') NOT NULL,
  `employment_status` enum('PERMANENT','TEMPORARY','CASUAL','CONTRACT_OF_SERVICE') NOT NULL,
  `school_id` int(11) NOT NULL,
  `division` varchar(100) DEFAULT NULL,
  `original_appointment` date DEFAULT NULL,
  `latest_appointment` date DEFAULT NULL,
  `position` varchar(150) DEFAULT NULL,
  `salary` decimal(12,2) DEFAULT NULL,
  `contact_number` varchar(20) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `photo` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `notes` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `employee_leave_balances`
--

CREATE TABLE `employee_leave_balances` (
  `id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `leave_type_id` int(11) NOT NULL,
  `balance` decimal(8,2) NOT NULL DEFAULT 0.00,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `employee_type_conversions`
--

CREATE TABLE `employee_type_conversions` (
  `id` int(11) NOT NULL,
  `conversion_number` varchar(20) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `from_type` enum('TEACHING','NON_TEACHING') NOT NULL,
  `to_type` enum('TEACHING','NON_TEACHING') NOT NULL,
  `vsc_balance_before` decimal(10,4) DEFAULT NULL,
  `total_credits_converted` decimal(10,4) DEFAULT NULL,
  `vl_balance_after` decimal(10,4) DEFAULT NULL,
  `sl_balance_after` decimal(10,4) DEFAULT NULL,
  `vl_balance_before` decimal(10,4) DEFAULT NULL,
  `sl_balance_before` decimal(10,4) DEFAULT NULL,
  `vsc_balance_after` decimal(10,4) DEFAULT NULL,
  `conversion_date` date NOT NULL,
  `remarks` text DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `leave_applications`
--

CREATE TABLE `leave_applications` (
  `id` int(11) NOT NULL,
  `application_number` varchar(20) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `leave_type_id` int(11) NOT NULL,
  `date_filed` date NOT NULL,
  `reason` text NOT NULL,
  `other_leave_description` varchar(255) DEFAULT NULL,
  `status` enum('FOR HRMO ACTION','FOR APPROVAL','RETURNED','DISAPPROVED','APPROVED') NOT NULL DEFAULT 'FOR HRMO ACTION',
  `status_updated_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
  `deleted_at` datetime DEFAULT NULL,
  `deleted_by` int(11) DEFAULT NULL,
  `mnt_vl_days` decimal(8,2) DEFAULT NULL,
  `mnt_sl_days` decimal(8,2) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `leave_application_dates`
--

CREATE TABLE `leave_application_dates` (
  `id` int(11) NOT NULL,
  `leave_application_id` int(11) NOT NULL,
  `leave_date` date NOT NULL,
  `duration_type` enum('FULL_DAY','HALF_DAY') NOT NULL,
  `half_day_period` enum('AM','PM') DEFAULT NULL,
  `is_paid` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `leave_approvals`
--

CREATE TABLE `leave_approvals` (
  `id` int(11) NOT NULL,
  `leave_application_id` int(11) NOT NULL,
  `approver_id` int(11) NOT NULL,
  `level` int(11) NOT NULL,
  `status` enum('FOR APPROVAL','APPROVED','RETURNED','DISAPPROVED') NOT NULL,
  `remarks` text DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `leave_credit_transactions`
--

CREATE TABLE `leave_credit_transactions` (
  `id` int(11) NOT NULL,
  `transaction_number` varchar(20) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `leave_type_id` int(11) NOT NULL,
  `transaction_type` enum('CREDIT','DEBIT') NOT NULL,
  `amount` decimal(8,2) NOT NULL,
  `source_type` enum('SPECIAL_ORDER','LEAVE_APPLICATION','MANUAL_ADJUSTMENT','SYSTEM_ADJUSTMENT','HOLIDAY_REFUND','MONETIZATION','FORWARDED_BALANCE','UNDERTIME_TARDINESS','TYPE_CONVERSION') NOT NULL,
  `source_id` int(11) NOT NULL,
  `transaction_date` date NOT NULL,
  `balance_snapshot_after` decimal(8,2) NOT NULL,
  `remarks` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `leave_refunded_dates`
--

CREATE TABLE `leave_refunded_dates` (
  `id` int(11) NOT NULL,
  `leave_application_id` int(11) NOT NULL,
  `calendar_event_id` int(11) NOT NULL,
  `holiday_date` date NOT NULL,
  `amount_refunded` decimal(8,2) NOT NULL,
  `credited_leave_type_id` int(11) NOT NULL,
  `refunded_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `leave_types`
--

CREATE TABLE `leave_types` (
  `id` int(11) NOT NULL,
  `code` varchar(10) NOT NULL,
  `name` varchar(100) NOT NULL,
  `balance_type` enum('SELF','CHARGED_TO_VL','CHARGED_TO_VSC','NONE') NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Dumping data for table `leave_types`
--

INSERT INTO `leave_types` (`id`, `code`, `name`, `balance_type`, `is_active`, `created_at`, `updated_at`) VALUES
(1, 'VL', 'Vacation Leave', 'SELF', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(2, 'SL', 'Sick Leave', 'SELF', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(3, 'SPL', 'Special Privilege Leave', 'SELF', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(4, 'FL', 'Forced Leave', 'CHARGED_TO_VL', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(5, 'ML', 'Maternity Leave', 'NONE', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(6, 'PL', 'Paternity Leave', 'NONE', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(7, 'SLB', 'Solo Parent Leave', 'NONE', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(8, 'VAWC', 'VAWC Leave', 'NONE', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(9, 'CTO', 'Compensatory Time Off', 'SELF', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(10, 'VSC', 'Vacation Service Credits', 'SELF', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(11, 'OL', 'Others', 'NONE', 1, '2026-06-15 09:37:40', '2026-06-15 09:37:40'),
(12, 'WL', 'Wellness Leave', 'SELF', 1, '2026-06-18 16:22:28', '2026-06-18 16:22:28'),
(13, 'PR', 'Personal Reason', 'CHARGED_TO_VSC', 1, '2026-06-29 10:36:36', '2026-06-29 10:36:36'),
(14, 'SLBT', 'Solo Parent Leave (Teaching)', 'SELF', 1, '2026-06-29 11:31:24', '2026-06-29 11:31:24'),
(15, 'MNT', 'Monetization', 'NONE', 1, '2026-06-30 11:13:27', '2026-06-30 11:13:27');

-- --------------------------------------------------------

--
-- Table structure for table `monthly_leave_credits`
--

CREATE TABLE `monthly_leave_credits` (
  `id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `leave_type_id` int(11) NOT NULL,
  `year` smallint(6) NOT NULL,
  `month` tinyint(4) NOT NULL,
  `amount` decimal(6,2) NOT NULL,
  `transaction_id` int(11) NOT NULL,
  `credited_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `positions`
--

CREATE TABLE `positions` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `type` enum('TEACHING','NON_TEACHING') NOT NULL,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Dumping data for table `positions`
--

INSERT INTO `positions` (`id`, `name`, `type`, `created_at`) VALUES
(1, 'Casual', 'NON_TEACHING', '2026-06-23 15:08:26'),
(2, 'Watchman', 'NON_TEACHING', '2026-06-23 15:08:26'),
(3, 'Security Guard', 'NON_TEACHING', '2026-06-23 15:08:26'),
(4, 'Chief Education Supervisor - SGOD', 'NON_TEACHING', '2026-06-23 15:08:26'),
(5, 'Chief Education Supervisor - CID', 'NON_TEACHING', '2026-06-23 15:08:26'),
(6, 'Public Schools District Supervisor', 'NON_TEACHING', '2026-06-23 15:08:26'),
(7, 'Education Program Supervisor', 'NON_TEACHING', '2026-06-23 15:08:26'),
(8, 'Senior Education Program Specialist', 'NON_TEACHING', '2026-06-23 15:08:26'),
(9, 'Education Program Specialist II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(10, 'Librarian II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(11, 'Guidance Counselor III', 'NON_TEACHING', '2026-06-23 15:08:26'),
(12, 'Guidance Counselor II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(13, 'Guidance Counselor I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(14, 'Registrar I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(15, 'Teacher-In-Charge', 'NON_TEACHING', '2026-06-23 15:08:26'),
(16, 'Head Teacher I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(17, 'Head Teacher II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(18, 'Head Teacher III', 'NON_TEACHING', '2026-06-23 15:08:26'),
(19, 'School Principal I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(20, 'School Principal II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(21, 'School Principal III', 'NON_TEACHING', '2026-06-23 15:08:26'),
(22, 'School Principal IV', 'NON_TEACHING', '2026-06-23 15:08:26'),
(23, 'Assistant School Principal II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(24, 'Information Technology Officer I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(25, 'Administrative Officer V', 'NON_TEACHING', '2026-06-23 15:08:26'),
(26, 'Administrative Officer IV', 'NON_TEACHING', '2026-06-23 15:08:26'),
(27, 'Project Development Officer II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(28, 'Nurse II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(29, 'Project Development Officer I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(30, 'Administrative Officer II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(31, 'Administrative Assistant III', 'NON_TEACHING', '2026-06-23 15:08:26'),
(32, 'Administrative Assistant II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(33, 'Administrative Assistant I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(34, 'Administrative Aide VI (Clerk III)', 'NON_TEACHING', '2026-06-23 15:08:26'),
(35, 'Administrative Aide IV (Driver)', 'NON_TEACHING', '2026-06-23 15:08:26'),
(36, 'Administrative Aide III (Driver)', 'NON_TEACHING', '2026-06-23 15:08:26'),
(37, 'Dentist II', 'NON_TEACHING', '2026-06-23 15:08:26'),
(38, 'Administrative Aide I', 'NON_TEACHING', '2026-06-23 15:08:26'),
(39, 'Administrative Aide IV (Clerk II)', 'NON_TEACHING', '2026-06-23 15:08:26'),
(40, 'Administrative Aide III (Clerk I)', 'NON_TEACHING', '2026-06-23 15:08:26'),
(41, 'Teacher I', 'TEACHING', '2026-06-23 15:08:26'),
(42, 'Teacher II', 'TEACHING', '2026-06-23 15:08:26'),
(43, 'Teacher III', 'TEACHING', '2026-06-23 15:08:26'),
(44, 'Teacher IV', 'TEACHING', '2026-06-23 15:08:26'),
(45, 'Teacher VI', 'TEACHING', '2026-06-23 15:08:26'),
(46, 'Teacher VII', 'TEACHING', '2026-06-23 15:08:26'),
(47, 'Master Teacher I', 'TEACHING', '2026-06-23 15:08:26'),
(48, 'Master Teacher II', 'TEACHING', '2026-06-23 15:08:26'),
(49, 'Master Teacher III', 'TEACHING', '2026-06-23 15:08:26'),
(50, 'Master Teacher IV', 'TEACHING', '2026-06-23 15:08:26'),
(51, 'Master Teacher V', 'TEACHING', '2026-06-23 15:08:26'),
(52, 'Special Education Teacher I', 'TEACHING', '2026-06-23 15:08:26'),
(53, 'Special Science Teacher I', 'TEACHING', '2026-06-23 15:08:26');

-- --------------------------------------------------------

--
-- Table structure for table `schools`
--

CREATE TABLE `schools` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Dumping data for table `schools`
--

INSERT INTO `schools` (`id`, `name`, `created_at`) VALUES
(1, 'Agudo E/S', '2026-06-23 14:59:21'),
(2, 'Alimatoc E/S', '2026-06-23 14:59:21'),
(3, 'Alingating E/S', '2026-06-23 14:59:21'),
(4, 'Aluyan E/S', '2026-06-23 14:59:21'),
(5, 'Andres Bonifacio E/S', '2026-06-23 14:59:21'),
(6, 'Balandra E/S', '2026-06-23 14:59:21'),
(7, 'Banquerohan NHS', '2026-06-23 14:59:21'),
(8, 'Bayabas E/S', '2026-06-23 14:59:21'),
(9, 'Burgos E/S', '2026-06-23 14:59:21'),
(10, 'Burgos NHS', '2026-06-23 14:59:21'),
(11, 'Cabahug E/S', '2026-06-23 14:59:21'),
(12, 'Cadiz East I E/S', '2026-06-23 14:59:21'),
(13, 'Cadiz East II E/S', '2026-06-23 14:59:21'),
(14, 'Cadiz Viejo E/S', '2026-06-23 14:59:21'),
(15, 'Cadiz Viejo NHS', '2026-06-23 14:59:21'),
(16, 'Cadiz West I E/S', '2026-06-23 14:59:21'),
(17, 'Cadiz West II E/S', '2026-06-23 14:59:21'),
(18, 'Caduha-an E/S', '2026-06-23 14:59:21'),
(19, 'Caduha-an NHS', '2026-06-23 14:59:21'),
(20, 'CNHS - A. Bonifacio Ext.', '2026-06-23 14:59:21'),
(21, 'CNHS - Luna Ext. HS', '2026-06-23 14:59:21'),
(22, 'CNHS - Tagbanon Ext. HS', '2026-06-23 14:59:21'),
(23, 'Cotcot E/S', '2026-06-23 14:59:21'),
(24, 'Daga E/S', '2026-06-23 14:59:21'),
(25, 'Don Luis Consing E/S', '2026-06-23 14:59:21'),
(26, 'Don R. Jesena E/S', '2026-06-23 14:59:21'),
(27, 'Dr. VF Gustilo E/S', '2026-06-23 14:59:21'),
(28, 'Dr. Vicente F. Gustilo Memorial NHS', '2026-06-23 14:59:21'),
(29, 'DVFGMNHS - Daga Ext. HS', '2026-06-23 14:59:21'),
(30, 'Egido Fernandez E/S', '2026-06-23 14:59:21'),
(31, 'Escolastica E/S', '2026-06-23 14:59:21'),
(32, 'F.M. Cabras E/S', '2026-06-23 14:59:21'),
(33, 'Floro Reboton E/S', '2026-06-23 14:59:21'),
(34, 'Gen A. Lacson E/S', '2026-06-23 14:59:21'),
(35, 'Hiyang-Hiyang E/S', '2026-06-23 14:59:21'),
(36, 'Hon P. Villena E/S', '2026-06-23 14:59:21'),
(37, 'Igcamalig E/S', '2026-06-23 14:59:21'),
(38, 'Jerusalem NHS', '2026-06-23 14:59:21'),
(39, 'Luis Uy Chiat E/S', '2026-06-23 14:59:21'),
(40, 'M.J Escalante E/S', '2026-06-23 14:59:21'),
(41, 'M.V. Gamboa E/S', '2026-06-23 14:59:21'),
(42, 'Mabini E/S', '2026-06-23 14:59:21'),
(43, 'Mabini NHS', '2026-06-23 14:59:21'),
(44, 'Manara E/S', '2026-06-23 14:59:21'),
(45, 'Martin A. Quiachon E/S', '2026-06-23 14:59:21'),
(46, 'MNHS - Alimatoc Ext', '2026-06-23 14:59:21'),
(47, 'Paniqui-on E/S', '2026-06-23 14:59:21'),
(48, 'Pedro E. Ramos E/S', '2026-06-23 14:59:21'),
(49, 'Pedro Pitogo E/S', '2026-06-23 14:59:21'),
(50, 'Progreso E/S', '2026-06-23 14:59:21'),
(51, 'San Andres E/S', '2026-06-23 14:59:21'),
(52, 'San Rafael E/S', '2026-06-23 14:59:21'),
(53, 'Sangay E/S', '2026-06-23 14:59:21'),
(54, 'Severino Escaro E/S', '2026-06-23 14:59:21'),
(55, 'Sewahon E/S', '2026-06-23 14:59:21'),
(56, 'Sicaba NHS', '2026-06-23 14:59:21'),
(57, 'Sombito E/S', '2026-06-23 14:59:21'),
(58, 'SPED HS', '2026-06-23 14:59:21'),
(59, 'SPED Training Center', '2026-06-23 14:59:21'),
(60, 'Tagbanon E/S', '2026-06-23 14:59:21'),
(61, 'Tiglawigan E/S', '2026-06-23 14:59:21'),
(62, 'Tiglawigan NHS', '2026-06-23 14:59:21'),
(63, 'TNHS - Magsaysay Ext. HS', '2026-06-23 14:59:21'),
(64, 'Tres Andanas E/S', '2026-06-23 14:59:21'),
(65, 'Vicente Patricio E/S', '2026-06-23 14:59:21'),
(66, 'Villacin E/S', '2026-06-23 14:59:21'),
(67, 'Villacin NHS', '2026-06-23 14:59:21'),
(68, 'VNHS - Sewahon Ext.', '2026-06-23 14:59:21'),
(69, 'Yee-On E/S', '2026-06-23 14:59:21');

-- --------------------------------------------------------

--
-- Table structure for table `service_credit_applications`
--

CREATE TABLE `service_credit_applications` (
  `id` int(11) NOT NULL,
  `application_number` varchar(20) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `special_order_id` int(11) NOT NULL,
  `type` enum('CTO','VSC') NOT NULL,
  `hours_rendered` decimal(6,2) NOT NULL,
  `balance_earned` decimal(6,2) NOT NULL,
  `valid_until` date DEFAULT NULL,
  `date_filed` date NOT NULL,
  `date_of_upload` date DEFAULT NULL,
  `uploaded_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `service_credit_dates`
--

CREATE TABLE `service_credit_dates` (
  `id` int(11) NOT NULL,
  `service_credit_application_id` int(11) NOT NULL,
  `date` date NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `special_orders`
--

CREATE TABLE `special_orders` (
  `id` int(11) NOT NULL,
  `special_order` varchar(100) NOT NULL,
  `activity_name` varchar(255) NOT NULL,
  `reference` varchar(100) DEFAULT NULL,
  `date_of_activity` date NOT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `undertime_tardiness_deductions`
--

CREATE TABLE `undertime_tardiness_deductions` (
  `id` int(11) NOT NULL,
  `application_number` varchar(20) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `undertime_points` decimal(8,4) NOT NULL DEFAULT 0.0000,
  `tardiness_points` decimal(8,4) NOT NULL DEFAULT 0.0000,
  `total_points` decimal(8,4) NOT NULL,
  `vl_deducted` decimal(8,4) NOT NULL,
  `deduction_date` date NOT NULL,
  `remarks` text DEFAULT NULL,
  `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('ADMIN','DIVISION_PERSONNEL','TEACHING_PERSONNEL','PAYROLL') NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `last_login_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `employee_id`, `username`, `password_hash`, `role`, `is_active`, `last_login_at`, `created_at`, `updated_at`) VALUES
(1, 1, 'admin', '$2b$12$cEAZwqfMnTE2iW6oL2Q/EuDEZ0cjd9futfsH9MXDKwqhmrpyp3nRm', 'ADMIN', 1, '2026-07-06 14:48:59', '2026-06-18 09:50:16', '2026-07-06 14:48:59');

-- --------------------------------------------------------

--
-- Table structure for table `vsc_deduction_log`
--

CREATE TABLE `vsc_deduction_log` (
  `id` int(11) NOT NULL,
  `leave_application_id` int(11) NOT NULL,
  `credit_pool` enum('OLD','NEW') NOT NULL,
  `credit_balance_id` int(11) NOT NULL,
  `amount_deducted` decimal(10,2) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `vsc_new_credit_balances`
--

CREATE TABLE `vsc_new_credit_balances` (
  `id` int(11) NOT NULL,
  `service_credit_application_id` int(11) DEFAULT NULL,
  `employee_id` int(11) NOT NULL,
  `original_balance` decimal(10,2) NOT NULL,
  `remaining_balance` decimal(10,2) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `remarks` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

-- --------------------------------------------------------

--
-- Table structure for table `vsc_old_credit_balances`
--

CREATE TABLE `vsc_old_credit_balances` (
  `id` int(11) NOT NULL,
  `service_credit_application_id` int(11) DEFAULT NULL,
  `employee_id` int(11) NOT NULL,
  `original_balance` decimal(10,2) NOT NULL,
  `remaining_balance` decimal(10,2) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `remarks` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `calendar_events`
--
ALTER TABLE `calendar_events`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `date` (`date`),
  ADD KEY `created_by` (`created_by`);

--
-- Indexes for table `cto_credit_balances`
--
ALTER TABLE `cto_credit_balances`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_sca` (`service_credit_application_id`),
  ADD KEY `employee_id` (`employee_id`);

--
-- Indexes for table `cto_deduction_log`
--
ALTER TABLE `cto_deduction_log`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cto_credit_balance_id` (`cto_credit_balance_id`),
  ADD KEY `leave_application_id` (`leave_application_id`);

--
-- Indexes for table `employees`
--
ALTER TABLE `employees`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `leave_card_number` (`leave_card_number`),
  ADD UNIQUE KEY `employee_number` (`employee_number`),
  ADD UNIQUE KEY `email` (`email`);

--
-- Indexes for table `employee_leave_balances`
--
ALTER TABLE `employee_leave_balances`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_employee_leave_balance` (`employee_id`,`leave_type_id`),
  ADD KEY `fk_balance_leave_type` (`leave_type_id`);

--
-- Indexes for table `employee_type_conversions`
--
ALTER TABLE `employee_type_conversions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `conversion_number` (`conversion_number`),
  ADD KEY `fk_etc_employee` (`employee_id`),
  ADD KEY `fk_etc_created_by` (`created_by`);

--
-- Indexes for table `leave_applications`
--
ALTER TABLE `leave_applications`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `application_number` (`application_number`),
  ADD KEY `fk_application_employee` (`employee_id`),
  ADD KEY `fk_application_leave_type` (`leave_type_id`),
  ADD KEY `fk_app_status_updated_by` (`status_updated_by`);

--
-- Indexes for table `leave_application_dates`
--
ALTER TABLE `leave_application_dates`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_lad_application` (`leave_application_id`);

--
-- Indexes for table `leave_approvals`
--
ALTER TABLE `leave_approvals`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_approval_application` (`leave_application_id`),
  ADD KEY `fk_approval_approver` (`approver_id`);

--
-- Indexes for table `leave_credit_transactions`
--
ALTER TABLE `leave_credit_transactions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `transaction_number` (`transaction_number`),
  ADD KEY `fk_transaction_employee` (`employee_id`),
  ADD KEY `fk_transaction_leave_type` (`leave_type_id`);

--
-- Indexes for table `leave_refunded_dates`
--
ALTER TABLE `leave_refunded_dates`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_lrd_app` (`leave_application_id`),
  ADD KEY `fk_lrd_event` (`calendar_event_id`),
  ADD KEY `fk_lrd_leave_type` (`credited_leave_type_id`);

--
-- Indexes for table `leave_types`
--
ALTER TABLE `leave_types`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `code` (`code`);

--
-- Indexes for table `monthly_leave_credits`
--
ALTER TABLE `monthly_leave_credits`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_monthly_credit` (`employee_id`,`leave_type_id`,`year`,`month`),
  ADD KEY `fk_mlc_leave_type` (`leave_type_id`),
  ADD KEY `fk_mlc_transaction` (`transaction_id`);

--
-- Indexes for table `positions`
--
ALTER TABLE `positions`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `schools`
--
ALTER TABLE `schools`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `service_credit_applications`
--
ALTER TABLE `service_credit_applications`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `application_number` (`application_number`),
  ADD KEY `fk_sc_employee` (`employee_id`),
  ADD KEY `fk_sc_special_order` (`special_order_id`),
  ADD KEY `fk_sc_uploaded_by` (`uploaded_by`);

--
-- Indexes for table `service_credit_dates`
--
ALTER TABLE `service_credit_dates`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_sc_dates_application` (`service_credit_application_id`);

--
-- Indexes for table `special_orders`
--
ALTER TABLE `special_orders`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `special_order` (`special_order`);

--
-- Indexes for table `undertime_tardiness_deductions`
--
ALTER TABLE `undertime_tardiness_deductions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `application_number` (`application_number`),
  ADD KEY `fk_utd_employee` (`employee_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `employee_id` (`employee_id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `vsc_deduction_log`
--
ALTER TABLE `vsc_deduction_log`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_vsc_log_leave_app` (`leave_application_id`);

--
-- Indexes for table `vsc_new_credit_balances`
--
ALTER TABLE `vsc_new_credit_balances`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_vsc_new_sca` (`service_credit_application_id`),
  ADD KEY `fk_vsc_new_employee` (`employee_id`);

--
-- Indexes for table `vsc_old_credit_balances`
--
ALTER TABLE `vsc_old_credit_balances`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_vsc_old_sca` (`service_credit_application_id`),
  ADD KEY `fk_vsc_old_employee` (`employee_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `calendar_events`
--
ALTER TABLE `calendar_events`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `cto_credit_balances`
--
ALTER TABLE `cto_credit_balances`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `cto_deduction_log`
--
ALTER TABLE `cto_deduction_log`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `employees`
--
ALTER TABLE `employees`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `employee_leave_balances`
--
ALTER TABLE `employee_leave_balances`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `employee_type_conversions`
--
ALTER TABLE `employee_type_conversions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `leave_applications`
--
ALTER TABLE `leave_applications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `leave_application_dates`
--
ALTER TABLE `leave_application_dates`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `leave_approvals`
--
ALTER TABLE `leave_approvals`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `leave_credit_transactions`
--
ALTER TABLE `leave_credit_transactions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `leave_refunded_dates`
--
ALTER TABLE `leave_refunded_dates`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `leave_types`
--
ALTER TABLE `leave_types`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=16;

--
-- AUTO_INCREMENT for table `monthly_leave_credits`
--
ALTER TABLE `monthly_leave_credits`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `positions`
--
ALTER TABLE `positions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=54;

--
-- AUTO_INCREMENT for table `schools`
--
ALTER TABLE `schools`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=70;

--
-- AUTO_INCREMENT for table `service_credit_applications`
--
ALTER TABLE `service_credit_applications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `service_credit_dates`
--
ALTER TABLE `service_credit_dates`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `special_orders`
--
ALTER TABLE `special_orders`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `undertime_tardiness_deductions`
--
ALTER TABLE `undertime_tardiness_deductions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `vsc_deduction_log`
--
ALTER TABLE `vsc_deduction_log`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `vsc_new_credit_balances`
--
ALTER TABLE `vsc_new_credit_balances`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `vsc_old_credit_balances`
--
ALTER TABLE `vsc_old_credit_balances`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `calendar_events`
--
ALTER TABLE `calendar_events`
  ADD CONSTRAINT `calendar_events_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`);

--
-- Constraints for table `cto_credit_balances`
--
ALTER TABLE `cto_credit_balances`
  ADD CONSTRAINT `cto_credit_balances_ibfk_1` FOREIGN KEY (`service_credit_application_id`) REFERENCES `service_credit_applications` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `cto_credit_balances_ibfk_2` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `cto_deduction_log`
--
ALTER TABLE `cto_deduction_log`
  ADD CONSTRAINT `cto_deduction_log_ibfk_1` FOREIGN KEY (`cto_credit_balance_id`) REFERENCES `cto_credit_balances` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `cto_deduction_log_ibfk_2` FOREIGN KEY (`leave_application_id`) REFERENCES `leave_applications` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `employee_leave_balances`
--
ALTER TABLE `employee_leave_balances`
  ADD CONSTRAINT `fk_balance_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_balance_leave_type` FOREIGN KEY (`leave_type_id`) REFERENCES `leave_types` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `employee_type_conversions`
--
ALTER TABLE `employee_type_conversions`
  ADD CONSTRAINT `fk_etc_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_etc_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `leave_applications`
--
ALTER TABLE `leave_applications`
  ADD CONSTRAINT `fk_app_status_updated_by` FOREIGN KEY (`status_updated_by`) REFERENCES `employees` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_application_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_application_leave_type` FOREIGN KEY (`leave_type_id`) REFERENCES `leave_types` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `leave_application_dates`
--
ALTER TABLE `leave_application_dates`
  ADD CONSTRAINT `fk_lad_application` FOREIGN KEY (`leave_application_id`) REFERENCES `leave_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `leave_approvals`
--
ALTER TABLE `leave_approvals`
  ADD CONSTRAINT `fk_approval_application` FOREIGN KEY (`leave_application_id`) REFERENCES `leave_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_approval_approver` FOREIGN KEY (`approver_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `leave_credit_transactions`
--
ALTER TABLE `leave_credit_transactions`
  ADD CONSTRAINT `fk_transaction_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_transaction_leave_type` FOREIGN KEY (`leave_type_id`) REFERENCES `leave_types` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `leave_refunded_dates`
--
ALTER TABLE `leave_refunded_dates`
  ADD CONSTRAINT `fk_lrd_app` FOREIGN KEY (`leave_application_id`) REFERENCES `leave_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_lrd_event` FOREIGN KEY (`calendar_event_id`) REFERENCES `calendar_events` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_lrd_leave_type` FOREIGN KEY (`credited_leave_type_id`) REFERENCES `leave_types` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `monthly_leave_credits`
--
ALTER TABLE `monthly_leave_credits`
  ADD CONSTRAINT `fk_mlc_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_mlc_leave_type` FOREIGN KEY (`leave_type_id`) REFERENCES `leave_types` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_mlc_transaction` FOREIGN KEY (`transaction_id`) REFERENCES `leave_credit_transactions` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `service_credit_applications`
--
ALTER TABLE `service_credit_applications`
  ADD CONSTRAINT `fk_sc_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_sc_special_order` FOREIGN KEY (`special_order_id`) REFERENCES `special_orders` (`id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_sc_uploaded_by` FOREIGN KEY (`uploaded_by`) REFERENCES `employees` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Constraints for table `service_credit_dates`
--
ALTER TABLE `service_credit_dates`
  ADD CONSTRAINT `fk_sc_dates_application` FOREIGN KEY (`service_credit_application_id`) REFERENCES `service_credit_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `undertime_tardiness_deductions`
--
ALTER TABLE `undertime_tardiness_deductions`
  ADD CONSTRAINT `fk_utd_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `users`
--
ALTER TABLE `users`
  ADD CONSTRAINT `fk_user_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `vsc_deduction_log`
--
ALTER TABLE `vsc_deduction_log`
  ADD CONSTRAINT `fk_vsc_log_leave_app` FOREIGN KEY (`leave_application_id`) REFERENCES `leave_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `vsc_new_credit_balances`
--
ALTER TABLE `vsc_new_credit_balances`
  ADD CONSTRAINT `fk_vsc_new_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_vsc_new_sca` FOREIGN KEY (`service_credit_application_id`) REFERENCES `service_credit_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `vsc_old_credit_balances`
--
ALTER TABLE `vsc_old_credit_balances`
  ADD CONSTRAINT `fk_vsc_old_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_vsc_old_sca` FOREIGN KEY (`service_credit_application_id`) REFERENCES `service_credit_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
