# Executive Readiness Brief

`executive-readiness-brief.md` is generated with every assessment. It turns the
readiness model into a concise decision artifact for sponsors, migration
program leads, and change boards.

The brief includes:

- recommended decision.
- workload readiness posture.
- business-impact summary by tier.
- wave-level go/hold decisions.
- top readiness blockers.
- evidence required before approval.
- generated evidence references.

Validate the generated brief against `assessment.json`:

```powershell
python -m nmrcp.cli validate-executive-brief `
  --brief outputs\sample-assessment\executive-readiness-brief.md `
  --assessment outputs\sample-assessment\assessment.json
```

Use this brief as the front page for an evidence package. It does not replace
the detailed CSVs or gate output; it points reviewers to
`business-impact-summary.csv`, `wave-readiness-summary.csv`,
`migration-risk-register.csv`, `owner-risk-summary.csv`, and
`nutanix-move-plan.csv`.

When the brief says broad Move staging should not be approved, only explicitly
approved pilot workloads should proceed, and production handoff still requires
closed remediation evidence, owner sign-offs, rollback ownership, operator
review, redaction review, evidence-bundle verification, and approved Nutanix
Move lab appliance proof.

`change-gate` runs the same validation automatically and fails if the brief is
missing required sections, has counts that do not match `assessment.json`, omits
wave decision lines generated from workload membership, staging posture, and
held workload names, omits the Move lab proof requirement, or drops required
evidence references.
