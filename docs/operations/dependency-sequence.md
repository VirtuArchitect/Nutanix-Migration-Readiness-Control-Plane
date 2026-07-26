# Dependency Sequence

`dependency-sequence.csv` is generated with every assessment. It lists included
workloads in dependency-aware order so migration teams can stage internal
dependencies before workloads that rely on them.

## Columns

- `sequence`: dependency-aware order number.
- `workload_id`: source workload identifier.
- `name`: source workload name.
- `owner`: workload owner.
- `readiness`: current readiness state.
- `dependency_count`: number of declared dependencies on the workload.
- `notes`: generated sequencing note.

Validate the sequence against the canonical assessment before handoff:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-dependency-sequence `
  --sequence outputs\sample-assessment\dependency-sequence.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`assessment.json` includes a redacted `dependency_sequence_context` block so the
validator can verify sequence order and dependency counts without reopening raw
inventory. The validator also checks each context workload's name, owner, and
readiness against the canonical `assessments` rows so stale context cannot make
a held workload look ready or move ownership to the wrong team. `change-gate`
runs the same validation automatically.
