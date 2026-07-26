# Workload Metadata Enrichment

Workload metadata enrichment merges CMDB, application-owner, or migration-factory
CSV data into normalized inventory before scoring.

## Commands

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli enrich-metadata `
  --inventory examples\sample_inventory.json `
  --metadata examples\sample_metadata.csv `
  --out outputs\metadata-inventory.json
```

Metadata can also be applied directly during assessment:

```powershell
python -m nmrcp.cli assess `
  --inventory examples\sample_inventory.json `
  --metadata examples\sample_metadata.csv `
  --out outputs\metadata-assessment
```

Generic CMDB, service catalog, or application-owner CSV exports can be converted
to the normalized metadata format first:

```powershell
python -m nmrcp.cli import-cmdb-metadata `
  --export examples\sample_cmdb_export.csv `
  --out outputs\cmdb-metadata.csv
python -m nmrcp.cli enrich-metadata `
  --inventory examples\sample_inventory.json `
  --metadata outputs\cmdb-metadata.csv `
  --out outputs\cmdb-metadata-inventory.json
```

## CSV Columns

```text
source_id,source_name,owner,tier,tags,backup_protected,backup_last_success_hours,vendor_support,virtio_ready,application_owner_approved,rollback_owner,notes
```

`source_id` or `source_name` is required for matching. Unmatched records are
retained in `unmatched_metadata` and counted in source metadata.

## CMDB Import Columns

`import-cmdb-metadata` accepts common export headers and maps them into the
normalized columns above. Supported aliases include:

- Workload identity: `source_id`, `vm_id`, `vm_uuid`, `uuid`, `ci_id`,
  `source_name`, `vm_name`, `hostname`, `server_name`, `ci_name`.
- Ownership: `owner`, `application_owner`, `app_owner`, `service_owner`,
  `business_owner`, `support_group`.
- Criticality: `tier`, `criticality`, `business_criticality`,
  `business_tier`, `service_tier`.
- Operational readiness: `backup_status`, `backup_age_hours`,
  `target_support`, `virtio_ready`, `drivers_ready`, `migration_approved`,
  `rollback_owner`, `dr_owner`.

The importer rejects rows containing endpoint URLs or secret-like assignments
such as `password=`, `secret=`, `token=`, or `api_key=`. Keep raw exports local
and share only reviewed, redacted evidence.

## Supported Updates

- `owner`
- `tier`
- `tags`
- `backup.protected`
- `backup.last_success_hours`
- `vendor_support`
- `tools.virtio_ready`
- `governance.application_owner_approved`
- `governance.rollback_owner`
- `metadata_notes`

## Security Notes

Metadata files can include application names, ownership, support status, backup
posture, and business criticality. Treat them as sensitive migration data and
keep them in the approved migration workspace.
