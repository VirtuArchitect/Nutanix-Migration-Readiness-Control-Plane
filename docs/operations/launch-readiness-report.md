# Launch Readiness Report

`launch-readiness-report` turns a verified MVP proof package into a concise
partner, MSP, customer, or change-board status report. It does not replace the
proof package or closure report; it summarizes them into an external-facing
readiness posture.

```powershell
python -m nmrcp.cli launch-readiness-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --repo-url https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --out outputs\smoke-launch-readiness-report.md `
  --json-out outputs\smoke-launch-readiness-report.json

python -m nmrcp.cli validate-launch-readiness-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --report outputs\smoke-launch-readiness-report.md `
  --json-report outputs\smoke-launch-readiness-report.json
```

The report includes:

- the product value statement: "Know exactly what will break before you migrate
  from VMware to Nutanix",
- proof package verification status,
- MVP requirement status from `mvp-audit`,
- proof-role status from `summarize-mvp-proof`,
- nested handoff package role counts from the packaged handoff manifest,
- closure summary counts for open items, blocking items, required evidence
  schema IDs, closeout command lines, and residual risks,
- open closure items from `mvp-closure-report`,
- an explicit external handoff decision and blocker list so a valid
  internal-review report cannot be mistaken for approved external handoff,
- closeout commands from `mvp-closure-report`,
- residual risks and next actions.

When approved Move proof is still open, the Markdown report includes a
`Closeout Commands` section and the JSON report includes `closeout_commands`.
Those commands are a lab-only action map for closing the proof package; they
are not permission to run against production, bypass the generated request
artifacts, or claim external handoff before approved proof and evidence intake
pass. The refreshed `package-mvp-proof` command includes
`--move-lab-runbook` so launch reviewers keep the validated lab procedure
alongside proof validation, evidence intake, source collection plan, requests,
and handoff evidence.
The refreshed `mvp-audit` and `package-mvp-proof` commands also preserve
`--assessment-intake outputs\assessment-intake.csv` and
`--live-proof outputs\source-collection\live-proof-validation.json`, keeping the
read-only collection proof attached while the Move proof gap is closed. The
package refresh also carries `--source-collection-plan
outputs\source-collection-plan.md` so the no-contact collection checklist does
not disappear from the final reviewer package.
The refreshed `package-handoff` command includes
`--move-lab-readiness-packet` so the receiver archive keeps the same pre-lab
operator packet that the proof package verifies.
The closeout sequence generates `outputs\move-lab-proof.approved.json` with
`generate-approved-move-lab-proof` from the validated transcript before running
`validate-move-lab-proof`, which keeps transcript hashes and approval metadata
machine-derived.
The closeout sequence then runs `verify-mvp-proof`, `summarize-mvp-proof`,
`validate-mvp-proof-summary`, `validate-mvp-closure-report`,
`launch-readiness-report`, and
`validate-launch-readiness-report` so the closure and launch reports are checked
against the refreshed proof package.
The non-JSON CLI output also prints the nested handoff role count and handoff
readiness packet status, external handoff decision, plus blocking open-item and
required-evidence schema ID counts and ID list, so operators can see
receiver-archive and closeout evidence without opening the JSON report. The
Markdown report includes `Required Evidence IDs` and `External Handoff Blockers`
sections for the same reason.
The validator treats equivalent relative and absolute package paths as the same
package reference, while still rejecting stale readiness, proof role, open item,
external handoff decision, blocker list, closeout command, residual-risk
content, compact summary count lines, and Markdown reports that omit any
required evidence schema ID listed in the JSON `closure_summary`, any JSON
external handoff blocker, or any JSON closeout command line.
The local smoke runner regenerates and validates launch readiness at the end of
the full proof rehearsal so `outputs\smoke-launch-readiness-report.*` matches
the final smoke proof package.

## Readiness Status

- `ready_for_external_handoff`: proof package verifies, MVP closure has no open
  blocking items, and external handoff can proceed.
- `ready_for_internal_or_partner_review`: proof package verifies, but one or
  more blocking external proof gaps remain. This is the expected status when
  simulated Move proof is packaged.
- `review_ready_with_residual_risk`: no blocking items remain, but residual
  risks still need review or formal acceptance.
- `blocked`: the MVP proof package itself failed verification.

The current local MVP can be shared for internal or partner review when the
proof package verifies. It must not be described as ready for final external
handoff until approved non-production Nutanix Move appliance proof and passing
evidence intake are supplied.
