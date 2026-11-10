-- =============================================================
-- Step 5: OAuth Security Integration for MCP Agent Access
-- =============================================================

USE ROLE ACCOUNTADMIN;

-- 5a. Create OAuth integration
CREATE OR REPLACE SECURITY INTEGRATION payroll_agent_oauth
  TYPE = OAUTH
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
  OAUTH_REDIRECT_URI = 'http://localhost:3336/callback'
  ENABLED = TRUE;

-- 5b. Retrieve client_id and client_secret
-- Run this and note OAUTH_CLIENT_ID + OAUTH_CLIENT_SECRET from the output.
-- These go into mcp_config.json --static-oauth-client-info.
DESCRIBE SECURITY INTEGRATION payroll_agent_oauth;

-- 5c. Create a minimal-privilege role for the agent
CREATE ROLE IF NOT EXISTS PAYROLL_AGENT_ROLE;

GRANT USAGE   ON WAREHOUSE PAYROLL_WH                          TO ROLE PAYROLL_AGENT_ROLE;
GRANT USAGE   ON DATABASE  PAYROLL_DB                          TO ROLE PAYROLL_AGENT_ROLE;
GRANT USAGE   ON SCHEMA    PAYROLL_DB.PAYROLL_SCHEMA           TO ROLE PAYROLL_AGENT_ROLE;
GRANT SELECT  ON ALL TABLES IN SCHEMA PAYROLL_DB.PAYROLL_SCHEMA TO ROLE PAYROLL_AGENT_ROLE;

-- Future tables auto-granted
GRANT SELECT ON FUTURE TABLES IN SCHEMA PAYROLL_DB.PAYROLL_SCHEMA TO ROLE PAYROLL_AGENT_ROLE;

-- 5d. Assign role to service user (replace with your actual user)
-- GRANT ROLE PAYROLL_AGENT_ROLE TO USER your_service_user;

-- For PAT (Programmatic Access Token) auth instead of OAuth:
-- 1. Set SNOWFLAKE_MCP_AUTH=pat in .env
-- 2. Generate a PAT in Snowflake UI: User Menu → My Profile → Programmatic Access Tokens
-- 3. Set SNOWFLAKE_PAT=<token> in .env
