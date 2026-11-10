-- =============================================================
-- Step 4: Upload Semantic Models & Create Cortex Analyst MCP Server
-- =============================================================

USE ROLE SYSADMIN;
USE WAREHOUSE PAYROLL_WH;
USE DATABASE  PAYROLL_DB;
USE SCHEMA    PAYROLL_SCHEMA;

-- =============================================================
-- 4a. Create internal stage for semantic-model YAML files
-- =============================================================
CREATE STAGE IF NOT EXISTS SEMANTIC_MODELS
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'Cortex Analyst semantic model definitions';

-- =============================================================
-- 4b. Upload YAML files
-- =============================================================
-- Option A: SnowSQL CLI (run from your project root):
--
--   snowsql -a YOUR_ACCOUNT -u YOUR_USER -d PAYROLL_DB -s PAYROLL_SCHEMA
--
--   PUT file://snowflake/semantic_models/sv_employee_payroll.yaml  @SEMANTIC_MODELS AUTO_COMPRESS=FALSE;
--   PUT file://snowflake/semantic_models/sv_hr_workforce.yaml     @SEMANTIC_MODELS AUTO_COMPRESS=FALSE;
--   PUT file://snowflake/semantic_models/sv_employee_benefits.yaml @SEMANTIC_MODELS AUTO_COMPRESS=FALSE;
--
-- Option B: Snowflake UI drag-and-drop:
--   Data → PAYROLL_DB → PAYROLL_SCHEMA → Stages → SEMANTIC_MODELS → Upload Files

-- =============================================================
-- 4c. Verify uploads (run after uploading)
-- =============================================================
LIST @SEMANTIC_MODELS;

-- =============================================================
-- 4d. CREATE THE MCP SERVER (this is the actual creation step)
-- =============================================================
-- This creates the Cortex Analyst MCP Server that exposes two tools:
--   1. Cortex Analyst tool  — converts natural-language → SQL via semantic models
--   2. sql_query_executor   — executes the generated SQL and returns rows

CREATE OR REPLACE CORTEX MCP SERVER PAYROLL_MCP_SERVER
  WAREHOUSE = PAYROLL_WH
  SEMANTIC_MODEL_FILES = (
    '@SEMANTIC_MODELS/sv_employee_payroll.yaml',
    '@SEMANTIC_MODELS/sv_hr_workforce.yaml',
    '@SEMANTIC_MODELS/sv_employee_benefits.yaml'
  );

-- If the above DDL gives a syntax error, your Snowflake version may need
-- the newer syntax. Try this alternative:
--
-- CREATE OR REPLACE CORTEX ANALYST MCP SERVER PAYROLL_MCP_SERVER
--   WAREHOUSE = PAYROLL_WH
--   SEMANTIC_MODEL = '@SEMANTIC_MODELS/sv_employee_payroll.yaml'
--   SEMANTIC_MODEL = '@SEMANTIC_MODELS/sv_hr_workforce.yaml'
--   SEMANTIC_MODEL = '@SEMANTIC_MODELS/sv_employee_benefits.yaml';
--
-- If NEITHER works, use the Snowflake UI wizard instead:
--   AI & ML → Cortex Analyst → Create MCP Server
--   (fill in: Name=PAYROLL_MCP_SERVER, DB=PAYROLL_DB, Schema=PAYROLL_SCHEMA,
--    Warehouse=PAYROLL_WH, then add the 3 semantic model stage paths above)

-- =============================================================
-- 4e. Verify the MCP server was created
-- =============================================================
SHOW CORTEX MCP SERVERS IN SCHEMA PAYROLL_DB.PAYROLL_SCHEMA;

-- =============================================================
-- 4f. Get your MCP endpoint URL
-- =============================================================
-- After creation, your MCP URL follows this pattern:
-- https://<ACCOUNT>.snowflakecomputing.com/api/v2/databases/PAYROLL_DB/schemas/PAYROLL_SCHEMA/mcp-servers/PAYROLL_MCP_SERVER
--
-- To find your account identifier, run:
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS account_identifier;
-- Then your full URL is:
-- https://<account_identifier>.snowflakecomputing.com/api/v2/databases/PAYROLL_DB/schemas/PAYROLL_SCHEMA/mcp-servers/PAYROLL_MCP_SERVER
