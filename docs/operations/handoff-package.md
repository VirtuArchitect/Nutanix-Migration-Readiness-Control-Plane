# Handoff Package

`package-handoff` creates a single zip for migration handoff or closure
archives. It verifies the assessment evidence first, validates the Move staging
plan, and optionally includes the evidence bundle, final validation results,
final remediation tracker, final owner sign-offs, final approval exceptions,
and dry-run Move payload. When an operator review is supplied, it must be
approved before packaging.
When Move lab proof is supplied, it must be approved lab-appliance proof before
packaging, and the final Move lab evidence intake must be supplied with it so
external handoff carries the complete approved-lab proof set. When a Move lab
capture kit is supplied, its validation proof must be supplied with it so the
handoff carries the template, checklist, and preflight validation as one
reviewable set. When a Move lab readiness packet is supplied, it is archived as
pre-lab handoff evidence and validated before the package is accepted. When a
source collection plan is supplied, it is archived as the pre-access collection
brief and validated for the static source-plan contract before packaging.

## Create

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli package-handoff `
  --dir outputs\sample-assessment `
  --bundle outputs\sample-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json `
  --move-lab-capture-kit outputs\move-lab-capture-kit `
  --move-lab-capture-validation outputs\move-lab-capture-kit-validation.json `
  --move-lab-readiness-packet outputs\move-lab-readiness-packet.json `
  --source-collection-plan outputs\source-collection-plan.md `
  --move-payload outputs\sample-assessment\move-api-payload.dry-run.json `
  --out outputs\sample-handoff-package.zip
```

The package includes `handoff-manifest.json` with schema
`nmrcp_handoff_manifest_v1`. The manifest records each archived file path, role,
size, and SHA-256 hash. Local source paths are not written into the package.

## Verify

```powershell
python -m nmrcp.cli verify-handoff --package outputs\sample-handoff-package.zip
```

Verification checks that every file listed in the handoff manifest is present in
the zip and still matches its recorded size and SHA-256 hash. It also rejects
archive entries that are not listed in `handoff-manifest.json`, so hidden or
manually added files cannot ride along outside the reviewed manifest. It also
verifies handoff roles, duplicate archive paths, unique-role duplication,
required core assessment artifacts, nested evidence bundle readability,
approved Move lab proof semantics, approved-proof intake pairing, Move lab
evidence intake status, Move lab closure checklist contract, Move lab
capture-kit set completeness, capture-kit validation status, Move lab readiness
packet schema and flags, source collection plan privacy/static-contract guards,
and dry-run-only Move payload guards.

## Contents

- `assessment/`: core assessment artifacts from `evidence-manifest.json`.
- `bundles/evidence-bundle.zip`: optional previously verified evidence bundle.
- `validation/validation-results.csv`: optional final pre/post validation
  results, accepted only when all checks pass.
- `remediation/final-remediation-tracker.csv`: optional final remediation
  tracker, accepted only when no rows remain open.
- `signoffs/final-owner-signoffs.csv`: optional final owner sign-off matrix,
  accepted only when final sign-off validation passes.
- `signoffs/final-approval-exceptions.csv`: optional filled approval exception
  register, accepted only when every generated exception is closed with
  approval or waiver evidence and still matches the assessment baseline.
- `review/operator-review.csv`: optional operator/customer assessment review,
  accepted only when final operator-review validation passes.
- `assessment/move-lab-closure-checklist.md`: required generated assessment
  artifact, accepted only when the Move lab closure checklist contract passes.
- `move/move-lab-proof-validation.json`: optional approved non-production Move
  appliance proof, accepted only when scope is `approved_lab_move_appliance` and
  the transcript validation link check passes.
- `move/move-lab-evidence-intake.json`: required when approved Move lab proof
  is supplied, accepted only when schema is `nmrcp_move_lab_evidence_intake_v1`,
  status is `pass`, and intake errors are empty.
- `move/move-lab-transcript.template.json`: optional Move lab capture transcript
  template, accepted only as `template_only_replace_after_lab_capture` with
  production targets and mutation marked false.
- `move/move-lab-capture-checklist.md`: optional Move lab capture checklist.
- `move/move-lab-capture-kit-validation.json`: optional capture-kit validation
  proof, accepted only when schema is `nmrcp_move_lab_capture_kit_validation_v1`,
  status is `pass`, and validation errors are empty.
- `move/move-lab-readiness-packet.json`: optional pre-lab operator handoff
  packet, accepted only when schema is `nmrcp_move_lab_readiness_packet_v1`,
  status is `pass` or `warn`, required lab-only flags are set, required
  artifact roles are present, and packet errors are empty.
- `source/source-collection-plan.md`: optional pre-access source collection
  brief, accepted only when schema is `nmrcp_source_collection_plan_v1`,
  credentials and endpoint values are not serialized, commands remain
  read-only, proof outputs are listed, and no endpoint or secret-like material
  is present.
- `move/move-api-payload.dry-run.json`: optional review-only Move API payload.
  Verification rejects this artifact unless `dry_run_only` is `true` and
  `mutation_allowed` is `false`, even when the package hash matches the
  manifest.

## Review Notes

Run `change-gate` before creating the final package. The handoff package is an
archive and integrity wrapper; it does not submit actions to vCenter, Prism
Central, AHV, NC2, or Nutanix Move. A packaged capture kit is preflight evidence
for a later approved lab window; it is not proof that a real Move appliance
accepted or started any migration.
