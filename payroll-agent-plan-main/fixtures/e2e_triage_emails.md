# E2E triage email fixtures (Demo Client 000100)

Generated for the 10 employees returned by Cortex Analyst.
Use these as Outlook inbox seeds; do not invent Snowflake figures beyond what emails state.

## Employees

| employee_id | client_id | client_name | employment_type | status_class |
|---|---|---|---|---|
| A00001 | 000100 | Demo Client | F | A |
| A04801 | 000100 | Demo Client | F | A |
| B01154 | 000100 | Demo Client | F | A |
| B02090 | 000100 | Demo Client | F | L |
| C04803 | 000100 | Demo Client | F | A |
| D00172 | 000100 | Demo Client | F | A |
| E00173 | 000100 | Demo Client | F | A |
| E00965 | 000100 | Demo Client | F | A |
| E02021 | 000100 | Demo Client | F | A |
| E02645 | 000100 | Demo Client | F | A |

## Scenario map

| # | Expected category | employee_id | Scenario |
|---|---|---|---|
| 1 | qa | A00001 | Net pay lower than expected (August) |
| 2 | qa | A04801 | Deduction / garnishments question |
| 3 | changelist | B01154 | Hourly rate increase (states from/to) |
| 4 | changelist | B02090 | Direct deposit / bank update |
| 5 | changelist | C04803 | W-4 withholding change |
| 6 | todo | D00172 | Timesheet / pay approval request |
| 7 | todo | E00173 | Off-cycle payroll request |
| 8 | out_of_scope | E00965 | Benefits enrollment |
| 9 | out_of_scope | E02021 | Workers' compensation claim |
| 10 | out_of_scope | E02645 | Personal tax filing advice |
| 11 | qa | A00001 | Bonus not reflected (follow-up style) |
| 12 | changelist | A04801 | Position / title change with rate |
| 13 | todo | B01154 | Urgency: approve corrected hours ASAP |
| 14 | changelist | D00172 | Incomplete rate change (to only — tests incomplete lines) |
| 15 | qa | E00173 | YTD tax withholding variance |

---

## Email bodies

### 1 — QA — paycheck lower (A00001)

**From:** manager.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Client 000100 / EMP A00001 — August net pay looks short

```text
Hi Payroll Specialist,

For Demo Client (client_id 000100), employee A00001 is asking why their August 2026
net pay was lower than July.

Pay period: 2026-08
Employee ID: A00001
Client ID: 000100

Can you check regular earnings, overtime, and employee deductions and explain the variance?

Thanks,
Client HR
```

### 2 — QA — deductions (A04801)

**From:** a04801.employee@example.com  
**To:** payroll@peoservices.com  
**Subject:** Question on deductions for employee A04801 (Demo Client)

```text
Hello,

I am writing about employee A04801 at client 000100 (Demo Client).
On the latest payslip there is a deduction I do not recognize.

Please confirm what garnishment or benefit deduction codes applied for the
current pay period and the amounts from payroll history.

Employee ID: A04801
Client ID: 000100

Thank you.
```

### 3 — Changelist — hourly rate with from/to (B01154)

**From:** hr.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Pay change request — EMP B01154 hourly rate $20 → $22

```text
Payroll team,

Please process a pay change for Demo Client 000100 / employee B01154.

Change type: hourly_pay_rate
Previous hourly rate: 20.00
New hourly rate: 22.00
Effective date: 2026-09-14
Due: please complete by 2026-09-20

Employee ID: B01154
Client ID: 000100

Please prepare the change list for specialist review (no system write-back yet).

Regards,
Client Payroll Contact
```

### 4 — Changelist — direct deposit (B02090)

**From:** hr.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Bank / direct deposit update — EMP B02090

```text
Hi,

Employee B02090 (client 000100 Demo Client) needs a direct deposit account update.

Please change direct deposit to:
Bank routing: 021000021
Account ending: 4455 (checking)

Effective as soon as possible for the next pay cycle.
Note: status_class for this employee may show L — please validate in Snowflake before processing.

Employee ID: B02090
Client ID: 000100

Thanks,
HR
```

### 5 — Changelist — W-4 (C04803)

**From:** c04803@example.com  
**To:** payroll@peoservices.com  
**Subject:** W-4 withholding update — C04803 / client 000100

```text
Please update W-4 federal withholding for employee C04803 at Demo Client (000100).

Requested change:
- Filing status: Married filing jointly
- Extra withholding: $50 per pay period
Effective date: 2026-10-01

Employee ID: C04803
Client ID: 000100

Please create a change list line for specialist approval.
```

### 6 — Todo — pay approval / timesheet (D00172)

**From:** supervisor.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Please approve timesheet — EMP D00172 week of Sep 8

```text
Payroll,

Please approve hours for employee D00172 (Demo Client / 000100) for the week of
2026-09-08.

Regular: 40
OT: 4

This is a pay approval / timesheet task — confirm receipt and expected turnaround.

Employee ID: D00172
Client ID: 000100

— Supervisor
```

### 7 — Todo — off-cycle (E00173)

**From:** hr.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Off-cycle payroll request — EMP E00173

```text
We need an off-cycle / special payroll run for employee E00173 at client 000100
(Demo Client) for a missed reimbursement of $350.

Please schedule off-cycle processing and confirm the next available window.
This is an operational TODO for the specialist queue (not a data Q&A).

Employee ID: E00173
Client ID: 000100
Pay period context: 2026-09

Thank you,
HR Ops
```

### 8 — Out of scope — benefits (E00965)

**From:** e00965@example.com  
**To:** payroll@peoservices.com  
**Subject:** Help enrolling in dental benefits — E00965

```text
Hi,

I need help enrolling employee E00965 (client 000100) in dental benefits for open enrollment.
Which plan should they pick and how do they add dependents?

Employee ID: E00965
Client ID: 000100

Please route to Benefits if this is outside payroll.
```

### 9 — Out of scope — workers' comp (E02021)

**From:** manager.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Workers compensation claim follow-up — EMP E02021

```text
We have a workplace injury claim for employee E02021 at Demo Client 000100.
Can payroll file the workers' compensation paperwork and advise on claim status?

Employee ID: E02021
Client ID: 000100

Please route appropriately if out of payroll specialist scope.
```

### 10 — Out of scope — tax filing (E02645)

**From:** e02645@example.com  
**To:** payroll@peoservices.com  
**Subject:** Personal tax return advice — E02645

```text
Can you help employee E02645 (client 000100) prepare their personal IRS tax return
and recommend deductions for a side business?

Employee ID: E02645
Client ID: 000100

This may be tax advisory rather than payroll operations.
```

### 11 — QA — bonus missing (A00001)

**From:** hr.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Bonus not on payslip — EMP A00001 / client 000100

```text
Follow-up for Demo Client 000100 employee A00001:

A $500 spot bonus was approved for August but does not appear on the payslip.
Please check payroll history / earnings codes for pay period 2026-08 and explain
whether it was paid, deferred, or miscoded.

Employee ID: A00001
Client ID: 000100
Pay period: 2026-08
```

### 12 — Changelist — position + rate (A04801)

**From:** hr.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Position and pay rate change — A04801

```text
Please process a position update for employee A04801, client 000100 (Demo Client).

New position: Senior Payroll Clerk
Previous hourly rate: 18.50
New hourly rate: 21.00
Effective date: 2026-09-21

Employee ID: A04801
Client ID: 000100

Create change-list lines for position and hourly_pay_rate for HITL review.
```

### 13 — Todo — urgent hours correction (B01154)

**From:** supervisor.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** URGENT ASAP — correct hours approval EMP B01154

```text
URGENT — please approve corrected timesheet for employee B01154 (client 000100)
immediately / ASAP before today's cutoff.

Corrected OT: 6 hours (was 2).
This is a rush pay-approval task for the specialist TODO queue.

Employee ID: B01154
Client ID: 000100
```

### 14 — Changelist — incomplete (to only) (D00172)

**From:** hr.demo@example.com  
**To:** payroll@peoservices.com  
**Subject:** Raise hourly rate to $24 — EMP D00172 (no prior rate stated)

```text
Please increase the hourly rate for employee D00172 at Demo Client 000100 to $24.00
effective 2026-09-28.

We do not have the previous rate in this email — look up current rate in Snowflake
and build the change list.

Employee ID: D00172
Client ID: 000100
New hourly rate: 24.00
Effective date: 2026-09-28
```

### 15 — QA — YTD tax variance (E00173)

**From:** e00173@example.com  
**To:** payroll@peoservices.com  
**Subject:** YTD federal tax looks high — E00173

```text
For employee E00173 / client 000100, year-to-date federal withholding seems higher
than expected compared to peers on the same pay cycle.

Please use payroll history to compare YTD taxable wages and federal tax withheld
and explain any variance. Do not invent figures.

Employee ID: E00173
Client ID: 000100
Pay period context: 2026 YTD through August
```

---

## Suggested inject order (Outlook)

Send or create as **new Inbox messages** to `payroll@peoservices.com` with received time within the specialist lookback window (e.g. last 1–2 days) so Run triage picks them up.
