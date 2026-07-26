# Operator Dashboard

`operator-dashboard.html` is generated with every assessment. It is a
self-contained local HTML work queue for migration operators.

Validate the embedded dashboard payload against `assessment.json`:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-operator-dashboard `
  --dashboard outputs\sample-assessment\operator-dashboard.html `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the HTML shell, `nmrcp_operator_dashboard_v1` payload
schema, summary counts, workload rows, wave assignments, Move staging intent,
dependency counts, unmatched dependency totals, finding actions, operator stop
conditions, and sample endpoint or email leakage.

`change-gate` runs the same validation automatically. The dashboard does not
require a web server and does not contact vCenter, Prism Central, AHV, NC2, or
Nutanix Move.
