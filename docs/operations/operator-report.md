# Operator Report

`operator-report.html` is generated with every assessment. It is a
self-contained local HTML report for operators, partners, and change boards.

Validate the generated report against `assessment.json`:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-operator-report `
  --report outputs\sample-assessment\operator-report.html `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks report sections, exact summary metric cards including
unmatched dependency count, collection audit proof, read-only API paths, wave
cards, workload readiness cards, generated finding actions, redacted source
metadata, and sample secret or endpoint leakage.

`change-gate` runs the same validation automatically. The report remains a local
review artifact; it does not require a web server or contact endpoints.
