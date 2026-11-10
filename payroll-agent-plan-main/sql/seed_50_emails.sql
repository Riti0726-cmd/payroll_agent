-- ============================================================
-- 50 seed emails for email_processing (agent-ready)
-- Fields filled: message_id, sender_email, name, subject, content, sub_content
-- All other fields left at defaults — agent will populate them on run.
-- ============================================================

INSERT INTO email_processing (message_id, sender_email, name, subject, content, sub_content, is_categorized, is_drafted, is_processed)
VALUES

-- ── QA / Pay-query emails (1-18) ────────────────────────────
(
  'MSG-0001-QA-PAYCHECK',
  'james.carter@acmecorp.com', 'James Carter',
  'Why is my August paycheck lower than usual?',
  'Hi Payroll Team, I noticed my August 15 paycheck was $420 less than my usual net pay. I did not change any withholding and I did not take any unpaid time off. Could you please look into this and let me know what caused the difference? My employee ID is EMP-1042. Thank you.',
  '{"employee_id":"EMP-1042","pay_period":"August 2026","inquiry_type":"net_pay_discrepancy"}'
),
(
  'MSG-0002-QA-DEDUCTION',
  'priya.sharma@acmecorp.com', 'Priya Sharma',
  'Unexpected deduction on July payslip - EMP-2087',
  'Hello, I see a $310 deduction labeled MISC-ADJ on my July 31 payslip that I do not recognise. I have never seen this deduction before. Can you please explain what MISC-ADJ stands for and why it was applied? Employee ID: EMP-2087.',
  '{"employee_id":"EMP-2087","pay_period":"July 2026","inquiry_type":"unknown_deduction","deduction_code":"MISC-ADJ"}'
),
(
  'MSG-0003-QA-OVERTIME',
  'rafael.mendez@acmecorp.com', 'Rafael Mendez',
  'Overtime hours not reflected in pay - week ending Sep 06',
  'Hi, I worked 12 overtime hours during the week ending September 6th and they were approved by my manager David Lin. However my paycheck issued on September 10th does not show any OT pay. Please check and correct. EMP-3301.',
  '{"employee_id":"EMP-3301","pay_period":"September 2026","inquiry_type":"overtime_missing","ot_hours":12}'
),
(
  'MSG-0004-QA-BONUS',
  'lisa.nguyen@acmecorp.com', 'Lisa Nguyen',
  'Q3 performance bonus not received',
  'Dear Payroll, I was informed by HR in an email dated August 20 that I would receive a Q3 performance bonus of $2,500 in the September payroll cycle. The September 30 paycheck did not include this bonus. Could you verify and process it? My ID is EMP-4455.',
  '{"employee_id":"EMP-4455","pay_period":"September 2026","inquiry_type":"bonus_missing","expected_amount":2500}'
),
(
  'MSG-0005-QA-RETRO',
  'michael.obi@acmecorp.com', 'Michael Obi',
  'Retro pay from April raise still missing',
  'Hello Payroll Team, My salary was increased from $78,000 to $85,000 effective April 1. HR told me retro pay for April through June would be included in the July paycheck. It is now August and I still have not received it. EMP-1198.',
  '{"employee_id":"EMP-1198","pay_period":"July 2026","inquiry_type":"retro_pay_missing","effective_date":"2026-04-01"}'
),
(
  'MSG-0006-QA-TAXWITHHOLDING',
  'sophie.klein@acmecorp.com', 'Sophie Klein',
  'Federal tax withheld seems too high this month',
  'Hi, my federal income tax withheld in October was $1,840 vs an average of $1,200 in prior months. I did not change my W-4. I am single with no additional withholding. Can you check if there was a calculation error? EMP-5522.',
  '{"employee_id":"EMP-5522","pay_period":"October 2026","inquiry_type":"tax_withholding_high"}'
),
(
  'MSG-0007-QA-GARNISHMENT',
  'david.park@acmecorp.com', 'David Park',
  'Child support garnishment deducted twice in September',
  'Team, I noticed that my child support garnishment of $750 was deducted twice on my September paycheck — once on the 15th and once on the 30th — but only one payment is due per month. Please correct and refund the extra deduction. EMP-6633.',
  '{"employee_id":"EMP-6633","pay_period":"September 2026","inquiry_type":"garnishment_double_deduction","amount":750}'
),
(
  'MSG-0008-QA-401K',
  'amara.diallo@acmecorp.com', 'Amara Diallo',
  'My 401k contribution percentage did not update',
  'Hello, I submitted a form to increase my 401k contribution from 6% to 10% effective August 1. My August and September paychecks still show 6%. Please check the update status. Employee: EMP-7744.',
  '{"employee_id":"EMP-7744","pay_period":"August 2026","inquiry_type":"401k_contribution_not_updated","requested_rate":10}'
),
(
  'MSG-0009-QA-PAYSLIP',
  'kevin.walsh@acmecorp.com', 'Kevin Walsh',
  'Cannot access my payslip for June on the portal',
  'Hi, the employee portal shows an error when I try to download my June 30 payslip. I have tried three different browsers. Can you email me the payslip directly or fix the portal issue? EMP-8855.',
  '{"employee_id":"EMP-8855","pay_period":"June 2026","inquiry_type":"payslip_access_issue"}'
),
(
  'MSG-0010-QA-SHIFT',
  'fatima.al-rashid@acmecorp.com', 'Fatima Al-Rashid',
  'Shift differential missing from Oct 15 paycheck',
  'Dear Payroll, I worked the night shift (11 PM – 7 AM) for 8 days in the first half of October and should have received a 15% shift differential. The October 15 paycheck shows no shift differential. EMP-9900.',
  '{"employee_id":"EMP-9900","pay_period":"October 2026","inquiry_type":"shift_differential_missing","shift":"night","days":8}'
),
(
  'MSG-0011-QA-COMMISSION',
  'brian.santos@techsales.com', 'Brian Santos',
  'Commission for September not included in paycheck',
  'Hi Team, I closed $180,000 in sales in September which at our 2% commission rate should have generated $3,600 in commission. This was not in my September 30 pay. Please investigate. EMP-1123.',
  '{"employee_id":"EMP-1123","pay_period":"September 2026","inquiry_type":"commission_missing","sales_amount":180000,"expected_commission":3600}'
),
(
  'MSG-0012-QA-HOLIDAY',
  'nancy.flores@acmecorp.com', 'Nancy Flores',
  'Holiday pay for Labor Day not on paycheck',
  'Hello, Labor Day (September 2) was a company holiday, but my September 15 paycheck does not include holiday pay. All other full-time employees seem to have received it. EMP-2244.',
  '{"employee_id":"EMP-2244","pay_period":"September 2026","inquiry_type":"holiday_pay_missing","holiday":"Labor Day 2026"}'
),
(
  'MSG-0013-QA-NET',
  'george.chen@acmecorp.com', 'George Chen',
  'Why did my net pay drop by $900 in August?',
  'Hi Payroll, comparing my July and August net pay, there is a $900 drop. My salary, marital status, and withholding elections have not changed. Can you give me a line-by-line breakdown of what changed between the two months? EMP-3355.',
  '{"employee_id":"EMP-3355","pay_period":"August 2026","inquiry_type":"net_pay_drop","delta":-900}'
),
(
  'MSG-0014-QA-REIMBURSE',
  'helen.murphy@acmecorp.com', 'Helen Murphy',
  'Business travel reimbursement not in October paycheck',
  'Team, I submitted a $1,250 expense report for my Chicago business trip (approved by manager Oct 5) and was told it would be in the October 31 paycheck. It was not included. EMP-4466.',
  '{"employee_id":"EMP-4466","pay_period":"October 2026","inquiry_type":"reimbursement_missing","amount":1250}'
),
(
  'MSG-0015-QA-SALARY',
  'tom.larsen@acmecorp.com', 'Tom Larsen',
  'Salary appears incorrect after promotion - EMP-5577',
  'Hi, I was promoted to Senior Analyst effective September 1 with a new salary of $95,000. My September paycheck still shows the old salary of $82,000. HR confirmed the promotion in writing. Please correct. EMP-5577.',
  '{"employee_id":"EMP-5577","pay_period":"September 2026","inquiry_type":"salary_not_updated","old_salary":82000,"new_salary":95000,"effective_date":"2026-09-01"}'
),
(
  'MSG-0016-QA-YTDTAX',
  'elena.petrov@acmecorp.com', 'Elena Petrov',
  'YTD federal tax looks incorrect on November payslip',
  'Hi Payroll, my year-to-date federal withholding on the November payslip shows $19,400 but based on my monthly withholding of $1,400 it should be around $15,400. Something seems wrong. EMP-6688.',
  '{"employee_id":"EMP-6688","pay_period":"November 2026","inquiry_type":"ytd_tax_discrepancy"}'
),
(
  'MSG-0017-QA-DOUBLENET',
  'oscar.james@acmecorp.com', 'Oscar James',
  'Was paid double net pay on Oct 31 - please advise',
  'Hello, I was paid twice on October 31 — my bank shows two identical deposits of $3,840 each. I want to report this and understand what I should do. EMP-7799.',
  '{"employee_id":"EMP-7799","pay_period":"October 2026","inquiry_type":"duplicate_payment","amount":3840}'
),
(
  'MSG-0018-QA-PTO',
  'chloe.martin@acmecorp.com', 'Chloe Martin',
  'PTO payout on separation not received',
  'Hi, I resigned effective October 15 and HR said my remaining 48 PTO hours would be paid out in my final check. The final paycheck did not include PTO payout. Please process ASAP. EMP-8811.',
  '{"employee_id":"EMP-8811","pay_period":"October 2026","inquiry_type":"pto_payout_missing","pto_hours":48}'
),

-- ── CHANGELIST emails (19-34) ────────────────────────────────
(
  'MSG-0019-CL-BANKACCT',
  'aaron.cole@acmecorp.com', 'Aaron Cole',
  'Request to update direct deposit bank account',
  'Hi Payroll, I recently opened a new checking account and would like to update my direct deposit. New bank: Chase, Routing: 021000021, Account: 7890123456 (checking). Please process before the next pay cycle. EMP-1001.',
  '{"employee_id":"EMP-1001","change_type":"direct_deposit","new_bank":"Chase","new_routing":"021000021","new_account":"7890123456"}'
),
(
  'MSG-0020-CL-ADDRESS',
  'maya.robinson@acmecorp.com', 'Maya Robinson',
  'Home address change for W-2 purposes',
  'Hello, I moved last week. Please update my home address to: 4821 Maple Grove Drive, Austin, TX 78701. This needs to be updated before year-end for my W-2. EMP-2002.',
  '{"employee_id":"EMP-2002","change_type":"address","new_address":"4821 Maple Grove Drive, Austin, TX 78701"}'
),
(
  'MSG-0021-CL-W4',
  'ethan.brooks@acmecorp.com', 'Ethan Brooks',
  'W-4 update — married filing jointly, 2 allowances',
  'Hi Payroll Team, I got married in September and need to update my W-4. New filing status: Married Filing Jointly. Additional withholding: none. Please apply from the November pay cycle. EMP-3003.',
  '{"employee_id":"EMP-3003","change_type":"w4_update","new_status":"married_filing_jointly","allowances":2,"effective_date":"2026-11-01"}'
),
(
  'MSG-0022-CL-SPLIT',
  'isabella.turner@acmecorp.com', 'Isabella Turner',
  'Split direct deposit — savings and checking',
  'Hello, I want to split my direct deposit: 70% to my checking (Wells Fargo routing 121042882, acct 11223344) and 30% to my savings (Wells Fargo routing 121042882, acct 55667788). EMP-4004.',
  '{"employee_id":"EMP-4004","change_type":"direct_deposit_split","checking_pct":70,"savings_pct":30}'
),
(
  'MSG-0023-CL-WITHHOLDING',
  'liam.scott@acmecorp.com', 'Liam Scott',
  'Increase federal withholding by $200 per paycheck',
  'Hi, I would like to increase my additional federal withholding by $200 per pay period (currently $0 additional). Please apply from the December 1 payroll. EMP-5005.',
  '{"employee_id":"EMP-5005","change_type":"additional_withholding","amount":200,"effective_date":"2026-12-01"}'
),
(
  'MSG-0024-CL-TAXEXEMPT',
  'zoe.harris@acmecorp.com', 'Zoe Harris',
  'Claiming exempt from federal withholding for 2027',
  'Hello Payroll, I qualify to claim exempt from federal withholding for 2027 (had no tax liability in 2026 and expect none in 2027). Please update my W-4 accordingly. EMP-6006.',
  '{"employee_id":"EMP-6006","change_type":"w4_exempt","year":2027}'
),
(
  'MSG-0025-CL-NAME',
  'sarah.johnson@acmecorp.com', 'Sarah Johnson',
  'Legal name change — please update payroll records',
  'Hi Team, I recently changed my legal name. Former name: Sarah Williams. New legal name: Sarah Johnson. Social Security card has been updated. Please update all payroll records and W-2 name. EMP-7007.',
  '{"employee_id":"EMP-7007","change_type":"name_change","old_name":"Sarah Williams","new_name":"Sarah Johnson"}'
),
(
  'MSG-0026-CL-401KINCREASE',
  'noah.patel@acmecorp.com', 'Noah Patel',
  'Increase 401k deferral to 15%',
  'Hello, please increase my 401k pre-tax deferral from 8% to 15% effective December 1, 2026. I am within annual IRS limits. EMP-8008.',
  '{"employee_id":"EMP-8008","change_type":"401k_increase","old_rate":8,"new_rate":15,"effective_date":"2026-12-01"}'
),
(
  'MSG-0027-CL-HSA',
  'ava.wilson@acmecorp.com', 'Ava Wilson',
  'Start HSA payroll deduction — $250/month',
  'Hi Payroll, I enrolled in the HDHP plan during open enrollment. Please start an HSA payroll deduction of $250 per month effective January 1, 2027. EMP-9009.',
  '{"employee_id":"EMP-9009","change_type":"hsa_start","monthly_amount":250,"effective_date":"2027-01-01"}'
),
(
  'MSG-0028-CL-DIRECTSTOP',
  'jackson.lee@acmecorp.com', 'Jackson Lee',
  'Stop direct deposit to savings account',
  'Hello, please discontinue the $500/month direct deposit to my Bank of America savings account (ending 4321) and deposit full net pay to my checking account (ending 8765) starting next pay cycle. EMP-1010.',
  '{"employee_id":"EMP-1010","change_type":"direct_deposit_stop_savings","checking_ending":"8765"}'
),
(
  'MSG-0029-CL-STATEWITHOLD',
  'mia.taylor@acmecorp.com', 'Mia Taylor',
  'Update state withholding — moved to California',
  'Hi, I relocated from Texas to California on November 1. Please update my state tax withholding to California (CA DE-4 form attached). Filing status: Single, 1 allowance. EMP-2020.',
  '{"employee_id":"EMP-2020","change_type":"state_withholding_update","new_state":"CA","old_state":"TX","effective_date":"2026-11-01"}'
),
(
  'MSG-0030-CL-GARNSTOP',
  'lucas.anderson@acmecorp.com', 'Lucas Anderson',
  'Court order to stop wage garnishment',
  'Hi Payroll, I have attached a court order issued October 20 that terminates my wage garnishment effective immediately. Please stop all garnishment deductions from my next paycheck. EMP-3030.',
  '{"employee_id":"EMP-3030","change_type":"garnishment_stop","court_order_date":"2026-10-20"}'
),
(
  'MSG-0031-CL-BENFICIARY',
  'emma.thomas@acmecorp.com', 'Emma Thomas',
  'Update 401k beneficiary designation',
  'Hello, I recently had my first child and would like to update my 401k primary beneficiary. New primary: Liam Thomas (son, DOB 2026-08-10, 100%). Please send the beneficiary form or process via the portal. EMP-4040.',
  '{"employee_id":"EMP-4040","change_type":"401k_beneficiary_update","new_beneficiary":"Liam Thomas","relationship":"son"}'
),
(
  'MSG-0032-CL-ROTH',
  'oliver.moore@acmecorp.com', 'Oliver Moore',
  'Switch 401k contribution from pre-tax to Roth',
  'Hi Payroll, I want to switch my entire 401k contribution (currently 10% pre-tax) to Roth 401k effective January 1, 2027. Same percentage, just change the tax treatment. EMP-5050.',
  '{"employee_id":"EMP-5050","change_type":"401k_pretax_to_roth","rate":10,"effective_date":"2027-01-01"}'
),
(
  'MSG-0033-CL-DCFSA',
  'grace.jackson@acmecorp.com', 'Grace Jackson',
  'Enroll in Dependent Care FSA — $5,000 annual',
  'Hello, I want to enroll in the Dependent Care FSA for 2027 at the maximum allowed $5,000 per year ($208.33/pay period semi-monthly). Please process during open enrollment. EMP-6060.',
  '{"employee_id":"EMP-6060","change_type":"dcfsa_enroll","annual_election":5000,"per_period":208.33}'
),
(
  'MSG-0034-CL-BANKCLOSE',
  'sophie.white@acmecorp.com', 'Sophie White',
  'Old bank account closed — urgent DD update needed',
  'URGENT — my Citibank account was closed today. Please update my direct deposit immediately to: TD Bank, Routing 026013673, Account 998877665 (checking). Next payroll is in 3 days. EMP-7070.',
  '{"employee_id":"EMP-7070","change_type":"direct_deposit","urgency":"high","new_bank":"TD Bank","new_routing":"026013673","new_account":"998877665"}'
),

-- ── TODO / Action-needed emails (35-44) ─────────────────────
(
  'MSG-0035-TD-TIMESHEET',
  'rachel.kim@acmecorp.com', 'Rachel Kim',
  'Please approve my October timesheet — pending 5 days',
  'Hi, my October timesheet has been submitted and pending manager approval for 5 business days. If it is not approved by EOD Friday the payroll run will be missed. Can you escalate to my manager Mike Grant? EMP-8080.',
  '{"employee_id":"EMP-8080","action":"timesheet_approval","days_pending":5,"manager":"Mike Grant"}'
),
(
  'MSG-0036-TD-OFFCYCLE',
  'hr.admin@acmecorp.com', 'HR Admin',
  'Off-cycle payroll request for 3 terminated employees',
  'Payroll Team, please process an off-cycle payroll run for the following terminated employees who did not receive their final pay on the regular cycle: EMP-9091, EMP-9092, EMP-9093. Final pay dates were October 20, 21, and 22 respectively.',
  '{"action":"off_cycle_payroll","affected_employees":["EMP-9091","EMP-9092","EMP-9093"],"reason":"final_pay_missed"}'
),
(
  'MSG-0037-TD-NEWJOIN',
  'hr.recruit@acmecorp.com', 'HR Recruiting',
  'New hire payroll setup — 5 employees start Nov 1',
  'Hi Payroll, please set up payroll for 5 new hires starting November 1: Jessica Ford (EMP-1111), Samuel Park (EMP-1112), Amy Liu (EMP-1113), Carlos Rivera (EMP-1114), Priti Desai (EMP-1115). I-9 and direct deposit forms are attached.',
  '{"action":"new_hire_setup","start_date":"2026-11-01","count":5,"employees":["EMP-1111","EMP-1112","EMP-1113","EMP-1114","EMP-1115"]}'
),
(
  'MSG-0038-TD-MANUAL',
  'finance@acmecorp.com', 'Finance Team',
  'Manual paycheck needed for field employee',
  'Hello Payroll, our field technician Robert Marsh (EMP-2222) does not have direct deposit set up and missed the paper check cutoff. Please issue a manual check for his October 31 net pay of $3,120 and courier to Site B. ',
  '{"employee_id":"EMP-2222","action":"manual_check","amount":3120,"delivery":"courier","site":"Site B"}'
),
(
  'MSG-0039-TD-ADVANCE',
  'john.davis@acmecorp.com', 'John Davis',
  'Payroll advance request — medical emergency',
  'Hi Payroll, I am dealing with a medical emergency and need a payroll advance of $1,500 against my upcoming November 15 paycheck. I have my manager approval attached. Please process today. EMP-3333.',
  '{"employee_id":"EMP-3333","action":"payroll_advance","amount":1500,"against_period":"November 2026","manager_approved":true}'
),
(
  'MSG-0040-TD-CORRECTION',
  'payroll.ops@acmecorp.com', 'Payroll Operations',
  'Payroll correction needed — wrong pay rate used for 8 employees',
  'Team, we identified that the wrong hourly rate was used for 8 employees in the Oct 31 run (old rate applied instead of updated rate effective Oct 1). Affected: EMP-4001 through EMP-4008. Please calculate retro correction amounts and prepare adjustment run.',
  '{"action":"payroll_correction","affected_count":8,"employee_range":"EMP-4001 to EMP-4008","error":"wrong_pay_rate","period":"October 2026"}'
),
(
  'MSG-0041-TD-VERIFY',
  'audit@acmecorp.com', 'Internal Audit',
  'Payroll data verification request — Q3 audit',
  'Hi Payroll Team, as part of the Q3 internal audit we need payroll register exports for July, August, and September. Please prepare the standard payroll register files and send to the audit mailbox by November 10. ',
  '{"action":"audit_data_export","quarters":["Q3 2026"],"months":["July","August","September"],"due_date":"2026-11-10"}'
),
(
  'MSG-0042-TD-APPROVE',
  'sarah.chen@acmecorp.com', 'Sarah Chen',
  'Awaiting approval on Q4 incentive payout list',
  'Hello, I sent the Q4 incentive payout list to the payroll director last week for final approval before the November 30 run. Can you confirm it has been received and is in the queue for approval? Total payout: $142,000 across 24 employees.',
  '{"action":"incentive_approval","total_amount":142000,"employee_count":24,"target_period":"November 2026"}'
),
(
  'MSG-0043-TD-TERMPAY',
  'hr.ops@acmecorp.com', 'HR Operations',
  'Final pay calculation needed — employee EMP-5050 termination Oct 28',
  'Hi Payroll, employee Derek Hughes (EMP-5050) resigned effective October 28. Please calculate his final pay including: remaining October salary (Oct 20-28), 32 hours unused PTO payout, and deduct the outstanding $400 equipment loan. Final check needed by Nov 1.',
  '{"employee_id":"EMP-5050","action":"termination_final_pay","last_day":"2026-10-28","pto_hours":32,"equipment_loan_deduction":400}'
),
(
  'MSG-0044-TD-RAISESCHEDULE',
  'compensation@acmecorp.com', 'Compensation Team',
  'Annual merit increase file attached — please load for Dec 1',
  'Hi Payroll, the annual merit increase file for 2026 is attached (145 employees, effective December 1). Please validate, load into the system, and confirm receipt by November 15. Average increase is 4.2%.',
  '{"action":"merit_increase_load","effective_date":"2026-12-01","employee_count":145,"avg_increase_pct":4.2,"confirmation_due":"2026-11-15"}'
),

-- ── OUT-OF-SCOPE emails (45-50) ──────────────────────────────
(
  'MSG-0045-OOS-BENEFITS',
  'peter.hall@acmecorp.com', 'Peter Hall',
  'Open enrollment — which dental plan covers orthodontia?',
  'Hi, during open enrollment I am trying to decide between the Delta Dental Basic and Premium plans. Does the Premium plan cover orthodontia for adults? What is the annual orthodontia maximum? I could not find this in the benefits guide.',
  NULL
),
(
  'MSG-0046-OOS-401KADVICE',
  'linda.young@acmecorp.com', 'Linda Young',
  'Should I increase my 401k to max out for 2026?',
  'Hi Payroll Team, I want to make sure I max out my 401k for 2026 (limit is $23,000). Currently contributing 10% of my $90,000 salary = $9,000/year. How much should I increase my contribution percentage? Also what is the last pay date to make changes?',
  NULL
),
(
  'MSG-0047-OOS-WORKERSCOMP',
  'mike.evans@acmecorp.com', 'Mike Evans',
  'Workers comp claim — injured my back at the warehouse',
  'Hi, I injured my back lifting a box at the warehouse on October 30. I went to urgent care and have a doctors note. How do I file a workers comp claim? Will my pay continue while I am on workers comp leave? EMP-6060.',
  NULL
),
(
  'MSG-0048-OOS-W2ADVICE',
  'karen.white@acmecorp.com', 'Karen White',
  'W-2 question — box 12 code DD explanation',
  'Hi Payroll, I am doing my taxes early and I do not understand what Box 12 Code DD on my W-2 means. My tax preparer asked me if this amount is deductible. Can you explain and also confirm whether I will need to report it separately on my return?',
  NULL
),
(
  'MSG-0049-OOS-TAXFILING',
  'james.brown@acmecorp.com', 'James Brown',
  'Help with state tax filing — worked in two states',
  'Hi, I worked in New York from January to June and transferred to New Jersey in July. I am confused about how to file state taxes for 2026. Do I need to file in both states? Will there be any double taxation? Who should I contact for help?',
  NULL
),
(
  'MSG-0050-OOS-FMLA',
  'angela.scott@acmecorp.com', 'Angela Scott',
  'FMLA leave request — caring for ill parent',
  'Hi HR/Payroll, I need to request FMLA leave starting November 15 to care for my elderly mother who was just diagnosed with a serious illness. How do I apply for FMLA? Will I receive pay during the leave? How does it affect my benefits? EMP-7070.',
  NULL
);

