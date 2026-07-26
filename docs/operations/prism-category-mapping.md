# Prism Category Mapping

`prism-category-mapping.csv` is generated with every assessment. It turns source
ownership, tier, readiness, and tags into a review-only Prism/NCM category plan
before Nutanix Move staging.

Validate the generated mapping against `assessment.json`:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-prism-categories `
  --mapping outputs\sample-assessment\prism-category-mapping.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The mapping uses schema `nmrcp_prism_category_mapping_v1` and proposes
categories such as:

- `NMRCP:Owner`
- `NMRCP:Tier`
- `NMRCP:Readiness`
- `NMRCP:WaveIntent`
- `NMRCP:SourceTags`

`apply_scope` is always `review_only_prism_category_plan`. The artifact does
not apply categories and does not call Prism Central, NCM, AHV, NC2, or Nutanix
Move. Platform owners should review the CSV and decide whether to translate it
into approved target categories after the migration wave is cleared.

`change-gate` runs the same validation automatically. Tampering with category
assignments, review status, or apply scope fails the gate. The embedded
`prism_category_context` must also match canonical `assessment.json` workload
ID, name, owner, and readiness before the review-only target governance plan is
trusted.
