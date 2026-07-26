# Security Review

Use this checklist for changes touching connectors, inventory parsing, evidence
exports, logs, filesystem paths, or CI/CD.

## Checklist

- No credentials, tokens, support bundles, or customer exports are committed.
- Assessment intake files contain scope labels only, not endpoint URLs,
  credentials, tokens, support bundles, or raw customer exports.
- CMDB/application metadata imports reject endpoint URLs and secret-like
  assignments before writing normalized metadata.
- Connectors remain read-only unless mutation is explicitly scoped and approved.
- TLS verification defaults to enabled.
- Evidence exports redact source metadata and do not include secrets.
- Generated local HTML portal, report, and dashboard artifacts do not leak
  endpoint URLs, usernames, passwords, emails, or sample internal hostnames.
- Dependency and metadata CSV imports are synthetic in tests and reviewed before
  sharing.
- Move staging plans fail validation when blocked workloads are included.
- Prism/NCM category mapping remains review-only and does not apply categories
  or call Prism Central/NCM mutation endpoints.
- Stakeholder communication plans remain review-only local evidence and do not
  send emails, create tickets, or call collaboration APIs.
- What-will-break reports are generated from redacted assessment findings, but
  still contain sensitive migration failure modes and business-impact context.
- Wave execution calendars are planning evidence only and do not schedule
  migrations, create calendar events, or call Nutanix Move.
- Partner handoff matrices are local review evidence only and can reveal role
  ownership, blockers, and migration responsibilities.
- Move lab evidence requests are local preflight artifacts only. They can reveal
  workload counts, owner groups, lab-proof timing intent, and handoff blockers;
  keep endpoint names, IP addresses, FQDNs, customer identifiers, and secrets out
  of the request.
- Source endpoint evidence requests are local preflight artifacts only. They can
  reveal workload counts, owner groups, source-validation intent, and required
  endpoint proof commands; keep endpoint names, IP addresses, FQDNs, usernames,
  customer identifiers, and secrets out of the request.
- Move API payload generation is dry-run only and includes `mutation_allowed:
  false`.
- Handoff package manifests do not include local source paths and verify archived
  file size plus SHA-256.
- Doctor output reports environment-variable presence only, not values.
- Probe output is count-only and does not print endpoint, username, or password
  values.
- Live-readiness proof output is count-only and does not serialize endpoint,
  username, password, or inventory values.
- Collection summary output is count-only and does not serialize endpoint,
  username, password, or workload details.
- Generated files are written only to caller-selected directories.
- Errors do not print credentials or authorization headers.
- Tests use synthetic data only.
- Malformed normalized inventories fail before assessment artifacts are written.
- `scripts/security_scan.py` runs in CI and checks for private keys, AWS-style
  access keys, and literal secret assignments.

## Current Review

The initial MVP is local-first and dependency-free at runtime. The connector
helper supports vCenter session/GET inventory flows and Prism Central v3 POST
list inventory flows. It does not call mutation endpoints or persist sessions.
Evidence redaction covers common emails, IP addresses, URLs, hostnames, and
secret-keyed fields. Residual risk remains for arbitrary application names or
business labels that are sensitive but not pattern-matchable.
