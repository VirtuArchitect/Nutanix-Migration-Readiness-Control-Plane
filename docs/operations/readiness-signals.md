# Readiness Signals

The readiness engine is deterministic. It does not claim a workload is safe just
because it appears in inventory; it scores migration signals that operators can
verify and remediate.

## Current Signals

- Guest OS: missing or uncommon guest families require support research.
- Power state: powered-off, suspended, or unknown non-running states require
  live validation review before scheduling.
- NSX: NSX-backed networking blocks migration scheduling until mapping is done.
- VDS: distributed port groups require target network mapping.
- Storage posture: raw device mappings, shared or multi-writer disks,
  independent disks, encrypted disks, and source datastores below 15 percent
  free space create storage-owner review or blockers.
- Snapshots: any snapshot adds risk; snapshots older than seven days add a
  higher remediation finding.
- VMware Tools: missing tools weakens guest discovery and driver readiness.
- VMware Tools status: old, outdated, unsupported, or upgrade-required status
  adds risk.
- Guest identity: powered-on workloads without valid guest IP evidence or DNS
  or hostname evidence require follow-up before cutover validation.
- VirtIO readiness: VMware Tools without confirmed Nutanix VirtIO readiness
  requires preparation before cutover.
- Backup: missing backup proof is high risk.
- Backup age: protected workloads with a last successful recovery point older
  than 24 hours require fresh backup proof.
- Vendor support: critical workloads must declare support for the selected AHV
  or NC2 target.
- Governance: when governance metadata is supplied, missing application owner
  approval or rollback owner evidence adds high-risk findings.
- Dependencies: dependencies without owners add risk; internal dependencies
  that are not ready hold dependent workloads.

## Dependency Sources

Dependencies can come from dedicated CSV enrichment or from source metadata
hints discovered during collection/import. The vCenter, Prism, and RVTools
normalizers preserve declared hints from keys such as `dependency`,
`dependencies`, `depends_on`, and `application_dependencies`. Hints are useful
early discovery evidence, while the dependency CSV remains the authoritative
place to add dependency IDs, owners, criticality, and cleanup notes.
Application maps can be converted into dependency CSV records with
[application-map-import.md](application-map-import.md).

## Storage Posture

Normalized workloads can include a `storage` object:

```json
{
  "disk_count": 2,
  "thin_provisioned": true,
  "raw_device_mapping": false,
  "shared_disk": false,
  "independent_disk": false,
  "encrypted": false,
  "datastores": ["ds-prod"],
  "min_datastore_free_percent": 31
}
```

The vCenter normalizer derives this from disk detail payloads when those fields
are available. Prism inventory records native target disk/container posture.
RVTools imports derive disk count and available disk flags from `vDisk.csv`
columns when present.

## Snapshot Age Sources

The readiness engine uses `snapshots.oldest_days` when it is present. vCenter
detail payloads can provide snapshot lists or direct oldest-snapshot age fields.
RVTools imports derive `snapshots.oldest_days` and `snapshots.oldest_created_at`
from timestamp columns in `vSnapshot.csv`. If snapshot timestamps are missing or
unparseable, the import remains conservative by preserving snapshot count only.

## VMware Tools Sources

The readiness engine uses `tools.vmware_tools` and `tools.status` when present.
vCenter detail payloads can provide nested tools run state and version status;
those values are preserved in `tools.status`. RVTools imports combine the main
Tools column, version-status column, and running-status column when present.
Not-installed or not-running states are treated as missing tools. Upgrade-needed,
old, outdated, or unsupported states become `vmware_tools_outdated` findings.

## Guest Identity Sources

The readiness engine uses `guest_identity` when present. vCenter detail payloads
can provide guest identity, DNS name, host name, and IP address fields. Prism
inventory can provide guest-tools host, DNS, and IP data. RVTools imports read
common `DNS Name`, `FQDN`, `Primary IP Address`, `IP Address`, and
`Guest IP Address` columns when present.

For powered-on workloads, malformed guest IPs add `guest_ip_invalid`, no valid
guest IP adds `guest_ip_missing`, and missing DNS/hostname evidence adds
`guest_dns_missing`. These findings make the post-migration
`ip_dns_connectivity` validation row more evidence-backed.

## Power State Sources

The readiness engine uses `power_state` when present. Powered-on states such as
`POWERED_ON`, `poweredOn`, `on`, or `running` do not add risk. Non-running states
add `power_state_not_on` because guest tools, IP/DNS, application health, backup,
and precheck evidence may be stale or unavailable. Operators should confirm the
expected powered state, cold-migration path, and application-owner approval
before scheduling.

## RVTools Annotation Hints

RVTools does not prove every operational fact by itself. Use VM annotations for
operator-owned readiness facts:

```text
owner:apps;tier:critical;backup:protected;backup_last_success_hours:4;vendor_support:ahv,nc2;virtio_ready:true
```

You can also declare source-discovered dependencies in annotations:

```text
dependencies:db-01|redis-01
```

Unknown values remain conservative so the generated evidence shows the work
still needed before migration approval.

See [readiness-policy.md](readiness-policy.md) for configurable snapshot age,
backup age, and risk threshold values.
