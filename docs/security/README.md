# Security

## Principles

- Read-only collection first.
- Local-first execution.
- No persisted credentials.
- Redacted evidence by default.
- Deterministic output suitable for audit and change control.

## Credential Handling

Live connector credentials must come from environment variables, interactive
prompts, or a user-approved external secret store. Repository files, generated
evidence, logs, and test fixtures must not contain real credentials.

## Sensitive Data

Inventory exports can reveal hostnames, IP addresses, application names,
ownership, datastore names, storage topology, encryption posture, security
zoning, and business criticality. Treat raw inventory as sensitive operational
data.

RVTools CSV exports are raw VMware inventory and can include hostnames, network
names, datastore names, VM annotations, ownership hints, and business context.
Keep them local to the approved migration workspace and do not commit customer
exports.

Generated evidence redacts common sensitive values, but redaction is not a
substitute for human review before sharing artifacts outside the migration team.

## Current Controls

- The CLI writes artifacts only to a user-provided local output directory.
- The redaction module removes likely emails, IP addresses, URLs, hostnames, and
  secret-keyed fields from evidence source metadata.
- The HTML operator report is generated from redacted source metadata.
- Evidence manifests record SHA-256 hashes and sizes for assessment artifacts.
- Evidence bundles can be verified against the embedded manifest after handoff.
- Change gates compose local validators and do not contact endpoints or mutate
  infrastructure.
- Dependency CSV imports can include application names and ownership; treat them
  as sensitive operational data.
- Metadata CSV imports can include ownership, criticality, backup posture,
  support status, application approval, rollback ownership, and migration notes;
  treat them as sensitive operational data.
- `migration-risk-register.csv` aggregates finding codes, workload names,
  owners, and waves; treat it as sensitive migration planning data.
- `wave-readiness-summary.csv` aggregates wave names, owners, held workloads,
  and risk posture; treat it as sensitive migration planning data.
- `business-impact-summary.csv` aggregates business tier, owners, held
  workloads, and executive readiness posture; treat it as sensitive migration
  planning data.
- `assessment.json` includes a redacted `business_context` block with workload
  id, name, owner, and tier so generated business-impact evidence can be
  validated without reopening raw inventory.
- `assessment.json` includes a redacted `signoff_context` block with workload
  id, required approval roles, and dependency presence so generated sign-off
  evidence can be validated without reopening raw inventory.
- `assessment.json` includes a redacted `target_comparison_context` block with
  AHV and NC2 readiness, risk, findings, preferred target, and decision reason
  so target decision evidence can be validated without reopening raw inventory.
- `assessment.json` includes a redacted `dependency_sequence_context` block with
  included workload order and dependency counts so sequencing evidence can be
  validated without reopening raw inventory.
- `executive-readiness-brief.md` summarizes business impact, held workloads,
  top blockers, and approval gaps; treat it as sensitive migration planning
  evidence.
- RVTools imports run offline and do not use credentials, but the source CSVs
  remain sensitive operational data.
- Connector helpers expose vCenter session, VM inventory, VM detail, and network
  GET flows plus Prism Central v3 list POST flows only for the initial MVP.
- Connector contract tests verify POST allow-list enforcement, vCenter
  session-plus-GET behavior, Prism list pagination payloads, JSON headers, and
  configured request timeouts without contacting live endpoints.
- Normalized inventory includes non-secret collection audit metadata for live
  collectors and RVTools imports. The audit block records read-only path names,
  limits, counts, and `mutating_calls=0`, but does not duplicate endpoint URLs,
  usernames, or passwords.
- TLS verification defaults to enabled.
- Passwords are read from environment variables or secure prompts, not command
  arguments.
- Move API payload generation is dry-run only and cannot submit to Nutanix Move.
  Payload workload records include governance handoff fields, so treat payloads
  as sensitive migration evidence.
- Move submit readiness validation is lab-only, requires a separate review
  record and `NMRCP_MOVE_LAB_ACK=I_UNDERSTAND_LAB_ONLY`, and still does not
  connect to Nutanix Move.
- Environment access validation gates Dev, UAT, and Production read/write
  intent for PC, Move, vCenter, and ESXi. Write mode remains policy evaluation
  only and does not execute mutating actions.
- Migration runbooks are generated for human review and cannot execute
  migration actions.
- Validation result templates are local CSVs; final validation fails closed on
  unchecked or failed rows unless draft review is explicitly allowed.
- Dependency gates prevent workloads from being staged ahead of blocked internal
  dependencies.
- `doctor` reports only credential variable presence and never prints credential
  values.
- Endpoint probes do not write inventory files and do not print endpoint,
  username, or password values.
- Live endpoint configuration rejects plain HTTP for real vCenter and Prism
  Central URLs. HTTP is accepted only for loopback simulator smoke tests.
- Live readiness and collection-summary evidence record TLS verification state
  without endpoint values; `disabled` means TLS certificate verification was
  explicitly bypassed and should be reviewed before handoff.
- `live-readiness` writes only read-only call names and counts; it does not
  serialize endpoint URLs, usernames, passwords, or inventory details.
- `collect-sources` writes a redacted collection summary with artifact names,
  read-only path names, counts, and `mutating_calls=0`; it does not serialize
  endpoint URLs, usernames, passwords, or workload details.
- Inventory validation fails malformed inputs before evidence artifacts are
  generated.
- Inventory coverage reports reveal where owner, backup, support, network,
  storage, and dependency data is missing; treat the report as sensitive
  migration evidence.
- `review-evidence` scans generated evidence for unredacted URLs, emails, IPs,
  common internal hostnames, and secret-like assignments before handoff.
- Readiness policy files fail closed on unknown keys, invalid values, or
  inconsistent risk thresholds.
- Target capacity files are local governance inputs; they can reveal cluster
  sizing and reserved headroom and should be treated as sensitive.

## Review Checklist

- Confirm no secrets were committed.
- Confirm no mutation endpoints are called; Prism POST calls must remain list
  operations only.
- Confirm connector contract tests pass before changing live collector paths or
  payloads.
- Confirm generated artifacts do not include raw credentials.
- Confirm `review-evidence` passes before sharing evidence bundles or handoff
  packages.
- Confirm live-readiness proof files do not include endpoint URLs, usernames, or
  passwords.
- Confirm collection summary files do not include endpoint URLs, usernames,
  passwords, or workload details.
- Confirm collection audit metadata does not duplicate endpoint URLs, usernames,
  passwords, or source export labels.
- Confirm malformed or duplicate workload inventory is rejected.
- Confirm low inventory coverage is reviewed before approving migration waves.
- Confirm storage posture findings have storage-owner remediation or risk
  acceptance before approving migration waves.
- Confirm target network mapping passes before generating or reviewing dry-run
  Move payloads.
- Confirm target capacity fit passes before staging workloads in Nutanix Move.
- Confirm target reconciliation passes before staging included workloads in
  Nutanix Move.
- Confirm HTML reports are reviewed before sharing outside the migration team.
- Confirm evidence manifests are shared with the artifact bundle when handoff
  integrity matters.
- Confirm packaged bundles are verified before upload to ticketing, change, or
  partner systems.
- Confirm sample data is synthetic.
- Confirm custom readiness policy files are approved and attached to change
  evidence.
- Confirm README and docs call out residual risk.
- Confirm dependency exports are reviewed before sharing outside the migration
  team.
- Confirm metadata exports are reviewed before sharing outside the migration
  team.
- Confirm dry-run Move payloads do not include real secrets and are reviewed
  before any future lab-only submitter is enabled.
- Confirm Move submit readiness proof passes only with lab-reviewed provider
  IDs, no immediate schedule, complete approvals, and explicit lab
  acknowledgement.
- Confirm migration runbooks are reviewed before operators use them for change
  execution.
- Confirm final remediation trackers have no open rows and include closure
  evidence before moving held workloads toward staging.
- Confirm final owner sign-offs include rollback-owner approval before staging
  or closing migration changes.
- Confirm final validation results have no unchecked or failed rows before
  closing a migration change.
- Confirm `change-gate` passes before handoff or closure.
- Confirm `verify-handoff` passes before sending final handoff packages outside
  the migration workspace.
- Confirm diagnostic output does not print endpoint passwords or usernames.
- Confirm probe output remains count-only and does not reveal connection values.
