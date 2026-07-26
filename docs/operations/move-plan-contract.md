# Move Plan Contract

## Contract

`nutanix-move-plan.csv` uses the `nmrcp_move_plan_v1` staging contract. It is a
validated operator planning artifact for Nutanix Move workflows, not a claimed
direct import format for every Nutanix Move version.
`move-plan-brief.md` is generated beside it as the human review summary.

Nutanix Move exposes migration-plan APIs that require source provider, target
provider, network mappings, schedule settings, and workload information. This
contract prepares the workload and precheck portion of that workflow while
keeping mutation out of the MVP.

## Columns

```text
schema_version
include_in_move_plan
wave
source_vm_id
source_vm_name
owner
target
readiness
risk_score
target_networks
dependency_count
application_owner_approval
rollback_owner
precheck_status
required_actions
```

## Validation

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-move-plan --plan outputs\smoke\nutanix-move-plan.csv
```

When the plan is being reviewed as part of an assessment packet, bind it to the
canonical assessment source:

```powershell
python -m nmrcp.cli validate-move-plan `
  --plan outputs\smoke\nutanix-move-plan.csv `
  --assessment outputs\smoke\assessment.json
python -m nmrcp.cli validate-move-plan-brief `
  --brief outputs\smoke\move-plan-brief.md `
  --plan outputs\smoke\nutanix-move-plan.csv `
  --assessment outputs\smoke\assessment.json
```

The change gate, workflow run, MVP audit, and handoff package use this
assessment-bound validation automatically.

Validation fails when:

- Required columns are missing.
- The schema version is not `nmrcp_move_plan_v1`.
- A blocked or remediation-required workload is included for staging.
- Include/hold flags do not match precheck status.
- Application owner approval state is not `confirmed`, `not confirmed`, or
  `not supplied`.
- Risk scores or dependency counts are invalid.
- Source VM IDs are missing or duplicated.
- Assessment-bound validation detects missing, extra, or stale source-bound
  workload fields: schema version, include flag, wave, source VM identity,
  owner, target, readiness, risk score, precheck status, and required actions.
- Assessment-bound validation fails closed when `assessment.json` wave
  membership references unknown workload IDs or places one workload in multiple
  waves.

Validation warns when an included workload does not have confirmed application
owner approval or a confirmed rollback owner. This lets discovery-only plans
remain reviewable while making governance gaps visible before handoff.

## Safety Rule

Only `ready` and `research` workloads can be included in the plan. `prepare` and
`blocked` workloads are held until remediation is complete.

## Future Move API Work

The next step after dry-run payload generation is a lab-only submitter that is
disabled by default and tested against a non-production Nutanix Move appliance.
