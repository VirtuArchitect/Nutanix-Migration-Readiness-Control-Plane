# Change Board Evidence

`change-board-evidence.md` is generated with every assessment. It is the
redacted Markdown packet intended for operator and change-board review.

Validate the generated evidence against `assessment.json`:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-change-board-evidence `
  --evidence outputs\sample-assessment\change-board-evidence.md `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks required sections, executive summary counts, collection
audit proof, read-only API paths, migration waves, workload readiness details,
generated finding actions, redaction markers, and zero mutating collection
calls.

`change-gate` runs the same validation automatically. The evidence remains a
review artifact; it does not execute migration actions or contact endpoints.
