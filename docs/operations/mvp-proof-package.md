# MVP Proof Package

`package-mvp-proof` creates a single zip containing the current product proof
posture: MVP audit, live endpoint proof, Move submit readiness, Move lab
capture kit, capture-kit validation, readiness packet, transcript validation,
Move lab proof validation, Move lab closure checklist, Move lab evidence
intake, source collection plan, source endpoint and Move lab evidence requests,
external proof gap plan, operator gate summary, and optionally the full handoff
package.

It is intended for internal review, partner handoff, or release readiness
reviews where reviewers need one integrity-checked bundle instead of a folder of
loose artifacts.

## Create

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli package-mvp-proof `
  --mvp-audit outputs\smoke-mvp-audit.json `
  --live-proof outputs\smoke-live-proof-validation.json `
  --move-submit-readiness outputs\smoke\move-submit-readiness.json `
  --move-lab-transcript outputs\smoke\move-lab-transcript-validation.json `
  --move-lab-proof outputs\smoke\move-lab-proof-validation.simulated.json `
  --move-lab-runbook outputs\smoke\move-lab-execution-runbook.md `
  --move-lab-closure-checklist outputs\smoke\move-lab-closure-checklist.md `
  --move-lab-capture-kit outputs\smoke\move-lab-capture-kit `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --move-lab-readiness-packet outputs\smoke\move-lab-readiness-packet.json `
  --source-collection-plan outputs\source-collection-plan.md `
  --source-endpoint-evidence-request outputs\smoke\source-endpoint-evidence-request.md `
  --move-lab-evidence-request outputs\smoke\move-lab-evidence-request.md `
  --external-proof-plan outputs\external-proof-plan.json `
  --operator-gate-summary outputs\smoke\operator-gate-summary.md `
  --handoff-package outputs\smoke-handoff-package.zip `
  --out outputs\smoke-mvp-proof-package.zip
```

## Verify

```powershell
python -m nmrcp.cli verify-mvp-proof --package outputs\smoke-mvp-proof-package.zip
```

Verification checks the package manifest, required file presence, role coverage,
role-to-archive-path mapping, duplicate roles, duplicate archive paths, file
sizes, SHA-256 hashes, and role-specific proof semantics. A valid package must
include the `mvp_audit` role, and packaged JSON proof roles must use the
expected schema and acceptable status for their role.
Packaged live endpoint proof must also include passing evidence checks for
live-readiness status/security, collection-summary privacy/schema,
assessment-intake binding, proof-manifest security/API scope, and matching
assessment-intake checksums. A stale JSON file that only declares
`status=pass` is rejected.
When a handoff package is nested in the MVP proof package, verification runs
the handoff verifier against that nested zip rather than only checking that it
is a readable archive.
The proof summary reports nested handoff state as `verified`, `invalid`,
`missing`, or `present_unverified`; closure reports only count proof roles as
verified when package verification passes.

## Contents

- `mvp-proof-manifest.json`: schema `nmrcp_mvp_proof_manifest_v1`.
- `proof/mvp-audit.json`: requirement-by-requirement MVP status.
- `proof/live-proof-validation.json`: optional live endpoint proof validation
  with collection-summary assessment-intake binding and proof-manifest checksum
  match checks.
- `proof/move-submit-readiness.json`: optional Move dry-run submit readiness.
- `proof/move-lab-transcript-validation.json`: optional redacted Move lab
  transcript validation.
- `proof/move-lab-proof-validation.json`: optional Move lab proof validation.
- `proof/move-lab-execution-runbook.md`: optional validated Move lab
  execution runbook.
- `proof/move-lab-closure-checklist.md`: optional Move lab proof closeout
  checklist.
- `proof/move-lab-transcript.template.json`: optional Move lab transcript
  capture template.
- `proof/move-lab-capture-checklist.md`: optional Move lab evidence capture
  checklist.
- `proof/move-lab-capture-kit-validation.json`: optional Move lab capture-kit
  validation proof.
- `proof/source-collection-plan.md`: optional validated source collection plan
  that keeps endpoint values and credentials out of the package while showing
  local secret handling, read-only collection sequence, required proof outputs,
  and stop conditions.
- `proof/move-lab-readiness-packet.json`: optional Move lab readiness packet.
- `proof/move-lab-evidence-intake.json`: optional final approved-lab evidence
  intake proof.
- `proof/source-endpoint-evidence-request.md`: optional validated read-only
  source endpoint collection request.
- `proof/move-lab-evidence-request.md`: optional validated approved Move lab
  proof-window request.
- `proof/external-proof-plan.json`: optional combined approved endpoint and
  Nutanix Move proof closeout plan.
- `proof/operator-gate-summary.md`: optional human-readable gate summary.
- `handoff/handoff-package.zip`: optional full handoff archive.

The verifier prints the roles found in the package so reviewers can distinguish
an integrity-clean partial proof package from a complete approved-lab package.
The summary also reads the nested handoff manifest and lists handoff package
role counts, including whether `move_lab_readiness_packet` is present in the
receiver archive without repeating every assessment artifact row.
Capture templates must remain `template_only_replace_after_lab_capture` inside
the proof package; approved evidence belongs in transcript validation and proof
validation artifacts. The capture template and checklist are treated as a pair:
packages that include only one of them fail verification.
When supplied, capture-kit validation must use
`nmrcp_move_lab_capture_kit_validation_v1`, `status=pass`, and no errors.
Capture-kit files and capture-kit validation are also treated as a set: a
package that includes either the template/checklist without validation, or
validation without the template/checklist, fails verification.
When supplied, the readiness packet must use
`nmrcp_move_lab_readiness_packet_v1`, `status=pass` or `status=warn`, and no
errors. This role keeps the pre-lab operator handoff hashes visible in the proof
zip; it is not approved appliance proof.
When supplied, Move lab evidence intake must use
`nmrcp_move_lab_evidence_intake_v1`, `status=pass`, and no errors. Complete
approved-lab proof packages should include this role so the closure report can
verify that raw transcript, validation files, completed proof, and capture-kit
validation were checked together.
When supplied, the external proof plan must use `nmrcp_external_proof_plan_v1`
and carry both approved read-only source endpoint proof and approved Nutanix
Move appliance proof steps. It may remain `blocked_until_external_evidence`
for internal review, but complete external handoff packages should carry
`ready_for_external_handoff`.
The smoke and CI proof workflows generate, validate, and package this plan as
`proof/external-proof-plan.json` so internal reviewers always see the combined
endpoint and Move proof closeout boundary before external handoff is claimed.
When supplied, live endpoint proof must use `nmrcp_live_endpoint_proof_v1`,
`status=pass`, no errors, and passing checks for the read-only live readiness
chain, collection summary privacy, assessment-intake binding, proof-manifest
security, API allowlist scope, and proof-manifest intake checksum match.
When supplied, the Move lab execution runbook must pass
`validate-move-lab-runbook`, including lab acknowledgement, production stop
conditions, redaction/secret handling, capture-kit validation, final
`validate-move-lab-evidence-intake`, and closeout reruns with both
`--move-proof` and `--move-lab-evidence-intake`.
When supplied, the Move lab closure checklist must pass the same contract used
by `change-gate`, including the approved-proof, transcript, evidence-intake,
and final gate rerun chain.
When supplied, source endpoint and Move lab evidence requests must pass the
same request validators used by `change-gate` and handoff verification. These
roles keep the approved collection/proof-window asks visible in the MVP proof
zip instead of relying only on the nested handoff package.
When supplied, the operator gate summary must pass
`validate-operator-gate-summary`, including required gate rows, allowed row
statuses, use guidance, and the proof-plus-intake consistency rule.
Launch readiness is generated after the package, so it is validated against the
package rather than archived inside it. Run `validate-launch-readiness-report`
with the package, Markdown report, and JSON report to catch stale or tampered
handoff readiness outputs.

## Summarize

```powershell
python -m nmrcp.cli summarize-mvp-proof `
  --package outputs\smoke-mvp-proof-package.zip `
  --out outputs\smoke-mvp-proof-summary.md

python -m nmrcp.cli validate-mvp-proof-summary `
  --package outputs\smoke-mvp-proof-package.zip `
  --summary outputs\smoke-mvp-proof-summary.md
```

The summary is a reviewer-facing Markdown report with package verification
status, role coverage, MVP requirement status, Move proof scope, and residual
risk. It intentionally reports the remaining approved Move appliance proof gap
without exposing lab appliance identifiers.
The non-JSON CLI summary also prints the nested handoff role count and handoff
readiness packet status so operators can confirm receiver-archive evidence at
the console before opening the Markdown or JSON artifacts.
`validate-mvp-proof-summary` rebuilds the summary from the current package and
checks the reviewer-facing Markdown for stale or tampered status, role, and
requirement rows.

The package accepts partial MVP audits, because partial is the correct state
until real approved lab Move evidence exists. It rejects failed MVP audits.

## Closure Report

```powershell
python -m nmrcp.cli mvp-closure-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --out outputs\smoke-mvp-closure-report.md `
  --json-out outputs\smoke-mvp-closure-report.json

python -m nmrcp.cli validate-mvp-closure-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --report outputs\smoke-mvp-closure-report.md `
  --json-report outputs\smoke-mvp-closure-report.json
```

The closure report turns the proof package into an action list for reviewers:
open MVP audit requirements, missing proof roles, simulated Move proof, package
integrity failures, and the exact evidence needed to move the package from
partial to externally handoff-ready.

For the cleanest closure report, generate `mvp-audit` after the evidence bundle
and final handoff package are available, and pass the final validation,
remediation, sign-off, approval-exception, operator-review, and capture-kit
validation files into the audit. If remaining change-gate warnings were
formally accepted, also pass the validated warning acceptance register. The Move
appliance proof gap remains separate: do not pass simulated Move proof as
`--move-proof` when claiming external handoff readiness. For approved lab Move
proof, include both `--move-proof` and `--move-lab-evidence-intake` in the MVP
audit and proof package before using the closure report as an external handoff
signal. The report names both
`nmrcp_move_lab_proof_validation_v1` and
`nmrcp_move_lab_evidence_intake_v1` as required evidence for the Move-ready plan
closure.

The report uses schema `nmrcp_mvp_closure_report_v1` when written as JSON. It
sets `ready_for_external_handoff=false` until blocking items are closed. A
simulated Move proof package remains valid for internal review, but the closure
report keeps it blocked on the approved lab Move appliance proof-plus-intake
evidence set. The closure report also includes compact nested handoff role
counts so reviewers can see what the receiver archive contains. Its JSON and
Markdown also include `closure_summary` counts for open items, blocking open
items, required evidence schema IDs, closeout command lines, and residual
risks. The same block lists the missing schema IDs, such as
`nmrcp_move_lab_proof_validation_v1` and
`nmrcp_move_lab_evidence_intake_v1`, giving dashboards a compact
external-handoff gate without parsing the full open-item table.
The non-JSON CLI closure output prints the same nested handoff role count and
handoff readiness packet status, plus blocking open-item and required-evidence
schema ID counts and ID list, for quick operator review. The Markdown closure
report includes a `Required Evidence IDs` section so reviewer packets remain
self-explanatory without opening JSON.
When that proof chain is still open, the Markdown report and JSON record also
include a `closeout_commands` sequence. Operators should treat those commands
as a lab-only closeout map, not as permission to run against production or to
skip `move-lab-closure-checklist.md`. The package command in that sequence
includes `--move-lab-runbook` so the validated lab procedure remains attached
to the refreshed proof package instead of being dropped during final closeout.
The refreshed `mvp-audit` and `package-mvp-proof` commands also carry
`--assessment-intake outputs\assessment-intake.csv` and
`--live-proof outputs\source-collection\live-proof-validation.json` forward, so
closing the Move proof gap does not accidentally drop the read-only collection
proof chain.
The same sequence now runs `generate-approved-move-lab-proof` after transcript
validation and before proof validation, so the approved proof JSON is derived
from clean transcript evidence rather than hand-copied.
The refreshed `package-handoff` command also includes
`--move-lab-readiness-packet` so the receiver archive carries the pre-lab
operator packet alongside proof validation and evidence intake.
The same sequence now reruns `verify-mvp-proof`, regenerates
`summarize-mvp-proof`, validates the refreshed proof summary with
`validate-mvp-proof-summary`, validates the refreshed closure report with
`validate-mvp-closure-report`, regenerates `launch-readiness-report`, and runs
`validate-launch-readiness-report`, so closeout is not complete until both
handoff-facing reports match the refreshed proof package.
Closure and launch validators compare the referenced package by resolved path,
so equivalent relative and absolute paths do not create false stale-report
failures. Other JSON and Markdown fields still have to match the current proof
package exactly, including compact closure summary count lines, every required
evidence schema ID listed in `closure_summary.required_evidence_ids`, and every
generated closeout command line.

The local `scripts\smoke.ps1` runner intentionally performs a final MVP proof
package, summary, closure report, and launch readiness refresh near the end of
the run. A passing smoke therefore leaves the reviewer-facing smoke artifacts
valid against the final `outputs\smoke-mvp-proof-package.zip`, even after later
workflow rehearsals regenerate intermediate proof files.

For operator execution, `scripts\move_lab_proof_workflow.ps1` can validate the
Move lab proof inputs, rebuild handoff, refresh the MVP audit, produce a
verified MVP proof package, rewrite the closure report, and validate
launch-readiness outputs in one approved lab pass. See
[move-lab-proof-workflow.md](move-lab-proof-workflow.md).
