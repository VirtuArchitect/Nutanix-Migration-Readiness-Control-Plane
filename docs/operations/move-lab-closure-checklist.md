# Move Lab Closure Checklist

Every assessment writes `move-lab-closure-checklist.md` so operators can see
the approved Nutanix Move lab proof chain before the final lab window.

The checklist is not appliance proof. It is an operator-facing closeout map for
the remaining external MVP gap: reviewed dry-run payload, submit-readiness
validation, capture-kit validation, approved transcript validation, approved
proof validation, final evidence intake, and final gate reruns.

## Generated Artifact

`write_assessment` creates the checklist in the assessment directory and the
evidence manifest records its size and SHA-256 hash. `change-gate` validates
that the file still includes:

- `nmrcp_move_submit_readiness_v1`.
- `nmrcp_move_lab_transcript_validation_v1`.
- `nmrcp_move_lab_proof_validation_v1`.
- `proof_scope=approved_lab_move_appliance`.
- `nmrcp_move_lab_evidence_intake_v1`.
- final `summarize-gates`, `change-gate`, `mvp-audit`, and `package-handoff`
  reruns with both `--move-proof` and `--move-lab-evidence-intake`.

The validator also rejects stale closeout command flags. Generated
`summarize-gates`, `change-gate`, and `package-handoff` examples must use
`--dir`, while `mvp-audit` must use `--assessment-dir` and `--out`.

## Operator Use

Review the checklist before an approved non-production lab Move appliance proof
window. Stop if any target is production, if evidence is unredacted, if proof
validation is not `status=pass` with approved scope, or if final gates are run
with approved proof but without passing evidence intake.

When supplied to `package-mvp-proof`, the checklist is archived as
`proof/move-lab-closure-checklist.md` and verified with the same contract.
