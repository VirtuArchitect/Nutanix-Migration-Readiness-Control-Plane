# Operator Portal

`operator-portal.html` is generated with every assessment. It is a
self-contained local landing page for migration operators, partners, and change
reviewers.

The portal links the core artifacts an operator naturally opens first:

- `operator-dashboard.html`
- `operations-console.html`
- `operator-report.html`
- `executive-readiness-brief.md`
- `change-board-evidence.md`
- `migration-runbook.md`
- `nutanix-move-plan.csv`
- `move-staging-brief.md`
- `pre-post-validation-checklist.md`
- `source-endpoint-evidence-request.md`
- `move-lab-closure-checklist.md`
- `move-lab-evidence-request.md`
- `what-will-break-brief.md`
- `external-proof-plan.md`
- `evidence-manifest.json`

Validate the generated portal against `assessment.json`:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-operator-portal `
  --portal outputs\sample-assessment\operator-portal.html `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the HTML shell, `nmrcp_operator_portal_v1` payload schema,
summary counts, visible readiness metric cards, proof posture workload and wave
counts, artifact launchpad payload entries, visible artifact links, titles,
descriptions, required local artifact presence, redacted evidence posture,
approved Move proof contract visibility, and sample endpoint or email leakage.
The proof posture section names
`nmrcp_external_proof_plan_v1`,
`proof/external-proof-plan.json`,
`nmrcp_move_lab_proof_validation_v1` and
`nmrcp_move_lab_evidence_intake_v1` so the first local reviewer surface matches
the closure and launch readiness reports. `external-proof-plan.md` is an
optional closeout artifact because it is generated after the assessment, but
the portal still links it and preserves the boundary that external handoff
readiness must not be packaged until approved endpoint and Nutanix Move lab
evidence validate.

`change-gate` runs the same validation automatically. The portal is local-only,
does not require a web server, and does not contact vCenter, Prism Central, AHV,
NC2, Nutanix Move, or external services.
