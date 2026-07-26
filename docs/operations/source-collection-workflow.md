# Source Collection Workflow

`collect-sources` is the operator entry point for approved live collection. It
connects to vCenter and Prism Central in read-only mode, writes local normalized
inventory files, writes explicit vCenter network evidence, drafts Prism target
capacity, and emits redacted collection proof artifacts.

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

The source collection plan is the pre-access operator checklist. It lists the
approved scope, local-only credential handling, proof outputs, and stop
conditions without storing endpoint values or secrets.

The command also accepts explicit endpoint and username flags when environment
variables are not used:

```powershell
python -m nmrcp.cli collect-sources `
  --vcenter-endpoint https://vcenter.example.com `
  --vcenter-username administrator@example.com `
  --prism-endpoint https://prism-central.example.com:9440 `
  --prism-username admin `
  --assessment-intake outputs\assessment-intake.csv `
  --out-dir outputs\source-collection
```

`--assessment-intake` is optional for compatibility with local collection
experiments, but required for customer, partner, and external live-proof
closeout runs. When supplied, `collect-sources` validates the intake before
connecting to source systems. Invalid or incomplete intake fails closed. Passing
intake is not copied into the output directory; the collection summary and proof
manifest record only validation status, row count, warnings, and the source file
SHA-256 so reviewers can prove the kickoff acknowledgements were bound to the
collection run without exposing scope notes or contact details.

## Outputs

- `vcenter-inventory.json`: normalized source workload inventory for migration
  readiness assessment.
- `vcenter-networks.json`: explicit read-only vCenter network inventory with
  network IDs, names, types, and non-secret collection proof.
- `prism-inventory.json`: normalized current Prism VM inventory for reference
  and future reconciliation.
- `prism-capacity.json`: target capacity draft from Prism Central cluster list.
- `collection-summary.json`: redacted source collection proof with counts,
  read-only API path names, artifact names, optional assessment-intake checksum,
  and `mutating_calls=0`.
- `collection-proof-manifest.json`: redacted checksum manifest for the source
  collection artifacts and the exact read-only API allowlist observed during
  collection. When an assessment intake is supplied, the manifest repeats the
  intake validation checksum under `security.assessment_intake`.
- `collection-proof-report.md`: redacted Markdown brief for operator, partner,
  and change-board review. It summarizes read-only checks, API path names, TLS
  posture, artifact paths, assessment-intake binding, and stop conditions
  without endpoint values or secrets. See
  [collection-proof-report.md](collection-proof-report.md).

When source metadata includes dependency hints, the normalized inventory keeps
them as declared dependency records. Supported hint keys include
`dependency`, `dependencies`, `depends_on`, and
`application_dependencies` in vCenter tags, vCenter annotations or
descriptions, Prism categories or descriptions, and RVTools annotations.
Separate multiple dependency names with commas or pipes, for example
`dependencies:db-01|redis-01`.

When guest identity fields are available, collection also preserves host name,
DNS name, guest IP addresses, valid and invalid IP lists, and IPv4/IPv6
presence. This is local evidence for pre-change review and the post-cutover
`ip_dns_connectivity` validation row.

## Next Step

Assess the vCenter source inventory against the Prism target capacity:

```powershell
python -m nmrcp.cli validate-collection-audit --inventory outputs\source-collection\vcenter-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\source-collection\prism-inventory.json
python -m nmrcp.cli assess `
  --inventory outputs\source-collection\vcenter-inventory.json `
  --capacity outputs\source-collection\prism-capacity.json `
  --out outputs\source-assessment
```

Or use the full workflow with target reconciliation:

```powershell
python -m nmrcp.cli run-assessment `
  --inventory outputs\source-collection\vcenter-inventory.json `
  --capacity outputs\source-collection\prism-capacity.json `
  --prism-inventory outputs\source-collection\prism-inventory.json `
  --out outputs\source-assessment
```

## Security Behavior

- Passwords are read from local environment variables or secure prompts.
- Real vCenter and Prism Central endpoint URLs must use HTTPS. Plain HTTP is
  accepted only for loopback simulator URLs such as `http://127.0.0.1:<port>`
  during local smoke tests.
- The redacted collection summary does not serialize endpoint URLs, usernames,
  passwords, or workload details.
- The collection proof manifest does not serialize endpoint URLs, usernames, or
  passwords. It binds each collected artifact to `size_bytes` and `sha256` so
  reviewers can detect local artifact tampering before assessment or handoff.
- Assessment intake binding records validation metadata and SHA-256 only; it
  does not serialize intake field values.
- The collection summary records TLS verification state as `enabled`,
  `disabled`, or `loopback_http` per source check. `disabled` should be treated
  as a reviewed exception, not a default production posture.
- Source inventory files retain local operator traceability and must remain in
  the approved migration workspace.
- vCenter uses session plus GET inventory and network calls.
- Prism Central uses allow-listed v3 list calls for VMs and clusters.
- The command does not mutate vCenter, Prism Central, AHV, NC2, or Nutanix Move.

## Proof Validation

Pair source collection with `live-readiness` and `validate-live-proof` when the
run is intended to retire the read-only endpoint proof gap:

```powershell
python -m nmrcp.cli live-readiness `
  --require-vcenter `
  --require-prism `
  --out outputs\source-collection\live-readiness.json
python -m nmrcp.cli validate-live-proof `
  --live-readiness outputs\source-collection\live-readiness.json `
  --collection-summary outputs\source-collection\collection-summary.json `
  --source-dir outputs\source-collection `
  --out outputs\source-collection\live-proof-validation.json
python -m nmrcp.cli validate-collection-proof-report `
  --report outputs\source-collection\collection-proof-report.md `
  --collection-summary outputs\source-collection\collection-summary.json
```

The live proof validator requires assessment-intake binding and TLS verification
evidence in both `live-readiness.json` and `collection-summary.json`. When
`collection-proof-manifest.json` is present in the summary, the validator also
checks manifest redaction, read-only API allowlist scope, artifact membership,
sizes, SHA-256 hashes, and that the manifest intake checksum matches the
collection summary. `enabled` and `loopback_http` can pass, `disabled` returns a
warning for exception review, and missing, unknown, or `not_configured` states
fail external proof.
