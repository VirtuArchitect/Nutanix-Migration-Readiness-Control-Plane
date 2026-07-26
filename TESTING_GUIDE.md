# Testing Guide

## Standard Checks

```powershell
$env:PYTHONPATH = "src"
Get-ChildItem src/nmrcp/*.py | ForEach-Object { python -m py_compile $_.FullName }
python -m unittest discover -s tests
python scripts/security_scan.py
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

## Smoke Test

The smoke test runs the CLI against sample inventory/dependency data, validates
an RVTools import and its collection audit, runs the simulated live collector
HTTP smoke, validates the simulated vCenter and Prism audit blocks, writes
explicit vCenter network inventory evidence, drafts Prism capacity from the
simulated cluster list, proves vCenter snapshot timestamp to oldest-age
normalization, proves vCenter VMware Tools version-status normalization,
generates and validates the assessment intake preflight, writes a redacted
live-readiness proof, imports a generic CMDB metadata export, validates the Move plan,
validates target capacity fit, generates a dry-run Move payload, validates draft
and approved sign-offs, runs `doctor`, and verifies that the expected evidence
artifacts, including `migration-runbook.md`, are created under `outputs/smoke`.
It also validates `operator-portal.html`, `prism-category-mapping.csv`, and
`stakeholder-communication-plan.csv`, validates `what-will-break-report.csv`,
validates `wave-execution-calendar.csv` and `partner-handoff-matrix.csv`,
validates `move-lab-evidence-request.md` and
`source-endpoint-evidence-request.md`, requires `operator-dashboard.html`,
packages and verifies the evidence bundle plus the final handoff package with
approved sign-offs, packages and verifies the MVP proof bundle, writes the MVP
closure report, writes the launch readiness report, proves the Move lab proof
workflow can rerun over generated outputs, then runs the one-command assessment
workflow. Generated evidence is also scanned with `review-evidence`.
The PowerShell smoke runner wraps native `python` and nested `powershell`
commands and aborts on the first nonzero exit code, so a failed gate cannot be
hidden by later artifact generation.

The GitHub CI smoke mirrors the same hosted-safe proof posture with Linux
commands: it validates assessment intake, live proof, Move capture-kit evidence,
submit-readiness, transcript validation, simulated proof validation, a hosted
generated approved proof rehearsal with evidence intake, warning acceptance,
handoff package verification, MVP audit, MVP proof package verification, proof
summary, closure report generation, and launch readiness report generation.
Real Nutanix Move appliance behavior remains an explicit external proof gap
until an approved non-production lab run is supplied.

## Security Scan

`scripts/security_scan.py` is a dependency-free guardrail for committed content.
It fails on private-key blocks, AWS-style access keys, and literal secret
assignments. It intentionally allows the synthetic test strings used to verify
redaction behavior.

The scan does not replace human review. Application names, ownership labels,
network names, datastore names, storage topology, and business context can be
sensitive without matching a secret pattern.

## Test Strategy

- Unit-test deterministic readiness rules.
- Unit-test power-state readiness review for powered-off or suspended
  workloads.
- Unit-test snapshot age, VMware Tools status, and backup recovery-point age
  scoring rules.
- Unit-test vCenter and RVTools snapshot timestamp normalization into
  oldest-snapshot age.
- Unit-test vCenter and RVTools VMware Tools status normalization.
- Unit-test storage posture scoring for raw device mappings, shared disks,
  independent disks, encrypted disks, and low datastore free space.
- Unit-test readiness policy loading, validation, and CLI use.
- Unit-test normalized inventory validation and strict-mode behavior.
- Unit-test assessment intake generation, required kickoff fields, local-safety
  acknowledgements, and endpoint/secret-looking value refusal.
- Unit-test generic CMDB metadata import, normalized metadata output, and
  endpoint/secret-looking value refusal.
- Unit-test redaction before evidence expansion.
- Unit-test CLI artifact creation.
- Unit-test HTML operator report generation and redacted source rendering.
- Unit-test HTML operator portal generation, artifact links, redacted posture,
  and CLI validation.
- Unit-test HTML operator dashboard generation, local work-queue controls, and
  redacted source posture.
- Unit-test migration runbook generation and manifest inclusion.
- Unit-test inventory coverage generation and manifest inclusion.
- Unit-test evidence manifest generation and SHA-256 hash shape.
- Unit-test evidence bundle packaging, verification, and tamper detection.
- Unit-test evidence redaction review pass/fail behavior and change-gate
  integration.
- Unit-test change gate pass/fail behavior over evidence, bundles, Move plans,
  and validation results.
- Unit-test handoff package creation, manifest privacy, verification, and
  missing-entry detection.
- Unit-test one-command assessment workflow success and invalid-inventory
  refusal.
- Unit-test dependency CSV enrichment and unmatched-record tracking.
- Unit-test workload metadata enrichment, CMDB metadata conversion, and
  unmatched-record tracking.
- Unit-test dependency gates and dependency-aware sequencing.
- Unit-test Move plan validation, including blocked-workload fail-closed cases.
- Unit-test review-only Prism/NCM category mapping generation, validation, and
  change-gate tamper detection.
- Unit-test dry-run Move payload generation and invalid-plan refusal.
- Unit-test source network validation against collected vCenter network
  inventory.
- Unit-test target network mapping pass/fail behavior and Move payload refusal
  on unmapped included networks.
- Unit-test target capacity-fit pass/fail behavior and CSV output.
- Unit-test Prism capacity draft normalization and CLI output.
- Unit-test validation-results template generation and fail-closed validation.
- Unit-test collector commands with mocked clients.
- Unit-test endpoint probe commands with mocked clients and redacted output.
- Unit-test live-readiness proof generation, fail-closed required endpoints, and
  secret/endpoint redaction.
- Unit-test offline RVTools CSV import and CLI output.
- Unit-test vCenter, Prism, and RVTools storage normalization.
- Unit-test storage-owner sign-off generation and validation.
- Unit-test collection audit validation for live collectors, RVTools, count
  consistency, mutating-call refusal, and endpoint/credential leakage.
- Unit-test `doctor` output so secret values are not printed.
- Run CI over compile, unit tests, security scan, simulated live collector
  smoke, full smoke, evidence bundle, redaction review, validation results,
  sign-off validation, network-mapping validation, capacity-fit validation,
  change gates, live-readiness proof generation, Move lab capture/proof
  evidence, hosted generated-proof rehearsal with evidence intake, warning
  acceptance, handoff package verification with final sign-offs, MVP proof
  package verification, MVP closure report generation, launch readiness report
  generation, plus the one-command assessment workflow.
- Add mocked HTTP response tests before expanding connector endpoint coverage.
