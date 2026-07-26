# External Proof Gap Plan

`external-proof-plan` creates a non-mutating closeout plan for the two remaining
external MVP proof gates: approved read-only vCenter/Prism Central evidence and
approved non-production Nutanix Move appliance evidence.

Generate the plan from the current repository state:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli external-proof-plan `
  --repo-root . `
  --out outputs\external-proof-plan.md `
  --json-out outputs\external-proof-plan.json
```

Validate it before branch-owner or operator review:

```powershell
python -m nmrcp.cli validate-external-proof-plan `
  --repo-root . `
  --report outputs\external-proof-plan.md `
  --json-report outputs\external-proof-plan.json
```

When approved proof files exist, pass them to both commands:

```powershell
python -m nmrcp.cli external-proof-plan `
  --repo-root . `
  --assessment-intake outputs\assessment-intake.csv `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --move-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake-validation.json `
  --out outputs\external-proof-plan.md `
  --json-out outputs\external-proof-plan.json
```

`blocked_until_external_evidence` is expected until both proof steps pass. The
plan does not contact vCenter, Prism Central, Nutanix Move, AHV, or NC2. It also
does not stage, commit, push, publish, open a pull request, or mutate
infrastructure.

The required closeout contracts are:

- `nmrcp_live_endpoint_proof_v1`
- `nmrcp_move_lab_proof_validation_v1`
- `nmrcp_move_lab_evidence_intake_v1`

Do not claim external handoff readiness until the plan validates with both proof
steps at `pass` and the product-readiness gate is rerun with the same approved
proof paths.
