# Application Map Import

## Purpose

`import-app-map` converts a structured application dependency map into the
standard dependency CSV used by readiness scoring, dependency gates, migration
sequencing, runbooks, and Move planning.

Use this when a CMDB, application discovery tool, monitoring platform, or
migration factory exports application-to-database, application-to-service, or
application-to-external-system relationships before you have a hand-curated
dependency CSV.

## Command

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli import-app-map `
  --map examples\sample_app_map.json `
  --out outputs\app-map-dependencies.csv
python -m nmrcp.cli enrich-dependencies `
  --inventory examples\sample_inventory.json `
  --dependencies outputs\app-map-dependencies.csv `
  --out outputs\app-map-inventory.json
python -m nmrcp.cli assess `
  --inventory outputs\app-map-inventory.json `
  --out outputs\app-map-assessment
```

## JSON Shape

The adapter accepts `nmrcp_app_map_v1` JSON with either nested applications,
flat edges, or both:

```json
{
  "schema_version": "nmrcp_app_map_v1",
  "applications": [
    {
      "source_id": "vm-1001",
      "source_name": "pilot-web-01",
      "dependencies": [
        {
          "name": "pilot-db-01",
          "id": "vm-1002",
          "type": "database",
          "owner": "Platform Team",
          "criticality": "medium"
        }
      ]
    }
  ],
  "edges": [
    {
      "source_name": "erp-app-01",
      "target_name": "erp-db-01",
      "relationship": "database",
      "owner": "Database Team",
      "criticality": "critical"
    }
  ]
}
```

## Output

The command writes the same dependency CSV contract used by
`enrich-dependencies`:

```text
source_id,source_name,dependency_name,dependency_id,dependency_type,owner,criticality,protocol,ports,direction,validation_method,notes
```

Records require `source_id` or `source_name` plus a dependency name. Duplicate
source/dependency pairs are collapsed before writing.
Connectivity fields are optional, but when supplied they feed
`connectivity-checklist.csv` for firewall, DNS, routing, and application
reachability validation.

## Security Notes

Application maps can expose business topology, upstream and downstream service
names, database ownership, security zones, and external-provider dependencies.
Treat app-map input and converted dependency CSV files as sensitive migration
evidence.
