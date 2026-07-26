# Stakeholder Communication Plan

`stakeholder-communication-plan.csv` is generated with every assessment. It
groups workloads by owner and wave so a partner, MSP, or migration lead can see
which audience must be contacted before a workload enters Nutanix Move staging.

The artifact is local and review-only. NMRCP does not send messages, open
tickets, or call collaboration tools from this plan.

## Validate

```powershell
python -m nmrcp.cli validate-stakeholder-comms `
  --plan outputs\sample-assessment\stakeholder-communication-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validator. The CSV must match rows recomputed from
canonical `assessment.json` workload assessments and waves, and the embedded
`stakeholder_comms_context` must match those same recomputed rows. Validation
fails closed when context drifts, waves reference unknown workload IDs, or the
same workload appears in multiple waves.

## Columns

- `owner`: workload owner from inventory or metadata.
- `wave`: planned migration wave.
- `audience`: owner-scoped roles to include in review.
- `workload_ids` and `workload_names`: workloads covered by the row.
- `readiness_summary`: owner and wave readiness rollup.
- `communication_stage`: review stage derived from readiness.
- `message_intent`: plain-language purpose for the outreach.
- `evidence_refs`: local evidence files to attach or cite.
- `required_action`: operator action before scheduling.

## Operating Notes

Use the plan after assessment review and before Move staging. Blocked and
remediation rows should not be scheduled until the owner response, remediation
owner, or risk-acceptance path is captured in the handoff evidence.
