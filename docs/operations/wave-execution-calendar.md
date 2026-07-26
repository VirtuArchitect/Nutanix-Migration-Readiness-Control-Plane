# Wave Execution Calendar

`wave-execution-calendar.csv` is generated with every assessment. It turns the
readiness wave plan into an operator-facing execution calendar with window type,
go/hold status, candidate and held workloads, owner groups, entry gate, exit
gate, required actions, and evidence references.

The artifact is planning evidence only. It does not create calendar events,
schedule migrations, or call Nutanix Move.

## Validate

```powershell
python -m nmrcp.cli validate-wave-execution-calendar `
  --calendar outputs\sample-assessment\wave-execution-calendar.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validator. The CSV must match calendar rows
recomputed from the `assessments` and `waves` in `assessment.json`, and the
embedded `wave_execution_calendar_context` must match those same recomputed
rows. This prevents stale or edited context from turning a hold or blocked wave
into a schedulable Move window. Validation also fails closed when assessment
waves reference unknown workload IDs or place the same workload in multiple
waves, so execution windows cannot be scheduled from invented or duplicated
wave membership.

## Columns

- `execution_sequence`: generated wave order.
- `wave`: migration wave name.
- `window_type`: pilot/standard, compatibility review, remediation review, or
  blocked no-move window.
- `move_staging_status`: `ready`, `conditional`, or `hold`.
- `candidate_workloads` and `held_workloads`: workload names by scheduling
  posture.
- `owners`: workload owner groups included in the wave.
- `entry_gate`: proof required before opening the window.
- `exit_gate`: proof required to leave the review window.
- `operator_actions`: scheduling guidance.
- `evidence_refs`: local evidence artifacts to attach or inspect.

## Operating Notes

Use the calendar after assessment review and before Move staging. Rows with
`move_staging_status=hold` should not become migration windows until remediation
or risk acceptance evidence is recorded and the assessment is rerun.
