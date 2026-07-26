# Assessment Intake

`generate-assessment-intake` creates a customer or partner kickoff checklist for
an NMRCP assessment. It records migration scope and required local-safety
acknowledgements before source collection or evidence packaging.

```powershell
python -m nmrcp.cli generate-assessment-intake `
  --out outputs\assessment-intake.csv
```

Fill the required `value` cells, then validate it:

```powershell
python -m nmrcp.cli validate-assessment-intake `
  --intake outputs\assessment-intake.csv
```

For approved live collection, pass the completed intake into `collect-sources`:

```powershell
python -m nmrcp.cli source-collection-plan `
  --intake outputs\assessment-intake.csv `
  --out outputs\source-collection-plan.md
python -m nmrcp.cli validate-source-collection-plan `
  --plan outputs\source-collection-plan.md `
  --intake outputs\assessment-intake.csv
python -m nmrcp.cli collect-sources `
  --assessment-intake outputs\assessment-intake.csv `
  --out-dir outputs\source-collection
```

The collection command validates the intake before connecting to vCenter or
Prism Central. It writes only validation metadata, warnings, row count, and the
intake file SHA-256 into collection proof. Intake field values are not copied
into `collection-summary.json` or `collection-proof-manifest.json`.
The source collection plan is generated from the same intake so operators can
review scope, local secret handling, proof outputs, and stop conditions without
serializing endpoint values or credentials into the brief.

The validator fails closed when:

- required kickoff fields are missing or empty,
- migration target is not `ahv`, `nc2`, or `both`,
- local-safety acknowledgements are not set to `true`,
- a value appears to contain an endpoint URL or secret-style assignment.

The required acknowledgements are:

- `secrets_stay_local_ack`,
- `redacted_evidence_ack`,
- `read_only_collection_ack`,
- `no_production_mutation_ack`.

The intake file is not a secret store. Keep endpoint URLs, usernames,
passwords, tokens, support bundles, and raw customer exports out of it. Use
environment variables and local source files for live collection.

The sample filled intake is available at `examples/sample_assessment_intake.csv`.
It intentionally marks `approved_move_lab_available=false`, so the MVP closure
report and launch readiness report still keep final external handoff blocked
until approved non-production Nutanix Move proof is captured.
