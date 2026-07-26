# Inventory Coverage

`inventory-coverage.csv` is generated with every assessment. It shows whether
required migration facts were present, partial, or missing for each workload.

## Covered Fields

- owner
- tier
- guest OS
- CPU, memory, and disk capacity
- networking and VLAN hints
- guest identity, including DNS/hostname and valid guest IP evidence
- snapshot facts, including oldest snapshot age when available
- VMware Tools and VirtIO facts
- backup proof
- vendor support
- application owner approval evidence
- rollback owner evidence
- dependencies

## Coverage Score

Each workload gets a coverage percentage:

- present fields count fully.
- partial nested fields count half.
- missing fields count zero.

Coverage is evidence of data quality. It does not approve migration by itself.
Use low coverage to drive follow-up collection, CMDB enrichment, or application
owner review before scheduling.

## Validate

Validate the coverage artifact directly:

```powershell
python -m nmrcp.cli validate-inventory-coverage `
  --coverage outputs\sample-assessment\inventory-coverage.csv `
  --move-plan outputs\sample-assessment\nutanix-move-plan.csv
```

When the Move plan is supplied, included workloads fail validation if critical
coverage fields are missing or partial. Critical fields are owner, guest OS,
networking, guest identity, tools, backup, storage, application-owner approval,
and rollback owner.

`change-gate` runs the same validation automatically. Held workloads with low
coverage warn, but included workloads with critical gaps fail before handoff.
The same coverage signal is also copied into `what-will-break-report.csv` as
coverage percent, coverage gaps, and coverage risk so app owners can see when a
workload has no detected finding but incomplete inventory could still hide
migration breakage.
