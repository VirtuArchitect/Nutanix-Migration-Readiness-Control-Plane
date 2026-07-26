# Live Endpoint Proof

`validate-live-proof` validates the redacted evidence packet from approved
vCenter and Prism Central collection. It is the bridge between local connector
tests and real lab/customer endpoint proof.

The command checks:

- `live-readiness.json` uses schema `nmrcp_live_readiness_v1` and status
  `pass`.
- vCenter and Prism Central checks are configured, authenticated, and read-only.
- vCenter observed at least one VM.
- Prism Central observed at least one cluster.
- `collection-summary.json` uses schema `nmrcp_collection_summary_v1` and
  reports no serialized credentials or endpoint values.
- `collection-summary.json` includes validated assessment-intake proof with a
  SHA-256 checksum and no serialized intake values.
- live-readiness and collection-summary evidence include TLS verification state
  for vCenter and Prism Central.
- collection checks report `mutating_calls=0`.
- referenced vCenter and Prism inventory files contain valid non-secret
  collection audit blocks.
- `collection-proof-manifest.json` repeats the same assessment-intake proof as
  the collection summary.
- collection summaries can include explicit vCenter network evidence from
  `/api/vcenter/network`; zero observed networks is a warning, not mutation
  evidence.
- shared proof files do not contain URLs, IPs, emails, hostnames, or
  secret-like assignments.

## Run

After approved endpoint collection:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli live-readiness `
  --require-vcenter `
  --require-prism `
  --out outputs\source-collection\live-readiness.json

python -m nmrcp.cli validate-assessment-intake `
  --intake outputs\assessment-intake.csv

python -m nmrcp.cli collect-sources `
  --assessment-intake outputs\assessment-intake.csv `
  --out-dir outputs\source-collection

python -m nmrcp.cli validate-live-proof `
  --live-readiness outputs\source-collection\live-readiness.json `
  --collection-summary outputs\source-collection\collection-summary.json `
  --source-dir outputs\source-collection `
  --out outputs\source-collection\live-proof-validation.json
```

Then pass the validated proof into the MVP audit:

```powershell
python -m nmrcp.cli mvp-audit `
  --repo-root . `
  --assessment-dir outputs\smoke `
  --assessment-intake outputs\assessment-intake.csv `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --out outputs\mvp-audit.json
```

## Status

The validator returns `pass`, `warn`, or `fail`. Warnings are reserved for
non-blocking proof context, such as a Prism target environment with zero
existing VMs or an approved TLS verification exception. TLS verification states
must be `enabled`, `disabled`, or `loopback_http`; `not_configured`, missing, or
unknown states fail external proof. `disabled` keeps the proof valid but returns
`warn` so reviewers can confirm the exception was approved. Any leak, failed
endpoint readiness, mutation evidence, malformed schema, missing assessment
intake binding, mismatched proof-manifest intake checksum, or invalid collection
audit fails the proof.
