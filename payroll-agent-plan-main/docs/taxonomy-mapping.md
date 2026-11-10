# Taxonomy mapping (requirements sheet → engine)

Runtime categories stay:

- `qa`
- `changelist`
- `todo`
- `out_of_scope` (+ `oos_destination`: `benefits` | `tax` | `workers_comp` | `other`)

| Sheet label (UC-016) | Engine category |
|---|---|
| Q&A | `qa` |
| Pay Change Request | `changelist` |
| Pay Approval | `todo` |
| Off Cycle | `todo` |
| Internal Routing (payroll ops handoff) | `todo` |
| Benefits / Tax / Workers’ Compensation | `out_of_scope` |
| Others | `todo` unless clearly non-payroll → `out_of_scope` |

Sheet labels are documentation / UI language only. They are not stored as the classifier enum.
