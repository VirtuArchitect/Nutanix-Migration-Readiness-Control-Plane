# Move Submit Readiness

## Purpose

`validate-move-submit-readiness` is a fail-closed lab-only gate for reviewed
Move API payloads. It does not connect to Nutanix Move and does not submit a
migration plan. It proves that a dry-run payload has enough lab review evidence
before any future submitter is considered.

## Command

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli generate-move-payload `
  --plan outputs\smoke\nutanix-move-plan.csv `
  --config examples\sample_move_payload_lab_config.json `
  --out outputs\smoke\move-api-payload.lab.dry-run.json
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-submit-readiness `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out outputs\smoke\move-submit-readiness.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

## Required Proof

The gate fails unless:

- the payload contract is `nmrcp_move_api_payload_dry_run_v1`.
- the payload has `dry_run_only=true` and `mutation_allowed=false`.
- at least one workload is included.
- network mapping validation passed when the payload was generated.
- source provider, target provider, target cluster, and target container values
  are populated with reviewed lab identifiers instead of placeholders.
- schedule settings do not start immediately.
- the review file uses `nmrcp_move_submit_review_v1`.
- the review environment is `lab`.
- reviewer, review timestamp, and lab Move appliance fields are supplied.
- payload, network mapping, rollback, and no-production-submit approvals are
  all true.
- `NMRCP_MOVE_LAB_ACK` is set to `I_UNDERSTAND_LAB_ONLY`.

## Review Record

```json
{
  "schema_version": "nmrcp_move_submit_review_v1",
  "environment": "lab",
  "reviewed_by": "Migration Lab Operator",
  "reviewed_at": "2026-07-24T14:00:00Z",
  "lab_move_appliance": "move-lab-01.example.test",
  "approvals": {
    "payload_reviewed": true,
    "network_mapping_reviewed": true,
    "rollback_reviewed": true,
    "no_production_submit": true
  }
}
```

## Safety

The MVP still has no Move submit command. This gate is a readiness proof for
lab experimentation only. Production submission remains out of scope until a
real Nutanix Move appliance API flow is tested, documented, explicitly gated,
and reviewed.

Use [move-lab-proof.md](move-lab-proof.md) to validate redacted non-production
Move appliance evidence after lab testing.
