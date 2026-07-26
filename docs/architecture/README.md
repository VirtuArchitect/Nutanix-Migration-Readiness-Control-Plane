# Architecture

## Product Boundary

The Nutanix Migration & Readiness Control Plane is an assessment and evidence
layer. It should not become a competing migration engine. Nutanix Move, Prism
Central, Nutanix Cloud Manager, and partner runbooks remain the execution
systems.

## Initial Components

- Inventory adapters: offline RVTools CSV import plus read-only vCenter and
  Prism Central collectors, including a one-command source collection workflow.
- Metadata enricher: merges CMDB/application-owner facts into workload records
  before scoring.
- Normalized inventory model: workload, network, storage, guest OS, owner,
  dependency, backup, and tooling facts.
- Inventory validator: structural checks and optional strict completeness gates.
- Readiness engine: deterministic rules that explain why a workload is ready,
  needs research, needs remediation, or is blocked.
- Readiness policy: optional local JSON thresholds for snapshot age, backup
  freshness, and readiness classification.
- Dependency gate: holds workloads whose internal dependencies are not ready.
- Readiness signals: guest OS, NSX/VDS networking, storage posture, snapshots
  and snapshot age, VMware Tools presence/status, VirtIO readiness, backup proof
  and age, vendor support, and dependency ownership.
- Wave planner: migration wave grouping based on readiness, risk, and internal
  dependency order.
- Evidence exporter: redacted JSON, CSV, Markdown, HTML, and checklist artifacts.
- Change gate: local composite verifier for assessment artifacts, Move plans,
  evidence integrity, bundles, and optional validation results.
- Handoff package: final archive wrapper for assessment, evidence bundle,
  validation, and dry-run Move payload artifacts.
- Assessment workflow: one-command orchestration for inventory validation,
  scoring, evidence export, Move-plan validation, packaging, change gate, and
  handoff creation.
- Dependency enricher: merges CMDB/application map exports into workload
  records before scoring.

## Data Flow

```text
RVTools / vCenter / Prism Central / CMDB exports
  -> read-only collection or normalized JSON import
  -> redacted source collection summary
  -> optional metadata and dependency enrichment
  -> readiness scoring
  -> migration wave planning
  -> redacted evidence exports
  -> change-board and migration-factory workflows
```

## Collector Boundary

The MVP has two live collector paths:

- vCenter: create an API session, list VMs, then enrich each VM with detail GET
  calls up to the configured detail limit.
- Prism Central: call Prism v3 VM list APIs with pagination. Prism v3 list
  operations use POST with a read-only list payload, so mutation safety is
  enforced by endpoint allow-listing and connector review rather than HTTP verb
  alone.
- Prism capacity: call the Prism v3 cluster list API to draft target CPU,
  memory, and storage capacity assumptions for review before capacity-fit
  validation.

`collect-sources` orchestrates those read-only paths together and writes
`vcenter-inventory.json`, `prism-inventory.json`, `prism-capacity.json`, and a
redacted `collection-summary.json`.

Credentials are never written to normalized inventory. Source metadata records
the endpoint, collection mode, timestamp, and a non-secret collection audit
block. The audit block names the read-only API paths, configured collection
limits, observed counts, credential storage posture, and `mutating_calls=0`
without serializing usernames, passwords, or duplicate endpoint URLs.

`live-readiness` is a pre-collection proof command. It runs only the read-only
probe/list calls, writes `nmrcp_live_readiness_v1`, and records status plus
counts without serializing endpoint values, usernames, passwords, or inventory
details.

The offline RVTools path reads local CSV exports and does not contact vCenter.
It is useful before service accounts are approved, but RVTools files still
contain sensitive infrastructure inventory and should stay in the approved
migration workspace.

## Planning Exports

- `migration-waves.csv`: wave assignment and top findings.
- `wave-readiness-summary.csv`: wave-level readiness, risk, blockers, owners,
  Move staging status, and next gate.
- `inventory-coverage.csv`: per-workload coverage of required migration and
  governance facts.
- `target-readiness-comparison.csv`: AHV versus NC2 readiness, risk, findings,
  and preferred target decision support.
- `target-reconciliation.csv`: optional comparison between source Move-plan
  workloads and current Prism inventory for target-name collision detection.
- `dependency-sequence.csv`: dependency-aware order for included workloads.
- `remediation-tracker.csv`: owner-action tracker for readiness findings that
  must be closed or accepted before migration.
- `migration-risk-register.csv`: finding-code rollup of repeated breakage
  patterns, affected owners, waves, and Move staging blockers.
- `owner-risk-summary.csv`: owner-level readiness, risk, finding severity, and
  next-action rollup.
- `business-impact-summary.csv`: tier-level executive impact rollup for
  critical, noncritical, and unknown workload groups.
- `executive-readiness-brief.md`: Markdown decision brief for sponsors and
  change boards.
- `owner-signoff-matrix.csv`: workload-level approval register for application,
  migration, dependency, network, storage, backup, cloud, and risk sign-offs.
- `nutanix-move-plan.csv`: `nmrcp_move_plan_v1` Move staging plan with include/hold decisions,
  target network hints, dependency count, governance handoff fields, and
  required action codes.
- `target-network-mapping.csv`: optional source-to-target network mapping proof
  for included Move staging workloads.
- `target-capacity-fit.csv`: optional CPU, memory, and storage fit check for
  included Move staging workloads against approved target capacity.
- `wave-execution-calendar.csv`: operator-facing review-window plan with wave
  entry gate, exit gate, actions, and evidence references.
- `partner-handoff-matrix.csv`: role-based partner/customer/MSP handoff matrix
  with owned artifacts, required review, status, blockers, and next actions.
- `move-lab-evidence-request.md`: lab-only Move appliance proof-window request
  with dry-run controls, evidence chain, closeout commands, and stop conditions.
- `source-endpoint-evidence-request.md`: read-only vCenter and Prism Central
  validation request with proof commands, privacy controls, and stop conditions.
- `prism-category-mapping.csv`: review-only Prism/NCM category plan derived
  from source ownership, tier, readiness, and tags.
- `stakeholder-communication-plan.csv`: review-only owner/wave outreach plan
  with audience, evidence references, and required actions.
- `what-will-break-report.csv`: workload-level finding translation into
  breakage scenario, impact, operator signal, and evidence references.
- `change-board-evidence.md`: redacted narrative evidence for approval.
- `migration-runbook.md`: wave-ordered operator runbook with stop conditions,
  Move staging intent, target network hints, governance facts, dependency
  coordination, and workload required actions.
- `operator-portal.html`: self-contained local HTML launchpad for the generated
  assessment evidence set.
- `operator-report.html`: self-contained local HTML report for operator review.
- `operator-dashboard.html`: self-contained local HTML work queue with
  readiness, owner, wave, and finding filters for operator triage.
- `operator-gate-summary.md`: readable rollup of generated source endpoint and
  Move lab request checks plus optional capacity, reconciliation, network
  mapping, validation, remediation, and sign-off gates.
- `pre-post-validation-checklist.md`: operator checklist for cutover.
- `validation-results*.csv`: structured pre/post validation evidence generated
  from the Move staging plan and filled during migration execution.
- `evidence-manifest.json`: SHA-256 integrity manifest for the core evidence
  bundle.
- `*.zip`: optional evidence handoff bundle packaged from the manifest.
- `handoff-manifest.json`: manifest inside the final handoff package that
  records archived assessment, bundle, validation, and dry-run payload files.
- `move-api-payload.dry-run.json`: review-only API payload shape generated from
  a validated Move staging plan and explicit mapping config.
- `change-gate`: command output for pre-change or closure approval checks.

The Move staging plan and dry-run payload are validated locally. Direct Move API
plan creation is a future lab-only mutation workflow because plan creation
requires provider, network mapping, schedule, and workload payloads.

## Non-Goals

- Do not mutate vCenter, Prism Central, AHV, NC2, or Nutanix Move state in the
  MVP.
- Do not store credentials.
- Do not claim vendor support from heuristics alone.
- Do not replace application owner sign-off.

## Readiness States

- `ready`: low-risk pilot candidate.
- `research`: likely movable, but support or compatibility needs confirmation.
- `prepare`: remediation is required before scheduling.
- `blocked`: migration should not proceed until a blocking condition is cleared.
