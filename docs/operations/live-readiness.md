# Live Readiness Proof

`live-readiness` runs a redacted, read-only reachability check for configured
vCenter and Prism Central endpoints. It is intended to prove that collection can
start without writing credentials, endpoint URLs, usernames, or inventory
details into the proof file.

## Environment

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_VCENTER_URL = "https://vcenter.example.com"
$env:NMRCP_VCENTER_USERNAME = "administrator@example.com"
$env:NMRCP_VCENTER_PASSWORD = "<local secret>"
$env:NMRCP_PRISM_URL = "https://prism-central.example.com:9440"
$env:NMRCP_PRISM_USERNAME = "admin"
$env:NMRCP_PRISM_PASSWORD = "<local secret>"
```

## Run

```powershell
python -m nmrcp.cli live-readiness --out outputs\live-readiness.json
```

Use strict mode when both endpoints must be reachable before a migration factory
or partner team starts collection:

```powershell
python -m nmrcp.cli live-readiness `
  --require-vcenter `
  --require-prism `
  --out outputs\live-readiness.json
```

## What It Checks

- vCenter: `/api/session` plus `/api/vcenter/vm`.
- Prism Central: `/api/nutanix/v3/clusters/list` plus
  `/api/nutanix/v3/vms/list`.

The output records schema `nmrcp_live_readiness_v1`, endpoint status, read-only
call names, and object counts. Missing optional endpoints return `warn` and exit
successfully; required missing or failed endpoints return `fail`.

## Security Behavior

- Credentials are never serialized.
- Endpoint values and usernames are never serialized.
- Real endpoint URLs must use HTTPS. Plain HTTP is allowed only for local
  loopback simulator URLs used by the smoke test.
- TLS verification state is recorded without endpoint values as `enabled`,
  `disabled`, `loopback_http`, or `not_configured`. Treat `disabled` as an
  explicit review item before relying on live collection evidence.
- The command does not write inventory artifacts.
- Prism POST calls remain limited to allow-listed read-only list endpoints.
- No mutation against vCenter, Prism Central, AHV, NC2, or Nutanix Move is
  possible through this command.

## Connector Contract Coverage

Unit coverage verifies the read-only connector contract without contacting live
endpoints:

- mutating Prism VM POST paths are rejected before an HTTP request is built.
- allowed Prism list requests use POST payloads with `kind`, `offset`, and
  `length`.
- vCenter VM inventory uses a session request followed by GET calls with the
  session header.
- Prism VM inventory pagination advances offsets and stops at the reported
  total.
- raw HTTP requests carry JSON `Accept`/`Content-Type` headers and configured
  timeouts.

## Simulated Live Collector Smoke

`scripts/live_collector_smoke.py` starts local loopback HTTP simulators for
vCenter and Prism Central, runs the real `collect-sources` CLI command against
them, validates generated inventory and redacted `collection-summary.json`,
assesses the simulated vCenter inventory with generated Prism capacity, and runs
evidence redaction review.

This proves collector wiring, HTTP request paths, normalization, snapshot age
mapping when timestamp fields are present, VMware Tools version-status mapping,
collection audit metadata, capacity draft generation, capacity-fit evidence,
source-collection summary redaction, and redaction behavior without live
credentials. It does not replace validation against real vCenter and Prism
Central endpoints.

Use [live-endpoint-proof.md](live-endpoint-proof.md) after approved live
collection to validate the combined `live-readiness.json`, redacted collection
summary, and inventory collection audit blocks.
