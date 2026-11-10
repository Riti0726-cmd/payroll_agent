

USE ROLE SYSADMIN;

-- 1a. Warehouse — XS is sufficient for agent queries
CREATE WAREHOUSE IF NOT EXISTS PAYROLL_WH
  WAREHOUSE_SIZE = 'X-SMALL'
  AUTO_SUSPEND   = 120
  AUTO_RESUME    = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Payroll Agent – QA & Changelist Cortex Analyst queries';

-- 1b. Database
CREATE DATABASE IF NOT EXISTS PAYROLL_DB
  COMMENT = 'Payroll Agent data: employees, payroll, benefits, credentials';

-- 1c. Schema
CREATE SCHEMA IF NOT EXISTS PAYROLL_DB.PAYROLL_SCHEMA
  COMMENT = 'Primary schema for payroll semantic views';

-- Activate context
USE WAREHOUSE PAYROLL_WH;
USE DATABASE  PAYROLL_DB;
USE SCHEMA    PAYROLL_SCHEMA;

