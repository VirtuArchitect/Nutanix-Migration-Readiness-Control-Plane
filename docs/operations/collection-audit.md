# Collection Audit Metadata

Normalized inventory files include a non-secret `source.collection_audit` block
with schema `nmrcp_collection_audit_v1`. It helps operators prove how an
inventory was created before the assessment evidence is generated.

The audit block is intentionally not a credential record. It does not duplicate
endpoint URLs, usernames, passwords, or RVTools source labels.

`assessment.json`, `change-board-evidence.md`, and `operator-report.html`
include this audit metadata after source redaction. The change-board and
operator artifacts also promote it into a human-readable "Collection Audit
Proof" section so approvers can verify collection mode, limits, counts, and
mutation posture without parsing nested JSON.

## Live Collectors

vCenter audit metadata records:

- `mode=read-only`
- `/api/session`, `/api/vcenter/vm`, and `/api/vcenter/vm/{vm}` path names
- summary VM count
- configured detail limit
- detail records collected
- `credential_storage=not_persisted`
- `mutating_calls=0`

Prism Central audit metadata records:

- `mode=read-only`
- `/api/nutanix/v3/vms/list`
- configured page size and maximum pages
- entity count returned
- `post_paths_allowlisted=true`
- `credential_storage=not_persisted`
- `mutating_calls=0`

Prism v3 list operations use POST, so mutation safety is proved by the
allow-listed path and review of connector behavior rather than by HTTP verb
alone.

## Offline RVTools

RVTools audit metadata records:

- `mode=offline-import`
- observed `v*.csv` filenames
- normalized workload count
- `credential_storage=not_used`
- `endpoint_configured=false`
- `mutating_calls=0`

The source CSVs can still contain sensitive infrastructure inventory. Keep them
inside the approved migration workspace and do not commit customer exports.

## Evidence Review

Validate collected inventory audit metadata before assessment:

```powershell
python -m nmrcp.cli validate-collection-audit --inventory outputs\vcenter-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\prism-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\rvtools-inventory.json
```

The validator fails closed when the audit block is missing, has the wrong schema,
records mutating calls, stores credential material, duplicates the source
endpoint or hostname, or reports source-specific counts that do not match the
inventory workload count.

Before sharing evidence, confirm:

- `Collection Audit Proof` is present in `change-board-evidence.md`.
- `operator-report.html` shows schema `nmrcp_collection_audit_v1`.
- `Mutating calls` is `0`.
- Endpoint URLs, usernames, passwords, and RVTools source labels are not present
  in the audit section.
- `review-evidence` passes with no findings.
