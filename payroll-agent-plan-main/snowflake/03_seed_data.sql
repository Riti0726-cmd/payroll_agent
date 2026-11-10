-- =============================================================
-- Step 3: Seed Sample Data
-- =============================================================

USE WAREHOUSE PAYROLL_WH;
USE DATABASE  PAYROLL_DB;
USE SCHEMA    PAYROLL_SCHEMA;

-- -----------------------------------------------------------
-- 3a. Workforce — 5 employees across 2 clients
-- -----------------------------------------------------------
INSERT INTO sv_hr_workforce
  (employee_id, client_id, first_name, last_name, full_name, email,
   department, position_title, hire_date, termination_date, status_class,
   pay_type, hourly_rate, annual_salary,
   direct_deposit_bank, direct_deposit_last4,
   w4_filing_status, w4_allowances,
   address_line1, address_city, address_state, address_zip,
   system_target, updated_at)
VALUES
  ('EMP-1001','CLT-200','Jane','Doe','Jane Doe','jane.doe@acme.com',
   'Finance','Sr Accountant','2022-03-15',NULL,'active',
   'salary',NULL,85000.00,
   'Chase','4455','single',1,
   '100 Main St','Denver','CO','80202','prismhr',CURRENT_TIMESTAMP()),

  ('EMP-1002','CLT-200','John','Smith','John Smith','john.smith@acme.com',
   'Warehouse','Forklift Operator','2021-06-01',NULL,'active',
   'hourly',22.50,NULL,
   'Wells Fargo','7788','married',2,
   '200 Oak Ave','Denver','CO','80203','prismhr',CURRENT_TIMESTAMP()),

  ('EMP-1003','CLT-300','Maria','Garcia','Maria Garcia','maria.garcia@globex.com',
   'Engineering','Software Engineer','2023-01-10',NULL,'active',
   'salary',NULL,110000.00,
   'BofA','9900','single',1,
   '500 Tech Blvd','Austin','TX','78701','isolved',CURRENT_TIMESTAMP()),

  ('EMP-1004','CLT-300','Robert','Chen','Robert Chen','robert.chen@globex.com',
   'Engineering','QA Lead','2020-09-22',NULL,'active',
   'salary',NULL,95000.00,
   'Citibank','3344','married',3,
   '42 Pine Rd','Austin','TX','78702','isolved',CURRENT_TIMESTAMP()),

  ('EMP-1005','CLT-200','Alice','Johnson','Alice Johnson','alice.j@acme.com',
   'HR','HR Coordinator','2024-02-01',NULL,'active',
   'hourly',28.00,NULL,
   'Chase','1122','single',1,
   '350 Elm St','Denver','CO','80204','prismhr',CURRENT_TIMESTAMP());

-- -----------------------------------------------------------
-- 3b. Payroll — 2 pay periods (Jul & Aug 2026)
-- -----------------------------------------------------------
INSERT INTO sv_employee_payroll
  (client_id, employee_id, employee_name, pay_period, pay_date, pay_frequency,
   regular_hours, overtime_hours, hourly_rate,
   regular_pay, overtime_pay, gross_pay,
   federal_tax, state_tax, social_security, medicare,
   total_deductions, net_pay)
VALUES
  -- Jane Doe (salary, semi-monthly)
  ('CLT-200','EMP-1001','Jane Doe','2026-07','2026-07-31','semi-monthly',
    80, 0, NULL, 3541.67, 0, 3541.67,
    531.25, 177.08, 219.58, 51.35, 979.26, 2562.41),
  ('CLT-200','EMP-1001','Jane Doe','2026-08','2026-08-31','semi-monthly',
    80, 0, NULL, 3541.67, 0, 3541.67,
    531.25, 177.08, 219.58, 51.35, 979.26, 2562.41),

  -- John Smith (hourly, bi-weekly)
  ('CLT-200','EMP-1002','John Smith','2026-07','2026-07-15','bi-weekly',
    80, 8, 22.50, 1800.00, 270.00, 2070.00,
    310.50, 103.50, 128.34, 30.02, 572.36, 1497.64),
  ('CLT-200','EMP-1002','John Smith','2026-08','2026-08-15','bi-weekly',
    80, 12, 22.50, 1800.00, 405.00, 2205.00,
    330.75, 110.25, 136.71, 31.97, 609.68, 1595.32),

  -- Maria Garcia (salary, semi-monthly)
  ('CLT-300','EMP-1003','Maria Garcia','2026-08','2026-08-31','semi-monthly',
    80, 0, NULL, 4583.33, 0, 4583.33,
    687.50, 229.17, 284.17, 66.46, 1267.30, 3316.03),

  -- Robert Chen (salary, semi-monthly)
  ('CLT-300','EMP-1004','Robert Chen','2026-08','2026-08-31','semi-monthly',
    80, 0, NULL, 3958.33, 0, 3958.33,
    593.75, 197.92, 245.42, 57.40, 1094.49, 2863.84),

  -- Alice Johnson (hourly, bi-weekly)
  ('CLT-200','EMP-1005','Alice Johnson','2026-08','2026-08-15','bi-weekly',
    80, 4, 28.00, 2240.00, 168.00, 2408.00,
    361.20, 120.40, 149.30, 34.92, 665.82, 1742.18);

-- -----------------------------------------------------------
-- 3c. Benefits
-- -----------------------------------------------------------
INSERT INTO sv_employee_benefits
  (employee_id, client_id, benefit_type, plan_name,
   employee_contrib, employer_contrib, effective_date, status)
VALUES
  ('EMP-1001','CLT-200','medical','PPO Gold',      250.00, 500.00, '2022-04-01','active'),
  ('EMP-1001','CLT-200','401k',   'Safe Harbor',   340.00, 170.00, '2022-04-01','active'),
  ('EMP-1002','CLT-200','medical','HMO Basic',     150.00, 400.00, '2021-07-01','active'),
  ('EMP-1003','CLT-300','medical','PPO Platinum',   300.00, 600.00, '2023-02-01','active'),
  ('EMP-1003','CLT-300','401k',   'Standard',      460.00, 230.00, '2023-02-01','active'),
  ('EMP-1004','CLT-300','dental', 'Delta Dental',   45.00,  45.00, '2020-10-01','active');

-- -----------------------------------------------------------
-- 3d. User Credentials — specialists authorized per client
-- -----------------------------------------------------------
INSERT INTO sv_user_credentials
  (username, email, role, client_ids, is_active)
VALUES
  ('specialist1', 'specialist1@payroll.internal', 'specialist',
   PARSE_JSON('["CLT-200","CLT-300"]'), TRUE),
  ('admin1', 'admin@payroll.internal', 'admin',
   PARSE_JSON('["CLT-200","CLT-300"]'), TRUE),
  ('viewer1', 'viewer@payroll.internal', 'viewer',
   PARSE_JSON('["CLT-200"]'), TRUE);
