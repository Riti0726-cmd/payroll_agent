-- =============================================================
-- Step 2: Create Tables
-- =============================================================

USE WAREHOUSE PAYROLL_WH;
USE DATABASE  PAYROLL_DB;
USE SCHEMA    PAYROLL_SCHEMA;

-- -----------------------------------------------------------
-- 2a. Employee Payroll — earnings, taxes, deductions, net pay
-- -----------------------------------------------------------
CREATE OR REPLACE TABLE sv_employee_payroll (
    payroll_id        VARCHAR(36)   DEFAULT UUID_STRING() PRIMARY KEY,
    client_id         VARCHAR(20)   NOT NULL,
    employee_id       VARCHAR(20)   NOT NULL,
    employee_name     VARCHAR(120),
    pay_period        VARCHAR(10)   NOT NULL,           -- YYYY-MM
    pay_date          DATE,
    pay_frequency     VARCHAR(20)   DEFAULT 'bi-weekly',
    regular_hours     DECIMAL(8,2)  DEFAULT 0,
    overtime_hours    DECIMAL(8,2)  DEFAULT 0,
    hourly_rate       DECIMAL(10,2),
    regular_pay       DECIMAL(12,2) DEFAULT 0,
    overtime_pay      DECIMAL(12,2) DEFAULT 0,
    gross_pay         DECIMAL(12,2) DEFAULT 0,
    federal_tax       DECIMAL(10,2) DEFAULT 0,
    state_tax         DECIMAL(10,2) DEFAULT 0,
    social_security   DECIMAL(10,2) DEFAULT 0,
    medicare          DECIMAL(10,2) DEFAULT 0,
    total_deductions  DECIMAL(12,2) DEFAULT 0,
    net_pay           DECIMAL(12,2) DEFAULT 0,
    created_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- -----------------------------------------------------------
-- 2b. HR Workforce — identity, employment, comp, direct deposit
-- -----------------------------------------------------------
CREATE OR REPLACE TABLE sv_hr_workforce (
    employee_id       VARCHAR(20)   PRIMARY KEY,
    client_id         VARCHAR(20)   NOT NULL,
    first_name        VARCHAR(60),
    last_name         VARCHAR(60),
    full_name         VARCHAR(120),
    email             VARCHAR(120),
    department        VARCHAR(60),
    position_title    VARCHAR(80),
    hire_date         DATE,
    termination_date  DATE,
    status_class      VARCHAR(20)   DEFAULT 'active',
    pay_type          VARCHAR(20)   DEFAULT 'hourly',
    hourly_rate       DECIMAL(10,2),
    annual_salary     DECIMAL(12,2),
    direct_deposit_bank   VARCHAR(80),
    direct_deposit_last4  VARCHAR(4),
    w4_filing_status      VARCHAR(30),
    w4_allowances         INT         DEFAULT 0,
    address_line1     VARCHAR(120),
    address_city      VARCHAR(60),
    address_state     VARCHAR(2),
    address_zip       VARCHAR(10),
    system_target     VARCHAR(20)   DEFAULT 'prismhr',
    updated_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- -----------------------------------------------------------
-- 2c. Employee Benefits — medical, dental, 401k, etc.
-- -----------------------------------------------------------
CREATE OR REPLACE TABLE sv_employee_benefits (
    benefit_id        VARCHAR(36)   DEFAULT UUID_STRING() PRIMARY KEY,
    employee_id       VARCHAR(20)   NOT NULL,
    client_id         VARCHAR(20)   NOT NULL,
    benefit_type      VARCHAR(40),
    plan_name         VARCHAR(80),
    employee_contrib  DECIMAL(10,2) DEFAULT 0,
    employer_contrib  DECIMAL(10,2) DEFAULT 0,
    effective_date    DATE,
    end_date          DATE,
    status            VARCHAR(20)   DEFAULT 'active'
);

-- -----------------------------------------------------------
-- 2d. User Credentials — specialist auth & client access
-- -----------------------------------------------------------
CREATE OR REPLACE TABLE sv_user_credentials (
    user_id           VARCHAR(36)   DEFAULT UUID_STRING() PRIMARY KEY,
    username          VARCHAR(80)   NOT NULL UNIQUE,
    email             VARCHAR(120)  NOT NULL UNIQUE,
    role              VARCHAR(30)   DEFAULT 'specialist',
    client_ids        VARIANT,
    is_active         BOOLEAN       DEFAULT TRUE,
    last_login        TIMESTAMP_NTZ,
    created_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

