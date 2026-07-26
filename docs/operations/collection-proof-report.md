# Collection Proof Report

`collection-proof-report.md` is the human-readable companion to
`collection-summary.json` and `collection-proof-manifest.json`. It gives
operators, partners, and change boards a redacted proof brief for approved
source collection without exposing endpoint URLs, usernames, passwords, tokens,
hostnames, IP addresses, workload details, or assessment-intake values.

## Generate

`collect-sources` writes the report automatically:

```powershell
python -m nmrcp.cli collect-sources `
  --assessment-intake outputs\assessment-intake.csv `
  --out-dir outputs\source-collection
```

Regenerate it from an existing summary when needed:

```powershell
python -m nmrcp.cli collection-proof-report `
  --collection-summary outputs\source-collection\collection-summary.json `
  --out outputs\source-collection\collection-proof-report.md
```

## Validate

```powershell
python -m nmrcp.cli validate-collection-proof-report `
  --report outputs\source-collection\collection-proof-report.md `
  --collection-summary outputs\source-collection\collection-summary.json
```

Validation checks required sections, report schema
`nmrcp_collection_proof_report_v1`, source summary schema
`nmrcp_collection_summary_v1`, privacy statements, `mutating_calls=0`,
assessment-intake binding, `collection-proof-manifest.json`, and the
`validate-live-proof` closeout path. It also scans the Markdown for endpoint,
username, IP, URL, and secret-like leakage.

## Contents

- Collection status and source summary schema.
- Read-only evidence by collection check, including workload/network/target
  counts, API path names, TLS posture, and `mutating_calls=0`.
- Privacy posture for credentials, endpoint values, summary redaction, and TLS
  verification.
- Assessment-intake binding status, row count, checksum presence, and
  `values_serialized=false`.
- Artifact map including `collection-summary.json`,
  `collection-proof-manifest.json`, collected source inventory, and the report
  itself.
- Stop conditions for mutation, privacy drift, missing manifest proof, failed
  `validate-live-proof`, and sensitive data leakage.

## External Proof Boundary

The report does not replace `validate-live-proof`. It is the reviewer-facing
brief; `validate-live-proof` remains the machine gate that checks live
readiness, collection summary, collection audit metadata, proof-manifest
membership, artifact hashes, API allowlists, TLS posture, and assessment-intake
checksum consistency.
