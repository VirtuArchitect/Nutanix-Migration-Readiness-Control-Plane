# Move Plan Brief

`move-plan-brief.md` is the reviewer-facing companion to
`nutanix-move-plan.csv`. It summarizes which workloads are eligible for Nutanix
Move staging review, which workloads must be held, the governance warnings for
included rows, the evidence to inspect, and the stop conditions before any
appliance submission.

## Generate

The brief is generated automatically with every assessment. Regenerate it from
an existing assessment when needed:

```powershell
python -m nmrcp.cli move-plan-brief `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --assessment outputs\sample-assessment\assessment.json `
  --out outputs\sample-assessment\move-plan-brief.md
```

## Validate

```powershell
python -m nmrcp.cli validate-move-plan-brief `
  --brief outputs\sample-assessment\move-plan-brief.md `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

Validation checks schema text `nmrcp_move_plan_brief_v1`, required sections,
the Move plan schema `nmrcp_move_plan_v1`, source-bound workload fields,
include/precheck consistency, governance warnings, redaction, and exact
Markdown regeneration from the CSV plus `assessment.json`.

## Safety Boundary

The brief is not Nutanix Move appliance proof and it does not submit a plan. Do
not submit rows with `include_in_move_plan=no` or
`precheck_status=hold_until_remediated`. Final production handoff still requires
approved Nutanix Move lab evidence and passing validation results.
