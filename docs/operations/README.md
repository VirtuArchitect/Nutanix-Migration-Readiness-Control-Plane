# Operations Guide

## Assessment Workflow

1. Export or collect read-only vCenter and Prism Central inventory.
2. Normalize the inventory into the MVP JSON shape.
3. Run the local assessment CLI.
4. Review blocked and remediation-required workloads with application owners.
5. Attach the evidence pack to the migration change request.
6. Use the wave CSV to prepare Nutanix Move planning and operator runbooks.

For repeatable migration-factory runs, use the one-command workflow:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli run-assessment `
  --inventory examples\sample_inventory.json `
  --metadata examples\sample_metadata.csv `
  --dependencies examples\sample_dependencies.csv `
  --move-config examples\sample_move_payload_config.json `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --out outputs\workflow-assessment
```

See [assessment-workflow.md](assessment-workflow.md).

Before collection or offline import, generate and validate a customer or partner
assessment intake:

```powershell
python -m nmrcp.cli generate-assessment-intake `
  --out outputs\assessment-intake.csv
python -m nmrcp.cli validate-assessment-intake `
  --intake examples\sample_assessment_intake.csv
python -m nmrcp.cli source-collection-plan `
  --intake examples\sample_assessment_intake.csv `
  --out outputs\source-collection-plan.md
python -m nmrcp.cli validate-source-collection-plan `
  --plan outputs\source-collection-plan.md `
  --intake examples\sample_assessment_intake.csv
```

Pass the completed intake to `collect-sources --assessment-intake` on approved
live runs so collection proof records a redacted validation checksum before any
source inventory is gathered.
Generate the source collection plan before the access window when operators need
a credential-safe checklist for approved read-only collection.

See [assessment-intake.md](assessment-intake.md).
See [source-collection-plan.md](source-collection-plan.md).

Audit MVP requirement evidence after a local smoke or workflow run:

```powershell
python -m nmrcp.cli mvp-audit `
  --repo-root . `
  --assessment-dir outputs\smoke `
  --assessment-intake examples\sample_assessment_intake.csv `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --evidence-bundle outputs\smoke-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --warning-acceptance examples\sample_change_gate_warning_acceptance.csv `
  --out outputs\mvp-audit.json
```

See [mvp-readiness-audit.md](mvp-readiness-audit.md).

Validate the generated dependency review artifact:

```powershell
python -m nmrcp.cli validate-dependency-review `
  --review outputs\sample-assessment\dependency-review.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [dependency-review.md](dependency-review.md).

Validate the generated connectivity checklist artifact:

```powershell
python -m nmrcp.cli validate-connectivity-checklist `
  --checklist outputs\sample-assessment\connectivity-checklist.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [connectivity-checklist.md](connectivity-checklist.md).

Validate the generated identity cutover plan:

```powershell
python -m nmrcp.cli validate-identity-cutover-plan `
  --plan outputs\sample-assessment\identity-cutover-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [identity-cutover-plan.md](identity-cutover-plan.md).

Validate the generated compatibility research artifact:

```powershell
python -m nmrcp.cli validate-compatibility-research `
  --research outputs\sample-assessment\compatibility-research.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [compatibility-research.md](compatibility-research.md).

Validate the generated tools and VirtIO driver readiness artifact:

```powershell
python -m nmrcp.cli validate-tools-driver-readiness `
  --readiness outputs\sample-assessment\tools-driver-readiness.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [tools-driver-readiness.md](tools-driver-readiness.md).

Validate the generated storage posture artifact:

```powershell
python -m nmrcp.cli validate-storage-posture `
  --posture outputs\sample-assessment\storage-posture.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [storage-posture.md](storage-posture.md).

Validate the generated recovery readiness artifact:

```powershell
python -m nmrcp.cli validate-recovery-readiness `
  --readiness outputs\sample-assessment\recovery-readiness.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [recovery-readiness.md](recovery-readiness.md).

Validate the generated rollback plan:

```powershell
python -m nmrcp.cli validate-rollback-plan `
  --plan outputs\sample-assessment\rollback-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [rollback-plan.md](rollback-plan.md).

Validate the generated Move staging readiness artifact:

```powershell
python -m nmrcp.cli validate-move-staging-readiness `
  --readiness outputs\sample-assessment\move-staging-readiness.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [move-staging-readiness.md](move-staging-readiness.md).

Validate the generated workload validation checklist:

```powershell
python -m nmrcp.cli validate-workload-validation-checklist `
  --checklist outputs\sample-assessment\workload-validation-checklist.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [workload-validation-checklist.md](workload-validation-checklist.md).

Validate the generated migration execution queue:

```powershell
python -m nmrcp.cli validate-migration-execution-queue `
  --queue outputs\sample-assessment\migration-execution-queue.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [migration-execution-queue.md](migration-execution-queue.md).

Validate the generated approval exceptions register:

```powershell
python -m nmrcp.cli validate-approval-exceptions `
  --exceptions outputs\sample-assessment\approval-exceptions.csv `
  --assessment outputs\sample-assessment\assessment.json
```

See [approval-exceptions.md](approval-exceptions.md).

Package the audit and proof files for review:

```powershell
python -m nmrcp.cli package-mvp-proof `
  --mvp-audit outputs\smoke-mvp-audit.json `
  --live-proof outputs\smoke-live-proof-validation.json `
  --move-lab-proof outputs\smoke\move-lab-proof-validation.simulated.json `
  --move-lab-runbook outputs\smoke\move-lab-execution-runbook.md `
  --move-lab-closure-checklist outputs\smoke\move-lab-closure-checklist.md `
  --move-lab-capture-kit outputs\smoke\move-lab-capture-kit `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --move-lab-readiness-packet outputs\smoke\move-lab-readiness-packet.json `
  --source-collection-plan outputs\source-collection-plan.md `
  --source-endpoint-evidence-request outputs\smoke\source-endpoint-evidence-request.md `
  --move-lab-evidence-request outputs\smoke\move-lab-evidence-request.md `
  --out outputs\smoke-mvp-proof-package.zip
```

See [mvp-proof-package.md](mvp-proof-package.md).

`verify-mvp-proof` checks hashes and semantic role coverage, including the
required `mvp_audit` role and known archive paths for optional proof artifacts.
It also validates packaged proof schemas and acceptable statuses for each JSON
proof role, validates the Move lab closure checklist when packaged, and
validates packaged source endpoint and Move lab evidence requests. It also
validates packaged Move lab readiness packets as pre-lab handoff evidence, not
as approved appliance proof. `package-handoff` and `run-assessment` can also
archive the same packet at `move/move-lab-readiness-packet.json` with
`--move-lab-readiness-packet`.
The standalone `mvp-audit --live-proof` path uses the same live proof contract:
the file must come from `validate-live-proof` and include passing read-only
security, collection privacy, assessment-intake binding, proof-manifest
security, API allowlist, and proof-manifest intake checksum-match checks. A
status-only live proof is rejected as stale evidence.
Use `summarize-mvp-proof` to create a reviewer-facing Markdown report from the
package. Use `mvp-closure-report` to create the reviewer action list and JSON
closure record:

```powershell
python -m nmrcp.cli mvp-closure-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --out outputs\smoke-mvp-closure-report.md `
  --json-out outputs\smoke-mvp-closure-report.json
```

When Move proof remains open, the closure report includes a `Closeout Commands`
section and JSON `closeout_commands` list covering approved lab transcript,
generated approved proof, proof validation, evidence intake, final gates, proof
packaging, handoff packaging with the Move lab readiness packet, and rerun of
the closure report.

Create a launch-readiness brief for partner, MSP, customer, or change-board
reviewers from the verified MVP proof package:

```powershell
python -m nmrcp.cli launch-readiness-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --repo-url https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --out outputs\smoke-launch-readiness-report.md `
  --json-out outputs\smoke-launch-readiness-report.json
```

See [launch-readiness-report.md](launch-readiness-report.md).

Run the final Move lab proof workflow after a lab appliance proof record exists:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
powershell -ExecutionPolicy Bypass -File scripts\move_lab_proof_workflow.ps1 `
  -AssessmentDir outputs\sample-assessment `
  -MovePayload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  -MoveLabProof outputs\move-lab-proof.approved.json `
  -MoveLabTranscriptValidation outputs\move-lab-transcript-validation.json `
  -MoveSubmitReview examples\sample_move_submit_review.json `
  -LiveProof outputs\source-collection\live-proof-validation.json `
  -MvpAudit outputs\mvp-audit.json `
  -MvpProofPackage outputs\mvp-proof-package.zip `
  -MvpClosureReport outputs\mvp-closure-report.md `
  -LaunchReadinessReport outputs\launch-readiness-report.md `
  -LaunchRepoUrl https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

See [move-lab-proof-workflow.md](move-lab-proof-workflow.md).

Generate the redacted lab execution runbook before the approved proof window:

```powershell
python -m nmrcp.cli generate-move-lab-runbook `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --proof-template outputs\sample-assessment\move-lab-proof.template.json `
  --out outputs\sample-assessment\move-lab-execution-runbook.md
```

See [move-lab-runbook.md](move-lab-runbook.md).

Generate the Move lab capture kit before the proof window so the operator has a
redacted transcript template and checklist:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli generate-move-lab-capture-kit `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out-dir outputs\move-lab-capture-kit
python -m nmrcp.cli validate-move-lab-capture-kit `
  --kit-dir outputs\move-lab-capture-kit `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --out outputs\move-lab-capture-kit-validation.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

See [move-lab-transcript.md](move-lab-transcript.md).

## Local Preflight

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli doctor
```

`doctor` does not contact vCenter, Prism Central, or Nutanix Move. It validates
the local sample pipeline and reports whether endpoint environment variables are
present without printing values. Missing endpoint variables are warnings until a
live collector is being configured.

## Endpoint Probes

Use probes after `doctor` and before collection:

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_VCENTER_PASSWORD = "<local secret>"
python -m nmrcp.cli probe-vcenter --endpoint https://vcenter.example.com --username administrator@example.com

$env:NMRCP_PRISM_PASSWORD = "<local secret>"
python -m nmrcp.cli probe-prism --endpoint https://prism-central.example.com:9440 --username admin
```

Probes authenticate and execute read-only list calls. They do not write inventory
files and do not print endpoint, username, or password values.

## Example

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli assess --inventory examples/sample_inventory.json --out outputs/sample-assessment
```

## Offline RVTools Import

When live vCenter access is not approved yet, import a local RVTools export:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli import-rvtools --dir examples\rvtools --source-name "rvtools-export" --out outputs\rvtools-inventory.json
python -m nmrcp.cli validate-inventory --inventory outputs\rvtools-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\rvtools-inventory.json
python -m nmrcp.cli assess --inventory outputs\rvtools-inventory.json --out outputs\rvtools-assessment
```

Supported files are `vInfo.csv`, plus optional `vSnapshot.csv`, `vNetwork.csv`,
and `vDisk.csv`. Snapshot timestamps in `vSnapshot.csv` are converted into
`snapshots.oldest_days` for age-policy scoring when present; otherwise only the
snapshot count is used. Unknown readiness facts are left conservative. Use VM
annotations for operator-owned facts such as owner, tier, backup proof, vendor
support, NSX usage, VirtIO readiness, and declared dependencies.

## Dependency-Aware Assessment

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli assess --inventory examples/sample_inventory.json --metadata examples/sample_metadata.csv --dependencies examples/sample_dependencies.csv --out outputs/dependency-aware-assessment
```

The dependency CSV accepts:

```text
source_id,source_name,dependency_name,dependency_id,dependency_type,owner,criticality,protocol,ports,direction,validation_method,notes
```

The connectivity fields are optional, but when supplied they feed
`connectivity-checklist.csv` for firewall, DNS, routing, and application
reachability validation.

Application dependency maps can be converted into this CSV format with
`import-app-map`. See [application-map-import.md](application-map-import.md).

Source metadata can seed declared dependencies before a formal dependency CSV is
ready. The vCenter, Prism, and RVTools import paths recognize keys such as
`dependency`, `dependencies`, `depends_on`, and `application_dependencies`;
separate multiple names with commas or pipes. CSV enrichment can then add
owners, criticality, dependency IDs, and cleanup notes.

Generic CMDB or application-owner CSV exports can be converted into the
normalized workload metadata CSV before enrichment:

```powershell
python -m nmrcp.cli import-cmdb-metadata --export examples\sample_cmdb_export.csv --out outputs\cmdb-metadata.csv
python -m nmrcp.cli enrich-metadata --inventory examples\sample_inventory.json --metadata outputs\cmdb-metadata.csv --out outputs\cmdb-metadata-inventory.json
```

The converter maps common VM, CI, service-owner, criticality, backup, target
support, VirtIO, approval, and rollback-owner columns. It rejects endpoint URLs
and secret-like assignments so raw exports stay local and reviewable.

Unmatched dependency records are retained for cleanup and included in the
change-board summary. Dependency records without owners increase workload risk
so application teams cannot quietly skip unresolved dependencies.
If a CSV record matches an existing dependency by dependency ID or name, the
enricher updates that dependency in place instead of duplicating it.

If a workload depends on another internal workload that is blocked or requires
remediation, the dependent workload is held until the dependency is cleared.
Included workloads are written to `dependency-sequence.csv` in dependency-aware
order. See [dependency-sequence.md](dependency-sequence.md). Validate it with
`validate-dependency-sequence`; `change-gate` runs the same consistency check
automatically, including assessment-row binding for workload name, owner, and
readiness.

`migration-waves.csv` records one row per assessed workload with wave, owner,
target, readiness, risk, and top findings. See
[migration-waves.md](migration-waves.md). Validate it with
`validate-migration-waves`; `change-gate` runs the same consistency check
automatically.

`remediation-tracker.csv` turns every readiness finding into an owner-action row
with status, severity, recommended action, evidence reference, and closure
fields for final review. See [remediation-tracker.md](remediation-tracker.md).
Validate the generated tracker with `validate-remediation-tracker`;
`change-gate` runs the same consistency check automatically. Validate filled
closure rows with `validate-remediation`.

`migration-risk-register.csv` groups readiness findings by finding code so leads
can see repeated breakage patterns, affected owners, waves, and Move staging
blockers. See [migration-risk-register.md](migration-risk-register.md).
Validate it with `validate-risk-register`; `change-gate` runs the same
consistency check automatically and fails closed on unknown or duplicated wave
membership before wave-level risk is trusted.

`migration-waves.csv` records workload-level wave assignment. See
[migration-waves.md](migration-waves.md). Validate it with
`validate-migration-waves`; `change-gate` runs the same consistency check
automatically and fails closed on unknown or duplicate workload membership in
assessment waves.

`wave-readiness-summary.csv` rolls each migration wave into a change-board
go/hold view with readiness counts, risk, open findings, owners, Move staging
status, and the next gate. See
[wave-readiness-summary.md](wave-readiness-summary.md). Validate it with
`validate-wave-summary`; `change-gate` runs the same consistency check
automatically and fails closed on unknown or duplicate workload membership in
assessment waves.

`wave-execution-calendar.csv` turns each wave into an operator-facing review
window with entry gate, exit gate, owner groups, candidate and held workloads,
operator actions, and evidence references. See
[wave-execution-calendar.md](wave-execution-calendar.md). Validate it with
`validate-wave-execution-calendar`; `change-gate` runs the same consistency
check automatically by recomputing windows from the assessment workload rows and
waves, then rejecting CSV or embedded-context drift. Validation also fails
closed when assessment waves reference unknown workload IDs or place the same
workload in multiple waves.

`owner-risk-summary.csv` rolls readiness, risk, and finding severity up by owner
so migration leads can prioritize application-team follow-up. See
[owner-risk-summary.md](owner-risk-summary.md). Validate it with
`validate-owner-risk-summary`; `change-gate` runs the same consistency check
automatically and fails closed when assessment waves reference unknown workload
IDs or place the same workload in multiple waves.

`business-impact-summary.csv` rolls readiness and risk up by business tier so
executives and change boards can see whether critical, noncritical, or unknown
workload groups are ready, held, or blocked. See
[business-impact-summary.md](business-impact-summary.md). Validate it with
`validate-business-impact`; the validator binds redacted business tier context
to canonical assessment workload identity, owner, and wave membership, and
`change-gate` runs the same consistency check automatically.

`executive-readiness-brief.md` gives sponsors and change boards a concise
decision ask, migration posture, business-impact view, wave decisions, top
blockers, and evidence required before approval. See
[executive-readiness-brief.md](executive-readiness-brief.md). Validate it with
`validate-executive-brief`; `change-gate` runs the same assessment consistency
check automatically.

`owner-signoff-matrix.csv` lists one approval row per workload with pending
status, required sign-off roles, blocking reason, approval due milestone, and
evidence references. Final approved or waived rows must include `approval_ref`,
`approved_by`, and `approved_at` closure metadata. See
[owner-signoff-matrix.md](owner-signoff-matrix.md).
Validate the generated matrix with `validate-signoff-matrix`; `change-gate`
runs the same consistency check automatically. Validate filled approvals with
`validate-signoffs`.

`approval-exceptions.csv` records held workload, high-risk workload, and
high/critical finding exceptions that require formal risk acceptance or
role-based approval. See [approval-exceptions.md](approval-exceptions.md).
Validate it with `validate-approval-exceptions`; `change-gate` runs the same
consistency check automatically.

`partner-handoff-matrix.csv` maps evidence ownership and required review across
customer, partner, MSP, and operator roles. See
[partner-handoff-matrix.md](partner-handoff-matrix.md). Validate it with
`validate-partner-handoff`; `change-gate` runs the same consistency check
automatically by recomputing role rows from the assessment workload rows and
waves, then rejecting CSV or embedded-context drift. It also fails closed when
assessment waves reference unknown workload IDs or place the same workload in
multiple waves, so partner role ownership cannot be built from invented or
duplicated wave membership.
Validate filled final exception approvals with
`validate-approval-exception-approvals --assessment`; pass the approved register
to `change-gate`, `summarize-gates`, `package-handoff`, or `run-assessment`
with `--approval-exceptions` so closure is machine-checked and archived.

`operator-review.csv` records the migration lead/customer assessment review
before final handoff. Generate a draft with `generate-operator-review`, validate
filled reviews with `validate-operator-review`, and pass approved reviews into
`change-gate` and `package-handoff`. Final gates verify the review
`assessment_dir` matches the assessment being gated so stale reviews cannot be
reused across packages. See
[operator-review.md](operator-review.md).

`dependency-review.csv` records internal dependencies, external services,
unmatched dependency imports, owners, criticality, staging impact, blocker
codes, and required cleanup actions. See [dependency-review.md](dependency-review.md).
Validate it with `validate-dependency-review`; `change-gate` runs the same
consistency check automatically.

`connectivity-checklist.csv` records dependency owners, direction, protocol,
ports, validation method, connectivity status, and required firewall/DNS/app
validation actions. See [connectivity-checklist.md](connectivity-checklist.md).
Validate it with `validate-connectivity-checklist`; `change-gate` runs the same
consistency check automatically.

`identity-cutover-plan.csv` records hostname, DNS, redacted IP, source network,
identity status, and required identity validation actions for each workload.
See [identity-cutover-plan.md](identity-cutover-plan.md). Validate it with
`validate-identity-cutover-plan`; `change-gate` runs the same consistency check
automatically.

`compatibility-research.csv` records guest OS and vendor target-support status
for each workload so reviewers can clear AHV/NC2 support questions before
staging. See [compatibility-research.md](compatibility-research.md). Validate it
with `validate-compatibility-research`; `change-gate` runs the same consistency
check automatically.

Storage posture facts, when present, are scored for raw device mappings, shared
or multi-writer disks, independent disks, encrypted disks, and low source
datastore free space. See [readiness-signals.md](readiness-signals.md).

`recovery-readiness.csv` records backup protection, backup recency, source
snapshot posture, rollback ownership, recovery status, and required owner
actions before Move staging. See [recovery-readiness.md](recovery-readiness.md).
Validate it with `validate-recovery-readiness`; `change-gate` runs the same
consistency check automatically. Recovery context must match canonical workload
identity, readiness, and findings-derived recovery status/action before it is
trusted.

`rollback-plan.csv` records rollback owner, trigger criteria, recovery evidence,
rollback status, and required backout actions per workload. See
[rollback-plan.md](rollback-plan.md). Validate it with `validate-rollback-plan`;
`change-gate` runs the same consistency check automatically. Rollback context
must match canonical workload identity, valid wave membership, and
findings-derived recovery posture before backout criteria are trusted.

`move-staging-readiness.csv` combines readiness, tools, storage, recovery,
application-owner approval, and rollback-owner prerequisites into one
workload-level staging queue. `move-staging-brief.md` summarizes the same rows
for reviewer sign-off with include candidates, holds, blockers, evidence, and
stop conditions. See [move-staging-readiness.md](move-staging-readiness.md).
Validate them with `validate-move-staging-readiness` and
`validate-move-staging-brief`; `change-gate` runs the same consistency checks
automatically.

`migration-execution-queue.csv` rolls up wave order, Move-plan decision,
staging, compatibility, identity, connectivity, rollback, and workload
validation status into one operator execution queue. See
[migration-execution-queue.md](migration-execution-queue.md). Validate it with
`validate-migration-execution-queue`; `change-gate` runs the same consistency
check automatically. Queue context must match canonical workload identity and
valid wave membership before operator ordering is trusted.

`prism-category-mapping.csv` proposes review-only Prism/NCM categories for
owner, tier, readiness, wave intent, and source tags before target governance
work. See [prism-category-mapping.md](prism-category-mapping.md). Validate it
with `validate-prism-categories`; `change-gate` runs the same consistency check
automatically. Category context must match canonical workload identity and
readiness, and apply scope must remain review-only.

`stakeholder-communication-plan.csv` groups workloads by owner and wave so
operators can plan review-only stakeholder outreach with required evidence and
actions. See
[stakeholder-communication-plan.md](stakeholder-communication-plan.md).
Validate it with `validate-stakeholder-comms`; `change-gate` runs the same
consistency check automatically by recomputing rows from canonical workload
assessments and valid wave membership.

`what-will-break-report.csv` translates each readiness finding into a breakage
scenario, impact statement, operator signal, required action, and evidence
reference. `what-will-break-brief.md` turns the same rows into a short reviewer
brief with executive signal, top breakage scenarios, owner and wave holds,
evidence references, and stop conditions. See
[what-will-break-report.md](what-will-break-report.md). Validate them with
`validate-what-will-break` and `validate-what-will-break-brief`; both validators
rebuild from canonical assessment, wave, and inventory coverage context, and
`change-gate` runs the same consistency checks automatically.

`target-readiness-comparison.csv` compares each workload across AHV and NC2 with
readiness, risk, findings, and a preferred target decision hint. See
[target-readiness-comparison.md](target-readiness-comparison.md). Validate it
with `validate-target-comparison`; the validator binds the redacted comparison
context to canonical assessment workload identity and owner, and `change-gate`
runs the same consistency check automatically.

`target-reconciliation.csv` compares source Move-plan workloads against current
Prism inventory so included workloads do not collide with existing target VM
names. See [target-reconciliation.md](target-reconciliation.md).

`source-network-validation.csv` compares included Move-plan source network hints
against collected `vcenter-networks.json`. `run-assessment` creates it when
`--source-networks` is supplied. See
[source-network-validation.md](source-network-validation.md).

See [metadata-enrichment.md](metadata-enrichment.md) for CMDB/application-owner
enrichment before scoring.

## Inventory Validation

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-inventory --inventory outputs\enriched-inventory.json
python -m nmrcp.cli validate-inventory --inventory outputs\enriched-inventory.json --strict
```

Default mode fails only on structural errors. Strict mode also fails on warnings
such as missing owner, guest OS, backup, tools, networking, or capacity fields.
Assessment runs validation automatically; pass `--strict-inventory` when a
change-control process requires complete records before scoring.

## Live Collection Examples

Run a redacted live-readiness proof before writing live inventory files:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli live-readiness `
  --require-vcenter `
  --require-prism `
  --out outputs\live-readiness.json
```

The proof records read-only call names and counts without endpoint URLs,
usernames, passwords, or inventory details. See
[live-readiness.md](live-readiness.md).

Validate combined endpoint proof after collection:

```powershell
python -m nmrcp.cli validate-live-proof `
  --live-readiness outputs\source-collection\live-readiness.json `
  --collection-summary outputs\source-collection\collection-summary.json `
  --source-dir outputs\source-collection `
  --out outputs\source-collection\live-proof-validation.json
```

See [live-endpoint-proof.md](live-endpoint-proof.md).

Collect both vCenter and Prism Central source artifacts in one read-only step:

```powershell
python -m nmrcp.cli validate-assessment-intake `
  --intake outputs\assessment-intake.csv
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

This writes `vcenter-inventory.json`, `vcenter-networks.json`,
`prism-inventory.json`, `prism-capacity.json`, redacted
`collection-summary.json`, `collection-proof-manifest.json`, and
`collection-proof-report.md`. The manifest carries artifact hashes and the
read-only API allowlist so live proof validation can detect tampering or
out-of-scope collection paths. The Markdown report gives reviewers a redacted
brief with counts, API path names, TLS posture, intake binding, and stop
conditions. For external live proof closeout, `validate-live-proof` also
requires the assessment-intake checksum in the collection summary and proof
manifest to match. See [source-collection-workflow.md](source-collection-workflow.md)
and [collection-proof-report.md](collection-proof-report.md).

Collected inventory files also include non-secret `source.collection_audit`
metadata with read-only path names, configured limits, observed counts, and
`mutating_calls=0`. The audit block does not duplicate endpoint URLs, usernames,
passwords, or RVTools source labels. See
[collection-audit.md](collection-audit.md).

Validate the audit block before assessment or evidence packaging:

```powershell
python -m nmrcp.cli validate-collection-audit --inventory outputs\vcenter-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\prism-inventory.json
```

vCenter:

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_VCENTER_PASSWORD = "<local secret>"
python -m nmrcp.cli collect-vcenter --endpoint https://vcenter.example.com --username administrator@example.com --out outputs/vcenter-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs/vcenter-inventory.json
python -m nmrcp.cli assess --inventory outputs/vcenter-inventory.json --out outputs/vcenter-assessment
```

Prism Central:

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_PRISM_PASSWORD = "<local secret>"
python -m nmrcp.cli collect-prism --endpoint https://prism-central.example.com:9440 --username admin --out outputs/prism-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs/prism-inventory.json
python -m nmrcp.cli collect-prism-capacity --endpoint https://prism-central.example.com:9440 --username admin --out outputs/prism-capacity.json
```

## Stop Conditions

Do not proceed to migration execution when:

- A workload is in the `blocked` wave.
- Backup proof is missing.
- NSX dependency mapping is unresolved.
- A workload is powered off or suspended and the cold-migration path, guest
  validation, and owner approval are not explicitly confirmed.
- Guest OS or application vendor support is unconfirmed for a critical workload.
- Governance metadata is supplied and application owner approval is missing.
- Governance metadata is supplied and rollback ownership is missing.
- The change request does not include rollback criteria.

See [readiness-signals.md](readiness-signals.md) for the current deterministic
signals used by scoring and wave planning.

Use [readiness-policy.md](readiness-policy.md) when migration governance needs
custom snapshot, backup, or risk thresholds.

Use [inventory-coverage.md](inventory-coverage.md) to review captured, partial,
and missing migration facts before trusting wave assignments. Included Move
workloads with critical coverage gaps fail `validate-inventory-coverage` and
`change-gate`.

Use [target-capacity-fit.md](target-capacity-fit.md) with an approved target
capacity JSON to verify that included Move staging workloads fit within planned
AHV or NC2 CPU, memory, and storage headroom.

Use [target-reconciliation.md](target-reconciliation.md) with collected Prism
inventory to detect already-present target workloads or name collisions before
Move staging.

Use [target-network-mapping.md](target-network-mapping.md) with a Move payload
config to prove that every included workload network hint is mapped before dry
run payload generation or handoff.

Use [source-network-validation.md](source-network-validation.md) before target
mapping review to prove that included Move-plan source network hints exist in
the collected vCenter network inventory.

## Nutanix Move Planning Artifact

`nutanix-move-plan.csv` is generated with every assessment. It is a staging and
operator planning artifact for Nutanix Move workflows. It includes:

- include/hold decision.
- wave name.
- dependency-aware sequence artifact.
- source VM id and name.
- owner.
- target platform.
- readiness state and risk score.
- target network hints.
- dependency count.
- application owner approval state.
- rollback owner.
- precheck status.
- required action codes.

Treat it as the source-of-truth planning list until a verified Nutanix Move
import format is implemented and tested against the target Move version.
`move-plan-brief.md` is generated beside the CSV so reviewers can see include
and hold decisions, governance warnings, evidence references, and stop
conditions without reading every CSV column.

Validate the contract before handoff:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-move-plan --plan outputs\dependency-aware-assessment\nutanix-move-plan.csv
```

For handoff or change-board evidence, validate it against the assessment source
as well:

```powershell
python -m nmrcp.cli validate-move-plan `
  --plan outputs\dependency-aware-assessment\nutanix-move-plan.csv `
  --assessment outputs\dependency-aware-assessment\assessment.json
python -m nmrcp.cli validate-move-plan-brief `
  --brief outputs\dependency-aware-assessment\move-plan-brief.md `
  --plan outputs\dependency-aware-assessment\nutanix-move-plan.csv `
  --assessment outputs\dependency-aware-assessment\assessment.json
```

Assessment-bound validation rejects missing, extra, or stale source-bound
workload fields before the plan is staged for operator review.

See [move-plan-contract.md](move-plan-contract.md) and
[move-plan-brief.md](move-plan-brief.md).

For review-only Move API payload generation, see
[move-api-payload-dry-run.md](move-api-payload-dry-run.md).

For fail-closed lab-only review before any future Move API submitter, see
[move-submit-readiness.md](move-submit-readiness.md).

Use [source-endpoint-evidence-request.md](source-endpoint-evidence-request.md)
to scope the approved read-only vCenter and Prism Central validation request
before live endpoint evidence exists. It captures read-only calls, local
credential handling, required proof files, and `validate-live-proof` closeout
commands, but it is not proof by itself.

For redacted proof of non-production Move appliance behavior, see
[move-lab-proof.md](move-lab-proof.md). Simulated proof is allowed for local
smoke coverage, but only approved lab appliance proof should be passed to
`mvp-audit --move-proof`. Use `generate-move-lab-proof-template` to draft the
proof record before filling it from reviewed lab evidence.
Use [move-lab-evidence-request.md](move-lab-evidence-request.md) to scope the
approved lab window request before evidence exists. It captures lab-only scope,
dry-run-only controls, redaction rules, the required proof chain, and closeout
commands, but it is not proof by itself.
Use [move-lab-evidence-intake.md](move-lab-evidence-intake.md) after a real
approved lab run to tie the raw transcript, transcript validation, completed
proof, proof validation, and capture-kit validation into one fail-closed intake
record. Include the resulting file in `package-mvp-proof` and
`package-handoff` with `--move-lab-evidence-intake` for approved-lab external
handoff packages. Also pass it to `change-gate`, `summarize-gates`,
`mvp-audit`, or `run-assessment` whenever approved Move lab proof is supplied;
final gates fail approved proof without passing intake evidence.

Use [move-lab-readiness-packet.md](move-lab-readiness-packet.md) before the
approved lab window to bundle the reviewed payload, submit-readiness proof,
capture kit, preflight report, runbook, evidence request, and closure checklist
into one hash-addressed operator packet. The packet is not external proof; it
only proves the lab handoff inputs are ready and redacted before capture starts.

Use [move-lab-transcript.md](move-lab-transcript.md) to validate redacted API
round-trip transcript evidence from a real non-production Move appliance before
final approved proof is signed off. The same guide includes
`generate-move-lab-capture-kit`, which produces a template that intentionally
fails validation until replaced with captured approved lab evidence.

For structured pre/post validation evidence, see
[validation-results.md](validation-results.md).

## Docker Console

Use [docker.md](docker.md) to run the operations console as a local container.
The image serves the console over HTTP, exposes `/healthz`, and writes generated
site files under a host-mounted data volume.

## Operations Console

`operations-console.html` is generated with every assessment. It is a
self-contained local UI for operators to connect vCenter, Prism Central,
Nutanix Move, and RVTools/import sources, then review compatibility analysis,
readiness filters, wave placement, Move staging intent, and proof boundaries.

Validate the assessment-backed console contract with
`validate-operations-console`; `change-gate` runs the same check automatically.
See [operations-console.md](operations-console.md).

## Operator Portal

`operator-portal.html` is generated with every assessment. It is a
self-contained local landing page for the evidence set, linking the dashboard,
report, executive brief, change-board evidence, runbook, Move plan, validation
checklist, Move lab closure checklist, what-will-break brief, external proof
plan, and evidence manifest.

Validate the assessment-backed portal contract with `validate-operator-portal`;
`change-gate` runs the same check automatically. The validator checks the HTML
shell, `nmrcp_operator_portal_v1` payload schema, summary counts, artifact
links, required local artifact presence, redacted evidence posture, external
proof plan contract visibility, approved Move proof contract visibility, and
sample endpoint/email leakage. See [operator-portal.md](operator-portal.md).

## Operator Report

`change-board-evidence.md` is generated with every assessment. Validate the
assessment-backed evidence contract with `validate-change-board-evidence`;
`change-gate` runs the same check automatically. The validator checks executive
summary counts, collection audit proof, read-only API paths, migration waves,
workload readiness details, generated finding actions, redaction markers, and
zero mutating collection calls.

`operator-report.html` is generated with every assessment. It is a self-contained
local HTML report with the executive summary, migration waves, workload
readiness, findings, and redacted source metadata. Review it before attaching it
to a change request.

Validate the assessment-backed report contract with `validate-operator-report`;
`change-gate` runs the same check automatically. The validator checks report
sections, summary counts, collection audit proof, read-only API paths, wave
cards, workload readiness cards, generated finding actions, redacted source
metadata, and sample secret/endpoint leakage.

## Operator Dashboard

`operator-dashboard.html` is generated with every assessment. It is a
self-contained local work queue with readiness, owner, wave, and finding search
filters for operator triage. It does not require a server and remains part of
the evidence manifest, evidence bundle, change gate, and handoff package.

Validate the embedded dashboard payload with `validate-operator-dashboard`;
`change-gate` runs the same check automatically. The validator checks the HTML
shell, `nmrcp_operator_dashboard_v1` payload schema, summary counts, workload
rows, wave assignments, Move staging intent, finding actions, operator stop
conditions, and sample endpoint or email leakage.

## Operator Gate Summary

`operator-gate-summary.md` is generated by `run-assessment` after optional gates
are evaluated. Use `summarize-gates` after standalone assessment runs to create
the same readable gate rollup, including generated source endpoint and Move lab
evidence-request checks plus Move lab capture-kit preflight validation when
supplied. See
[operator-gate-summary.md](operator-gate-summary.md).

## Migration Runbook

`migration-runbook.md` is generated with every assessment. It turns readiness
findings into a wave-ordered operator plan with universal stop conditions,
include/hold intent, target network hints, governance facts, dependency
coordination details, and required actions per workload.

Validate the assessment-backed runbook contract with
`validate-migration-runbook`; `change-gate` runs the same check automatically.
The validator checks required sections, universal stop conditions, evidence
handoff references, workload identity, wave assignment, owner, target,
readiness, risk, staging intent, and generated finding actions.

Treat it as a human-reviewed runbook. It does not execute migration actions or
submit anything to Nutanix Move.

## Validation Results

`pre-post-validation-checklist.md` is generated with every assessment. Validate
the generated checklist contract with `validate-validation-checklist`;
`change-gate` runs the same check automatically. The checklist must retain
pre-migration, cutover, and post-migration sections, evidence capture, rollback
criteria, and the stop condition for excluded or blocked workloads.

`workload-validation-checklist.csv` turns that checklist into workload-level
pre-migration, cutover, and post-migration validation rows with required
evidence, stop conditions, and staging-derived status. Validate it with
`validate-workload-validation-checklist`; `change-gate` runs the same
assessment-backed contract automatically.

`migration-execution-queue.csv` is the execution-facing rollup of those
workload statuses and the supporting compatibility, identity, connectivity, and
rollback evidence.

Use `generate-validation-template` to create a pre/post validation CSV for
workloads included in the Move staging plan. Use `validate-validation-results`
for draft or final review. Final review fails closed on unchecked or failed
checks.

## Evidence Manifest

`evidence-manifest.json` is generated with every assessment. It records
`nmrcp_evidence_manifest_v1`, generation time, artifact names, sizes, and
SHA-256 hashes for the core evidence bundle. Use it to confirm files were not
changed after handoff.

The dry-run Move API payload is generated after assessment and is not included in
the core evidence manifest. The generated migration runbook is included in the
core evidence bundle. `inventory-coverage.csv` is also included so receivers can
review data-quality gaps.

Package the core evidence bundle:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli verify-evidence --dir outputs\dependency-aware-assessment
python -m nmrcp.cli review-evidence --dir outputs\dependency-aware-assessment
python -m nmrcp.cli package-evidence --dir outputs\dependency-aware-assessment --out outputs\dependency-aware-evidence-bundle.zip
python -m nmrcp.cli verify-evidence --bundle outputs\dependency-aware-evidence-bundle.zip
```

Send the zip and keep the manifest inside it. The receiver can run
`verify-evidence --bundle` to confirm no artifact changed after handoff and
that no extra archive entries were added outside `evidence-manifest.json`.
Use [evidence-redaction-review.md](evidence-redaction-review.md) before sharing
evidence outside the migration workspace.

Use [change-gate.md](change-gate.md) before handing an evidence package to a
change board or before closing a migration change.
Use [change-gate-warning-acceptance.md](change-gate-warning-acceptance.md)
when a reviewer needs to formally accept remaining warning-level findings for
MVP handoff review.

Create a closure-ready handoff package when the receiver needs the assessment
artifacts, evidence bundle, final validation results, and reviewed dry-run Move
payload in one sealed archive. Include the Move lab capture kit and validation
proof when the handoff also needs preflight evidence for the approved lab
capture window:

```powershell
python -m nmrcp.cli package-handoff `
  --dir outputs\dependency-aware-assessment `
  --bundle outputs\dependency-aware-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --move-lab-capture-kit outputs\move-lab-capture-kit `
  --move-lab-capture-validation outputs\move-lab-capture-kit-validation.json `
  --move-lab-readiness-packet outputs\move-lab-readiness-packet.json `
  --source-collection-plan outputs\source-collection-plan.md `
  --move-payload outputs\dependency-aware-assessment\move-api-payload.dry-run.json `
  --out outputs\dependency-aware-handoff-package.zip
python -m nmrcp.cli verify-handoff --package outputs\dependency-aware-handoff-package.zip
```

See [handoff-package.md](handoff-package.md) for the package layout and
verification behavior.

## Evidence Review

Review generated Markdown and CSV before external distribution. Redaction removes
common sensitive values, but operators remain responsible for confirming that no
customer-sensitive data leaves the approved migration workspace.

## GitHub Readiness

Use [github-readiness.md](github-readiness.md) before publishing or opening pull
requests. It documents CODEOWNERS, issue templates, pull-request verification,
security scan expectations, and the residual approved Move appliance proof gap.
Run `python -m nmrcp.cli github-readiness --repo-root .` to verify required
publication files, the expected GitHub origin, tracked Git paths, and generated
artifacts that must remain untracked.

## Vault Readiness

Use [vault-readiness.md](vault-readiness.md) before claiming repository work has
also been documented in the Obsidian vault. Run
`python -m nmrcp.cli vault-readiness --repo-root .` to verify operation-guide
coverage, required vault notes, nonempty note content, and vault README wiki
links.

## Product Readiness

Use [product-readiness.md](product-readiness.md) as the aggregate completion
gate. It combines MVP audit, GitHub publication readiness, and vault
documentation readiness, then prints the next actions that still prevent the
product from being considered complete.

## Publication Handoff

Use [publication-handoff.md](publication-handoff.md) to package the current
GitHub publication review, product-readiness report, smoke transcript, and
security-scan result into a branch-owner handoff record. The handoff validates
local publication evidence only; external handoff remains blocked until
approved endpoint and Nutanix Move appliance proof are present.

## Publication Staging

Use [publication-staging.md](publication-staging.md) to generate and validate a
non-mutating staging manifest with SHA-256 hashes, tracked-state evidence, local
forbidden-to-stage candidates, and the reviewed `git add -- ...` command. The
manifest supports operator review before any Git staging action.

## Pull Request Readiness

Use [pull-request-readiness.md](pull-request-readiness.md) to validate the
current publication review, product-readiness report, publication handoff,
staging manifest, smoke log, and security scan into a branch-owner packet before
operator-controlled staging and pull-request creation.

## External Proof Gap Plan

Use [external-proof-plan.md](external-proof-plan.md) to create and validate the
approved live endpoint and Nutanix Move proof closeout plan. The plan keeps
external handoff blocked until `nmrcp_live_endpoint_proof_v1`,
`nmrcp_move_lab_proof_validation_v1`, and
`nmrcp_move_lab_evidence_intake_v1` pass from approved evidence.
