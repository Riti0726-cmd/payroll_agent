# Snowflake Semantic Views vs Tables Guide

## Why did emails show "Clarification needed"?
When the agent processed emails, the validation node invoked the Cortex Analyst MCP tool (`hr_workforce_analyst`).
Snowflake returned:
```
MCP error calling tool hr_workforce_analyst: Error occurred while calling Cortex Analyst: SQL compilation error:
Semantic View 'PAYROLL_DB.PAYROLL_SCHEMA.SV_HR_WORKFORCE' does not exist or not authorized.{2}
```

### Root Cause
1. **Tables vs Semantic Views:**
   In Step 2 (`02_tables.sql`), tables were created with names `SV_HR_WORKFORCE`, `SV_EMPLOYEE_PAYROLL`, and `SV_EMPLOYEE_BENEFITS`.
   However, Snowflake's native Cortex MCP server (`CORTEX_ANALYST_MESSAGE`) expects the `identifier` to be a **Semantic View** (`CREATE SEMANTIC VIEW`), not a physical `TABLE`. Because tables and semantic views share the same schema namespace in Snowflake, a table named `SV_HR_WORKFORCE` is not recognized as a Semantic View.
2. **Strict Prompt Constraint:**
   The agent prompts (`prompts.py`) strictly instructed the LLM: `"Do not write or modify SQL yourself. Call sql_query_executor with that EXACT Analyst SQL."` When Analyst failed with the missing semantic view error, the agent was forbidden from querying the tables directly, leading to `status="needs_clarification"` and drafting a "Clarification Needed" email.

## What has been fixed in the Python Agent
1. `src/payroll_specialist/prompts.py`:
   - Updated `VALIDATION_INSTRUCTIONS`, `QA_INSTRUCTIONS`, and `CHANGELIST_INSTRUCTIONS` to allow the agent to immediately fallback to querying `PAYROLL_DB.PAYROLL_SCHEMA.SV_HR_WORKFORCE`, `SV_EMPLOYEE_PAYROLL`, and `SV_EMPLOYEE_BENEFITS` directly via `sql_query_executor` if Cortex Analyst encounters a semantic view error or is unavailable.
2. `src/payroll_specialist/nodes/validation.py`:
   - Validation node now instructs the agent to query `SV_HR_WORKFORCE` directly via `sql_query_executor` if Analyst errors.
3. `src/payroll_specialist/nodes/qa.py` & `nodes/changelist.py`:
   - QA and Changelist nodes now query the relevant tables directly via `sql_query_executor` when Analyst errors.

## (Optional) Creating Native Snowflake Semantic Views
If you wish to use native Snowflake Cortex Analyst semantic views rather than direct table querying:
1. Rename physical tables:
   ```sql
   USE DATABASE PAYROLL_DB;
   USE SCHEMA PAYROLL_SCHEMA;
   ALTER TABLE SV_HR_WORKFORCE RENAME TO T_HR_WORKFORCE;
   ALTER TABLE SV_EMPLOYEE_PAYROLL RENAME TO T_EMPLOYEE_PAYROLL;
   ALTER TABLE SV_EMPLOYEE_BENEFITS RENAME TO T_EMPLOYEE_BENEFITS;
   ```
2. Create Semantic Views pointing to the tables:
   ```sql
   CREATE OR REPLACE SEMANTIC VIEW SV_HR_WORKFORCE
     TABLES (
       workforce AS PAYROLL_DB.PAYROLL_SCHEMA.T_HR_WORKFORCE
         PRIMARY KEY (employee_id)
     )
     DIMENSIONS (
       workforce.employee_id AS workforce.employee_id,
       workforce.client_id AS workforce.client_id,
       workforce.full_name AS workforce.full_name,
       workforce.status_class AS workforce.status_class,
       workforce.w4_filing_status AS workforce.w4_filing_status,
       workforce.system_target AS workforce.system_target
     );
   ```

