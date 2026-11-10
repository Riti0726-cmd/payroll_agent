-- ============================================================
-- Seed emails for Snowflake-verified employees (EMP-1001 to EMP-1005)
-- These IDs exist in sv_hr_workforce + sv_employee_payroll in Snowflake.
-- Fields: message_id, sender_email, name, subject, content, sub_content
-- All other fields left at defaults — agent will populate them on run.
-- ============================================================

INSERT INTO email_processing (message_id, sender_email, name, subject, content, sub_content)
VALUES

-- ── EMP-1001 : Jane Doe | CLT-200 | Finance | Sr Accountant | Salary ──────────
(
  'MSG-SF-001-QA-NETPAY',
  'jane.doe@acme.com', 'Jane Doe',
  'August net pay lower than expected - EMP-1001',
  'Hello Payroll Team, I noticed my August 31 paycheck shows a net pay of $2,562.41, which is the same as July. However I believe my salary was adjusted to $90,000 effective August 1 as confirmed by HR. It seems the raise was not reflected. Could you please verify my gross pay for August 2026 against the new salary? My employee ID is EMP-1001 and I am under client CLT-200.',
  '{"employee_id":"EMP-1001","client_id":"CLT-200","pay_period":"August 2026","inquiry_type":"net_pay_discrepancy","expected_salary":90000}'
),
(
  'MSG-SF-002-CL-BANKCHANGE',
  'jane.doe@acme.com', 'Jane Doe',
  'Direct deposit bank change request - EMP-1001',
  'Hi, I would like to update my direct deposit from Chase (account ending 4455) to a new Bank of America account ending in 7891. Please update this for my next payroll cycle. My employee ID is EMP-1001, client CLT-200.',
  '{"employee_id":"EMP-1001","client_id":"CLT-200","inquiry_type":"direct_deposit_change","new_bank":"Bank of America","new_account_last4":"7891","previous_bank":"Chase","previous_account_last4":"4455","system_target":"prismhr"}'
),

-- ── EMP-1002 : John Smith | CLT-200 | Warehouse | Forklift Operator | Hourly ──
(
  'MSG-SF-003-QA-OVERTIME',
  'john.smith@acme.com', 'John Smith',
  'Overtime hours missing from August paycheck - EMP-1002',
  'Hello, I worked 12 approved overtime hours during the pay period ending August 15, 2026. My pay stub shows regular pay of $1,800.00 (80 hrs x $22.50) but the overtime pay of $405.00 (12 hrs x $33.75) is listed correctly. However the gross pay of $2,205.00 and net pay of $1,595.32 do not match what I calculated. Can you confirm the breakdown is accurate? My ID is EMP-1002, client CLT-200.',
  '{"employee_id":"EMP-1002","client_id":"CLT-200","pay_period":"August 2026","inquiry_type":"overtime_verification","ot_hours":12,"hourly_rate":22.50}'
),
(
  'MSG-SF-004-QA-JULYOT',
  'john.smith@acme.com', 'John Smith',
  'Overtime pay discrepancy - July 2026 paycheck',
  'Hi Payroll, I had 8 overtime hours approved for the July 2026 pay period (pay date July 15). My check shows $270 OT pay which looks right at 1.5x my $22.50 rate. But I want to confirm whether the total deductions of $572.36 are correct since my tax situation has not changed. My employee ID is EMP-1002 under CLT-200.',
  '{"employee_id":"EMP-1002","client_id":"CLT-200","pay_period":"July 2026","inquiry_type":"deduction_verification","ot_hours":8,"total_deductions":572.36}'
),
(
  'MSG-SF-005-CL-W4UPDATE',
  'john.smith@acme.com', 'John Smith',
  'W-4 allowance update request - EMP-1002',
  'Hello Payroll Team, I recently had a new dependent so I need to update my W-4 allowances from 2 to 3. My current filing status is Married. Please update my withholding effective the next available payroll cycle. Employee ID: EMP-1002, Client: CLT-200.',
  '{"employee_id":"EMP-1002","client_id":"CLT-200","inquiry_type":"w4_update","current_allowances":2,"new_allowances":3,"filing_status":"married","system_target":"prismhr"}'
),

-- ── EMP-1003 : Maria Garcia | CLT-300 | Engineering | Software Engineer | Salary ──
(
  'MSG-SF-006-QA-NETPAY',
  'maria.garcia@globex.com', 'Maria Garcia',
  'August paycheck deductions seem high - EMP-1003',
  'Dear Payroll Support, I received my August 31 paycheck with a net pay of $3,316.03 on a gross of $4,583.33. Total deductions are $1,267.30. I want to confirm whether the medical PPO Platinum deduction ($300) and 401k ($460) are both factored into this, and whether the tax amounts ($687.50 federal, $229.17 state, $284.17 social security, $66.46 medicare) are correct for my salary of $110,000 annual. My ID is EMP-1003, client CLT-300.',
  '{"employee_id":"EMP-1003","client_id":"CLT-300","pay_period":"August 2026","inquiry_type":"deduction_verification","expected_medical_deduction":300,"expected_401k_deduction":460,"annual_salary":110000}'
),
(
  'MSG-SF-007-CL-ADDRESS',
  'maria.garcia@globex.com', 'Maria Garcia',
  'Address update needed for W-2 mailing - EMP-1003',
  'Hi, I recently moved and need my address updated before the end of year W-2 is mailed. My new address is 800 Innovation Drive, Austin, TX 78703. My previous address was 500 Tech Blvd, Austin, TX 78701. Employee ID: EMP-1003, Client ID: CLT-300.',
  '{"employee_id":"EMP-1003","client_id":"CLT-300","inquiry_type":"address_change","new_address":"800 Innovation Drive, Austin, TX 78703","previous_address":"500 Tech Blvd, Austin, TX 78701","system_target":"isolved"}'
),
(
  'MSG-SF-008-OOS-BENEFIT',
  'maria.garcia@globex.com', 'Maria Garcia',
  'Switching from PPO Platinum to HMO plan - EMP-1003',
  'Hello, I want to switch my medical plan from PPO Platinum to an HMO Basic plan during open enrollment. Can payroll help me with the enrollment change? My current premium is $300/month employee contribution. Employee ID EMP-1003, CLT-300.',
  '{"employee_id":"EMP-1003","client_id":"CLT-300","inquiry_type":"benefit_plan_change","current_plan":"PPO Platinum","requested_plan":"HMO Basic"}'
),

-- ── EMP-1004 : Robert Chen | CLT-300 | Engineering | QA Lead | Salary ──────────
(
  'MSG-SF-009-QA-NETPAY',
  'robert.chen@globex.com', 'Robert Chen',
  'August pay stub verification request - EMP-1004',
  'Hi Payroll Team, I received my August 2026 pay stub (pay date Aug 31) with a net pay of $2,863.84. I want to confirm that the gross pay of $3,958.33 is correct for my annual salary of $95,000 on a semi-monthly schedule ($95,000 / 24 = $3,958.33). Also, can you confirm the dental deduction for Delta Dental at $45 is included? Total deductions listed are $1,094.49. Employee ID: EMP-1004, Client: CLT-300.',
  '{"employee_id":"EMP-1004","client_id":"CLT-300","pay_period":"August 2026","inquiry_type":"pay_stub_verification","annual_salary":95000,"expected_gross":3958.33,"expected_dental_deduction":45}'
),
(
  'MSG-SF-010-CL-FILING',
  'robert.chen@globex.com', 'Robert Chen',
  'Filing status change from Married to Single - EMP-1004',
  'Dear Payroll, Due to a change in my personal situation, I need to update my W-4 filing status from Married (3 allowances) to Single (1 allowance) effective immediately. Please apply this change for the next payroll cycle. My employee ID is EMP-1004 and my client is CLT-300.',
  '{"employee_id":"EMP-1004","client_id":"CLT-300","inquiry_type":"w4_update","current_filing_status":"married","new_filing_status":"single","current_allowances":3,"new_allowances":1,"system_target":"isolved"}'
),
(
  'MSG-SF-011-OOS-WORKERCOMP',
  'robert.chen@globex.com', 'Robert Chen',
  'Workers compensation claim inquiry - EMP-1004',
  'Hello, I had a minor injury at work last week and need to file a workers compensation claim. Who do I contact and what is the process? Can payroll advise? Employee ID EMP-1004, Client CLT-300.',
  '{"employee_id":"EMP-1004","client_id":"CLT-300","inquiry_type":"workers_comp_claim"}'
),

-- ── EMP-1005 : Alice Johnson | CLT-200 | HR | HR Coordinator | Hourly ──────────
(
  'MSG-SF-012-QA-OVERTIME',
  'alice.j@acme.com', 'Alice Johnson',
  'Overtime pay not showing correctly - August 2026',
  'Hi, my August 15 paycheck shows regular pay of $2,240 (80 hrs x $28/hr) and overtime pay of $168 (4 hrs x $42/hr at 1.5x). The gross is $2,408 and net is $1,742.18. I just want to confirm all 4 overtime hours I logged on August 10 were approved and accounted for. My employee ID is EMP-1005 under client CLT-200.',
  '{"employee_id":"EMP-1005","client_id":"CLT-200","pay_period":"August 2026","inquiry_type":"overtime_verification","ot_hours":4,"hourly_rate":28.00,"ot_date":"2026-08-10"}'
),
(
  'MSG-SF-013-CL-BANKCHANGE',
  'alice.j@acme.com', 'Alice Johnson',
  'Direct deposit change to new Chase account - EMP-1005',
  'Hello Payroll Team, I need to update my direct deposit. My current Chase account ends in 1122 and I want to switch to a new Chase account ending in 5566 starting next payroll cycle. Please confirm once updated. Employee ID: EMP-1005, Client: CLT-200.',
  '{"employee_id":"EMP-1005","client_id":"CLT-200","inquiry_type":"direct_deposit_change","new_bank":"Chase","new_account_last4":"5566","previous_bank":"Chase","previous_account_last4":"1122","system_target":"prismhr"}'
),
(
  'MSG-SF-014-QA-TAXHIGH',
  'alice.j@acme.com', 'Alice Johnson',
  'Federal tax withholding seems high for August - EMP-1005',
  'Dear Payroll, my August federal tax withheld was $361.20 on a gross of $2,408. I am filing as single with 1 allowance. Based on my previous months this feels higher than expected. Could you review whether the correct W-4 on file is being applied? Employee ID EMP-1005, CLT-200.',
  '{"employee_id":"EMP-1005","client_id":"CLT-200","pay_period":"August 2026","inquiry_type":"tax_withholding_high","federal_tax_withheld":361.20,"gross_pay":2408,"filing_status":"single","allowances":1}'
);
