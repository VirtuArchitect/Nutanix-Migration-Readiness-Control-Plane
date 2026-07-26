# Nutanix Migration & Readiness Control Plane

Know exactly what will break before you migrate from VMware to Nutanix.

## Console Demo

Open the static operator console preview:
[Operations Console Demo](https://virtuarchitect.github.io/Nutanix-Migration-Readiness-Control-Plane/)

The demo is generated from sample inventory only. It does not contact vCenter,
Prism Central, Nutanix Move, AHV, NC2, or any customer environment.

## Docker Console

Run the local operations console in Docker:

```powershell
docker compose up --build
```

Then open `http://localhost:8080/`. The container serves the same local-first
console and health endpoint without contacting infrastructure by itself. In
served mode, testers can use the browser to test approved read-only vCenter and
Prism Central connections, collect local source evidence, and run readiness
against collected inventory. See `docs/operations/docker.md` and the
tester-facing quickstart in `docs/operations/tester-quickstart.md`.

This project is a local-first readiness and evidence layer for teams planning
VMware-to-Nutanix AHV or NC2 migrations. It does not replace Nutanix Move,
Prism, or Nutanix Cloud Manager. It prepares operators, partners, and change
boards before migration execution by producing an evidence-backed readiness
score, migration waves, and pre/post validation checklists.

## MVP Scope

- Connect to vCenter and Prism Central in read-only mode.
- Inventory workloads, networks, storage posture, guest OS details, snapshots,
  tools/drivers, tags, ownership, and dependencies.
- Score each workload for AHV/NC2 migration readiness.
- Generate migration waves and change-board evidence.
- Export a Nutanix Move-ready planning CSV plus validation checklists.
- Keep secrets local and redact evidence by default.

The current implementation provides the first local MVP slice: it reads a
normalized inventory JSON file, scores migration readiness, creates waves, and
exports redacted evidence artifacts. Connector modules are included as
read-only stdlib HTTP building blocks so live discovery can be expanded without
introducing runtime dependencies.

## Quick Start

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli generate-assessment-intake --out outputs\assessment-intake.csv
python -m nmrcp.cli validate-assessment-intake --intake examples\sample_assessment_intake.csv
python -m nmrcp.cli source-collection-plan --intake examples\sample_assessment_intake.csv --out outputs\source-collection-plan.md
python -m nmrcp.cli validate-source-collection-plan --plan outputs\source-collection-plan.md --intake examples\sample_assessment_intake.csv
python -m nmrcp.cli assess --inventory examples/sample_inventory.json --out outputs/sample-assessment
```

For approved live collection, pass a completed intake to `collect-sources` with
`--assessment-intake`. The command validates the kickoff acknowledgements before
connecting and records only validation metadata plus the intake SHA-256 in the
redacted collection proof.
Generate and validate `source-collection-plan.md` before the approved access
window when operators need a credential-safe preparation brief. The collection
run also writes `collection-proof-report.md`, a redacted Markdown brief that
summarizes read-only checks, API path names, TLS posture, intake binding, and
stop conditions for reviewer use.

For repeated local use, install the package in editable mode and use the
console command:

```powershell
python -m pip install -e .
nmrcp doctor
nmrcp assess --inventory examples/sample_inventory.json --out outputs/sample-assessment
```

The docs keep `python -m nmrcp.cli` examples because they also work from a
fresh clone with only `PYTHONPATH=src`; the installed `nmrcp` command routes to
the same CLI entry point.
On Windows, if `pip` warns that the user Scripts directory is not on `PATH`,
launch it by absolute path or add that Scripts directory to `PATH`:

```powershell
$scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))"
& (Join-Path $scripts 'nmrcp.exe') doctor
```

For external lab testers, start with
`docs/operations/tester-quickstart.md`. It covers the Docker and Python console
paths, the expected connection workflow, redaction rules, and what evidence to
include in a tester connection report. After a local console run, testers can
select **Prepare Tester Report** in the UI or run `tester-report` from the CLI
to generate a redacted local feedback summary.

Run the full assessment-to-handoff workflow:

```powershell
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

This validates inventory, scores readiness, writes evidence, validates the Move
plan, creates the validation template, optionally creates the dry-run Move
payload, verifies/packages evidence, runs the change gate, and creates the final
handoff package. See `docs/operations/assessment-workflow.md`.

Audit local MVP evidence and remaining proof gaps:

```powershell
python -m nmrcp.cli mvp-audit `
  --repo-root . `
  --assessment-dir outputs\workflow-assessment `
  --assessment-intake examples\sample_assessment_intake.csv `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --evidence-bundle outputs\smoke-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json `
  --warning-acceptance examples\sample_change_gate_warning_acceptance.csv `
  --out outputs\mvp-audit.json
```

See `docs/operations/mvp-readiness-audit.md`. The `--live-proof` file must be
generated by `validate-live-proof` with passing read-only security,
assessment-intake binding, collection privacy, proof-manifest security, API
allowlist, and manifest checksum-match checks; a status-only proof JSON is
rejected as stale evidence.

Prepare the approved Move lab window with a single pre-lab handoff packet:

```powershell
python -m nmrcp.cli move-lab-readiness-packet `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --move-submit-readiness outputs\smoke\move-submit-readiness.json `
  --capture-kit outputs\smoke\move-lab-capture-kit `
  --capture-kit-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --evidence-preflight outputs\smoke\move-lab-evidence-preflight.json `
  --evidence-preflight-report outputs\smoke\move-lab-evidence-preflight.md `
  --runbook outputs\smoke\move-lab-execution-runbook.md `
  --evidence-request outputs\smoke\move-lab-evidence-request.md `
  --closure-checklist outputs\smoke\move-lab-closure-checklist.md `
  --out outputs\smoke\move-lab-readiness-packet.json `
  --report outputs\smoke\move-lab-readiness-packet.md
```

See `docs/operations/move-lab-readiness-packet.md`. This packet is a readiness
handoff artifact only; final closure still requires approved non-production Move
appliance evidence and passing evidence intake. Include it in `package-handoff`
with `--move-lab-readiness-packet` when the receiver needs the pre-lab operator
handoff evidence alongside the capture kit.

Package the current MVP proof posture into one verifiable zip:

```powershell
python -m nmrcp.cli package-mvp-proof `
  --mvp-audit outputs\smoke-mvp-audit.json `
  --live-proof outputs\smoke-live-proof-validation.json `
  --move-submit-readiness outputs\smoke\move-submit-readiness.json `
  --move-lab-transcript outputs\smoke\move-lab-transcript-validation.json `
  --move-lab-proof outputs\smoke\move-lab-proof-validation.simulated.json `
  --move-lab-runbook outputs\smoke\move-lab-execution-runbook.md `
  --move-lab-closure-checklist outputs\smoke\move-lab-closure-checklist.md `
  --move-lab-capture-kit outputs\smoke\move-lab-capture-kit `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --move-lab-readiness-packet outputs\smoke\move-lab-readiness-packet.json `
  --source-collection-plan outputs\source-collection-plan.md `
  --source-endpoint-evidence-request outputs\smoke\source-endpoint-evidence-request.md `
  --move-lab-evidence-request outputs\smoke\move-lab-evidence-request.md `
  --external-proof-plan outputs\external-proof-plan.json `
  --operator-gate-summary outputs\smoke\operator-gate-summary.md `
  --handoff-package outputs\smoke-handoff-package.zip `
  --out outputs\smoke-mvp-proof-package.zip
```

See `docs/operations/mvp-proof-package.md`.

`verify-mvp-proof` checks hashes and semantic role coverage, including the
required `mvp_audit` role and known archive paths for optional proof artifacts.
It also validates packaged proof schemas and acceptable statuses for each JSON
proof role. Packaged live endpoint proof must include the passing
assessment-intake binding and proof-manifest checksum-match checks from
`validate-live-proof`; a stale status-only proof is rejected. The verifier also
validates the Move lab closure checklist when packaged.
It also validates packaged Move lab readiness packets as pre-lab handoff
evidence; final closure still requires approved appliance proof and evidence
intake. The package can also carry `proof/source-collection-plan.md` so
reviewers see the no-contact read-only collection sequence and privacy posture,
and `proof/external-proof-plan.json` so reviewers see the combined approved
endpoint and Nutanix Move proof closeout path.
Use `summarize-mvp-proof` to create a reviewer-facing Markdown report from the
package:

```powershell
python -m nmrcp.cli summarize-mvp-proof `
  --package outputs\smoke-mvp-proof-package.zip `
  --out outputs\smoke-mvp-proof-summary.md
```

Create a partner/customer-facing launch readiness brief from the same proof
package:

```powershell
python -m nmrcp.cli launch-readiness-report `
  --package outputs\smoke-mvp-proof-package.zip `
  --repo-url https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --out outputs\smoke-launch-readiness-report.md `
  --json-out outputs\smoke-launch-readiness-report.json
```

See `docs/operations/launch-readiness-report.md`.

Run the Move lab proof workflow after a real approved lab appliance proof record
is available:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
powershell -ExecutionPolicy Bypass -File scripts\move_lab_proof_workflow.ps1 `
  -AssessmentDir outputs\sample-assessment `
  -MovePayload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  -MoveLabTranscript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  -MoveLabProof outputs\move-lab-proof.approved.json `
  -GenerateApprovedProof `
  -ApprovedBy "Lab Migration Lead" `
  -MoveLabTranscriptValidation outputs\move-lab-transcript-validation.json `
  -MoveLabEvidenceIntake outputs\move-lab-evidence-intake.json `
  -MoveSubmitReview examples\sample_move_submit_review.json `
  -LiveProof outputs\source-collection\live-proof-validation.json `
  -MvpAudit outputs\mvp-audit.json `
  -MvpProofPackage outputs\mvp-proof-package.zip `
  -MvpClosureReport outputs\mvp-closure-report.md `
  -LaunchReadinessReport outputs\launch-readiness-report.md `
  -LaunchRepoUrl https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

See `docs/operations/move-lab-proof-workflow.md`.

After a real approved lab run, the workflow can also write
`nmrcp_move_lab_evidence_intake_v1` evidence. To run the intake gate directly:

```powershell
python -m nmrcp.cli move-lab-evidence-preflight `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --capture-kit-validation outputs\move-lab-capture-kit-validation.json `
  --transcript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --proof outputs\move-lab-proof.approved.json `
  --proof-validation outputs\move-lab-proof-validation.json `
  --evidence-intake outputs\move-lab-evidence-intake.json `
  --out outputs\move-lab-evidence-preflight.json `
  --report outputs\move-lab-evidence-preflight.md
```

Use the preflight report before the approved lab window; it does not replace the
final evidence intake after the captured transcript and approved proof are
complete.

```powershell
python -m nmrcp.cli validate-move-lab-evidence-intake `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --proof outputs\move-lab-proof.approved.json `
  --proof-validation outputs\move-lab-proof-validation.json `
  --capture-kit-validation outputs\move-lab-capture-kit-validation.json `
  --out outputs\move-lab-evidence-intake.json
```

Include that file in `package-mvp-proof` and `package-handoff` with
`--move-lab-evidence-intake` for approved-lab external handoff packages. Also
pass it to `change-gate`, `summarize-gates`, `mvp-audit`, or `run-assessment`
whenever approved Move lab proof is supplied; final gates fail approved proof
without passing intake evidence.

Generate the redacted Move lab execution runbook before the approved proof
window:

```powershell
python -m nmrcp.cli generate-move-lab-runbook `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --proof-template outputs\sample-assessment\move-lab-proof.template.json `
  --out outputs\sample-assessment\move-lab-execution-runbook.md
```

See `docs/operations/move-lab-runbook.md`.

Optional readiness policy:

```powershell
python -m nmrcp.cli assess `
  --inventory examples/sample_inventory.json `
  --policy examples/sample_readiness_policy.json `
  --out outputs/policy-assessment
```

The command writes:

- `assessment.json`: full readiness model with risk findings.
- `inventory-coverage.csv`: per-workload data-quality coverage for required
  migration facts, including governance evidence.
- `migration-waves.csv`: wave plan suitable for migration planning.
  Validate it with `validate-migration-waves`; `change-gate` runs the same
  consistency check automatically and fails closed on unknown or duplicate
  workload membership in assessment waves.
- `wave-readiness-summary.csv`: wave-level go/hold summary with readiness
  counts, risk, blockers, owners, and next gate. Validation fails closed on
  unknown or duplicate workload membership in assessment waves.
- `wave-execution-calendar.csv`: operator-facing wave calendar with execution
  sequence, window type, go/hold status, entry/exit gates, actions, and
  evidence refs. Validate it with `validate-wave-execution-calendar`;
  `change-gate` runs the same assessment-backed contract automatically by
  recomputing windows from the assessment workload rows and waves. Validation
  fails closed on unknown or duplicate workload membership in assessment waves.
- `partner-handoff-matrix.csv`: role-based partner/MSP/customer handoff matrix
  that maps evidence ownership, required review, blocking condition, and next
  action. Validate it with `validate-partner-handoff`; `change-gate` runs the
  same assessment-backed contract automatically by recomputing roles from the
  assessment workload rows and waves.
- `move-lab-evidence-request.md`: partner/MSP/change-board request for the
  approved non-production Move appliance proof window, including lab scope,
  controls, required evidence, closeout commands, and stop conditions. Validate
  it with `validate-move-lab-evidence-request`; `change-gate` runs the same
  contract automatically.
- `source-endpoint-evidence-request.md`: operator/partner request for approved
  read-only vCenter and Prism Central validation, including source scope,
  credential-safe controls, required live proof artifacts, closeout commands,
  and stop conditions. Validate it with
  `validate-source-endpoint-evidence-request`; `change-gate` runs the same
  contract automatically.
- `target-readiness-comparison.csv`: AHV versus NC2 readiness and target
  preference view.
  Validate it with `validate-target-comparison`; `change-gate` runs the same
  consistency check automatically.
- `dependency-sequence.csv`: dependency-aware order for included workloads.
  Validate it with `validate-dependency-sequence`; `change-gate` runs the same
  consistency check automatically, including assessment-row binding for
  workload name, owner, and readiness.
- `dependency-review.csv`: dependency register for internal, external, and
  unmatched dependency records with owners, criticality, staging impact, and
  cleanup actions. Validate it with `validate-dependency-review`; `change-gate`
  runs the same consistency check automatically.
- `connectivity-checklist.csv`: dependency connectivity queue with owners,
  direction, protocol, ports, validation method, and required firewall/DNS/app
  validation actions. Validate it with `validate-connectivity-checklist`;
  `change-gate` runs the same consistency check automatically.
- `identity-cutover-plan.csv`: workload hostname, DNS, IP, and source-network
  validation queue for cutover identity preservation. Validate it with
  `validate-identity-cutover-plan`; `change-gate` runs the same consistency
  check automatically.
- `compatibility-research.csv`: guest OS and vendor target-support research
  queue for AHV/NC2 review. Validate it with
  `validate-compatibility-research`; `change-gate` runs the same consistency
  check automatically.
- `tools-driver-readiness.csv`: guest tools and Nutanix VirtIO readiness for
  each workload. Validate it with `validate-tools-driver-readiness`;
  `change-gate` runs the same consistency check automatically.
- `storage-posture.csv`: source storage risk view for RDMs, shared disks,
  independent disks, encryption, datastores, and free-space posture. Validate it
  with `validate-storage-posture`; `change-gate` runs the same consistency
  check automatically.
- `recovery-readiness.csv`: backup, snapshot, and rollback-owner readiness view
  before Nutanix Move staging. Validate it with
  `validate-recovery-readiness`; `change-gate` runs the same consistency check
  automatically. Recovery context must match canonical workload identity,
  readiness, and findings-derived recovery status/action before it is trusted.
- `rollback-plan.csv`: per-workload rollback owner, trigger, recovery evidence,
  and stop-criteria view. Validate it with `validate-rollback-plan`;
  `change-gate` runs the same consistency check automatically. Rollback context
  must match canonical workload identity, valid wave membership, and
  findings-derived recovery posture before backout criteria are trusted.
- `move-staging-readiness.csv`: single staging queue that combines readiness,
  tools, storage, recovery, owner approval, and rollback-owner prerequisites.
  Validate it with `validate-move-staging-readiness`; `change-gate` runs the
  same consistency check automatically.
- `move-staging-brief.md`: reviewer-ready Move staging summary generated from
  the same rows with include candidates, holds, blockers, evidence, and stop
  conditions. Validate it with `validate-move-staging-brief`; `change-gate`
  runs the same contract automatically.
- `migration-execution-queue.csv`: operator queue that rolls up wave order,
  Move-plan decision, staging, compatibility, identity, connectivity, rollback,
  and validation status. Validate it with `validate-migration-execution-queue`;
  `change-gate` runs the same consistency check automatically. Queue context
  must match canonical workload identity and valid wave membership before
  operator ordering is trusted.
- `prism-category-mapping.csv`: review-only Prism/NCM category plan derived
  from workload owner, tier, readiness, and source tags. Validate it with
  `validate-prism-categories`; `change-gate` runs the same assessment-backed
  category contract automatically. Category context must match canonical
  workload identity and readiness, and apply scope must remain review-only.
- `stakeholder-communication-plan.csv`: owner and wave communication plan that
  maps readiness state to audience, evidence references, and required actions.
  Validate it with `validate-stakeholder-comms`; `change-gate` runs the same
  assessment-backed contract automatically by recomputing rows from canonical
  workload assessments and valid wave membership.
- `what-will-break-report.csv`: workload-level breakage report that translates
  readiness findings into failure scenarios, impact, operator signal, required
  action, and evidence references. Validate it with `validate-what-will-break`;
  `change-gate` runs the same assessment-backed contract automatically.
- `what-will-break-brief.md`: sponsor/app-owner/change-board summary generated
  from the same breakage rows with executive signal, top scenarios, owner and
  wave holds, evidence references, and stop conditions. Validate it with
  `validate-what-will-break-brief`; `change-gate` runs the same contract
  automatically.
- `remediation-tracker.csv`: owner-action tracker for every readiness finding.
  Validate the generated tracker with `validate-remediation-tracker`; validate
  filled closure rows with `validate-remediation`.
- `migration-risk-register.csv`: estate-wide finding-code rollup showing
  repeated breakage patterns, affected owners, waves, and Move staging blockers.
  Validate it with `validate-risk-register`; `change-gate` runs the same
  consistency check automatically. Validation fails closed on unknown or
  duplicated wave membership before wave-level risk is trusted.
- `owner-risk-summary.csv`: owner-level readiness, risk, and next-action rollup.
  Validate it with `validate-owner-risk-summary`; `change-gate` runs the same
  consistency check automatically. Validation fails closed on unknown or
  duplicate workload membership in assessment waves.
- `business-impact-summary.csv`: tier-level executive impact rollup showing
  critical estate readiness, held workloads, owners, and go/hold status.
- `owner-signoff-matrix.csv`: workload-level approval register for application,
  migration, rollback, dependency, network, backup, cloud, and risk sign-offs.
  Final approved or waived rows must include `approval_ref`, `approved_by`, and
  `approved_at`. Validate the generated matrix with `validate-signoff-matrix`;
  validate filled approvals with `validate-signoffs`.
- `approval-exceptions.csv`: formal exception register for held workloads,
  high-risk workloads, and high/critical findings. Validate it with
  `validate-approval-exceptions`; `change-gate` runs the same consistency check
  automatically. Validate a filled final exception register with
  `validate-approval-exception-approvals --assessment`, then pass it to closure
  gates with `--approval-exceptions`.
- `nutanix-move-plan.csv`: Nutanix Move staging plan with include/hold flags
  and governance handoff fields.
- `move-plan-brief.md`: reviewer-facing summary of the Move plan include and
  hold decisions, governance warnings, evidence references, and stop conditions.
  Validate it with `validate-move-plan-brief`; `change-gate` runs the same
  source-bound contract automatically.
- `executive-readiness-brief.md`: leadership-ready decision brief summarizing
  Move staging posture, business impact, top blockers, and approval evidence.
- `target-capacity-fit.csv`: optional target headroom check for included Move
  staging workloads when `--capacity` is supplied.
- `target-reconciliation.csv`: optional source-to-Prism inventory collision
  check when `--prism-inventory` is supplied.
- `source-network-validation.csv`: optional proof that included Move workload
  source network hints exist in collected vCenter network inventory.
- `target-network-mapping.csv`: optional proof that included Move workloads have
  source-to-target network mappings when `--move-config` is supplied.
- `change-board-evidence.md`: redacted executive/operator evidence pack.
  Validate it with `validate-change-board-evidence`; `change-gate` runs the
  same assessment-backed evidence contract automatically.
- `migration-runbook.md`: wave-ordered operator runbook with stop conditions,
  governance facts, dependency coordination, and required actions.
  Validate it with `validate-migration-runbook`; `change-gate` runs the same
  assessment-backed operator contract automatically.
- `operations-console.html`: self-contained local operations console with
  vCenter, Prism Central, Nutanix Move, and RVTools/import connection panels,
  compatibility analysis filters, and Move-plan workbench actions. Validate it
  with `validate-operations-console`; `change-gate` runs the same
  assessment-backed console contract automatically.
- `operator-portal.html`: self-contained local landing page that links the
  dashboard, report, executive brief, change-board evidence, runbook, Move
  plan, validation checklist, closure checklist, and manifest. Validate it with
  `validate-operator-portal`; `change-gate` runs the same assessment-backed
  portal contract automatically.
- `operator-report.html`: self-contained local report for operators and change
  boards.
  Validate it with `validate-operator-report`; `change-gate` runs the same
  assessment-backed HTML report contract automatically.
- `operator-dashboard.html`: self-contained local dashboard for filtering the
  workload queue by readiness, owner, wave, and finding text.
  Validate it with `validate-operator-dashboard`; `change-gate` runs the same
  assessment-backed dashboard payload contract automatically.
- `operator-gate-summary.md`: optional readable rollup of source endpoint and
  Move lab request checks, capacity, reconciliation, source network validation,
  network mapping, validation, remediation, sign-off, and operator-review
  gates.
- `pre-post-validation-checklist.md`: validation checklist for cutover.
  Validate it with `validate-validation-checklist`; `change-gate` runs the
  same generated-checklist contract automatically.
- `workload-validation-checklist.csv`: workload-level pre-migration, cutover,
  and post-migration evidence queue tied to Move staging status. Validate it
  with `validate-workload-validation-checklist`; `change-gate` runs the same
  assessment-backed contract automatically.
- `evidence-manifest.json`: SHA-256 checksums and sizes for the core evidence
  bundle.

## Dependency Enrichment

Application, database, network, and external-service dependencies can be merged
from CSV before scoring:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli enrich-dependencies `
  --inventory examples/sample_inventory.json `
  --dependencies examples/sample_dependencies.csv `
  --out outputs/enriched-inventory.json
python -m nmrcp.cli assess `
  --inventory outputs/enriched-inventory.json `
  --out outputs/enriched-assessment
```

You can also pass dependencies directly to assessment:

```powershell
python -m nmrcp.cli assess `
  --inventory examples/sample_inventory.json `
  --metadata examples/sample_metadata.csv `
  --dependencies examples/sample_dependencies.csv `
  --out outputs/dependency-aware-assessment
```

Dependency CSV columns:

```text
source_id,source_name,dependency_name,dependency_id,dependency_type,owner,criticality,protocol,ports,direction,validation_method,notes
```

The connectivity fields are optional, but when supplied they feed
`connectivity-checklist.csv` for firewall, DNS, routing, and application
reachability validation.

Application dependency maps can be converted to this CSV format:

```powershell
python -m nmrcp.cli import-app-map `
  --map examples\sample_app_map.json `
  --out outputs\app-map-dependencies.csv
```

`source_id` or `source_name` is used to match a workload. Unmatched dependency
records are retained in the enriched inventory and summarized in the change-board
evidence. If an imported dependency matches an existing workload dependency by
dependency ID or name, enrichment updates the existing dependency instead of
creating a duplicate.

Workload metadata can also be merged from CMDB or application-owner exports:

```powershell
python -m nmrcp.cli import-cmdb-metadata `
  --export examples\sample_cmdb_export.csv `
  --out outputs\cmdb-metadata.csv
python -m nmrcp.cli enrich-metadata `
  --inventory examples/sample_inventory.json `
  --metadata outputs\cmdb-metadata.csv `
  --out outputs/metadata-inventory.json
```

Metadata CSV columns:

```text
source_id,source_name,owner,tier,tags,backup_protected,backup_last_success_hours,vendor_support,virtio_ready,application_owner_approved,rollback_owner,notes
```

See `docs/operations/metadata-enrichment.md`.

Dependency gates are applied after base readiness scoring. If a workload depends
on another internal workload that is blocked or still needs remediation, the
dependent workload is held in `prepare` until the dependency is cleared. Included
workloads are also ordered in `dependency-sequence.csv` so dependencies appear
before dependent applications.

Current readiness signals include guest OS, NSX, VDS, storage posture, snapshots,
snapshot age, VMware Tools presence/status, guest IP/DNS identity, VirtIO readiness, backup proof,
backup age, vendor support, governance metadata, and dependency
ownership/readiness. See
`docs/operations/readiness-signals.md`. App-map import is documented in
`docs/operations/application-map-import.md`. Thresholds can be tuned with a local
readiness policy JSON; see `docs/operations/readiness-policy.md`.
Use `docs/operations/inventory-coverage.md` to interpret captured versus missing
inventory facts. `validate-inventory-coverage` and `change-gate` fail included
Move workloads when critical coverage fields are missing or partial.

Generate and validate an operator assessment review before final handoff:

```powershell
python -m nmrcp.cli generate-operator-review `
  --dir outputs\sample-assessment `
  --out outputs\sample-operator-review.csv
python -m nmrcp.cli validate-operator-review `
  --review outputs\sample-operator-review.csv `
  --allow-draft
```

Approved reviews can be passed to `change-gate`, `summarize-gates`,
`package-handoff`, and `run-assessment`. Final gates bind approved reviews to
the assessment directory being gated, so the `assessment_dir` column must match
that assessment rather than a stale or copied review from another package. See
`docs/operations/operator-review.md`.

## Inventory Validation

Validate normalized inventory before assessment:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-inventory --inventory examples/sample_inventory.json
python -m nmrcp.cli validate-inventory --inventory examples/sample_inventory.json --strict
```

Default validation fails on malformed structure, duplicate workload IDs, or a
missing `workloads` list. It reports completeness gaps as warnings. `--strict`
also fails on warnings, which is useful for change-control gates.

`assess` validates inventory automatically. Use `--strict-inventory` to fail
assessment when completeness warnings are present.

## Offline RVTools Import

Use RVTools CSV exports when live vCenter credentials are not available yet:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli import-rvtools `
  --dir examples\rvtools `
  --source-name "rvtools-export-2026-07-24" `
  --out outputs\rvtools-inventory.json
python -m nmrcp.cli validate-inventory --inventory outputs\rvtools-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\rvtools-inventory.json
python -m nmrcp.cli assess --inventory outputs\rvtools-inventory.json --out outputs\rvtools-assessment
```

The importer reads `vInfo.csv` and, when present, enriches from
`vSnapshot.csv`, `vNetwork.csv`, and `vDisk.csv`. It maps common RVTools columns
into the normalized inventory contract. Snapshot timestamps in `vSnapshot.csv`
are converted into oldest-snapshot age for policy scoring when available;
otherwise snapshot count is preserved without age proof. The importer keeps
uncertain facts conservative:
VirtIO readiness, backup proof, owner, tier, and vendor support are only set
when encoded in VM annotations such as
`owner:apps;tier:critical;backup:protected;backup_last_success_hours:4;vendor_support:ahv,nc2;virtio_ready:true`.

## Move Plan Validation

`nutanix-move-plan.csv` uses the `nmrcp_move_plan_v1` staging contract. Validate
it before handing it to operators:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-move-plan --plan outputs\sample-assessment\nutanix-move-plan.csv
```

For assessment-packet review, bind the plan to the canonical assessment source:

```powershell
python -m nmrcp.cli validate-move-plan `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
python -m nmrcp.cli validate-move-plan-brief `
  --brief outputs\sample-assessment\move-plan-brief.md `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator fails closed if required columns are missing, a blocked workload is
included, include/hold state conflicts with precheck state, or risk/dependency
values are invalid. With `--assessment`, it also rejects missing, extra, or
stale source-bound workload fields.

Generate a dry-run Move API payload after validation:

```powershell
python -m nmrcp.cli generate-move-payload `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --config examples\sample_move_payload_config.json `
  --out outputs\sample-assessment\move-api-payload.dry-run.json
```

This payload is review-only. The MVP does not submit migration plans to Nutanix
Move.

Before any future lab-only Move API submitter is considered, run the fail-closed
submit readiness gate with reviewed lab identifiers and explicit acknowledgement:

```powershell
python -m nmrcp.cli generate-move-payload `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --config examples\sample_move_payload_lab_config.json `
  --out outputs\sample-assessment\move-api-payload.lab.dry-run.json
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-submit-readiness `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out outputs\sample-assessment\move-submit-readiness.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

Draft the Move lab proof before non-production API round-trip testing:

```powershell
python -m nmrcp.cli generate-move-lab-proof-template `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --proof-scope approved_lab_move_appliance `
  --out outputs\sample-assessment\move-lab-proof.template.json
```

See `docs/operations/move-lab-proof.md`.

Validate a redacted real lab Move API transcript before final proof sign-off,
then link its SHA-256 in the approved proof JSON as
`transcript_validation_sha256`. The generated capture checklist includes the
final `validate-move-lab-evidence-intake` command so the approved transcript,
proof validation, and capture-kit validation close into the handoff-required
`move-lab-evidence-intake.json` artifact:

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

python -m nmrcp.cli validate-move-lab-transcript `
  --transcript outputs\sample-assessment\move-lab-transcript.approved.json `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out outputs\sample-assessment\move-lab-transcript-validation.json
python -m nmrcp.cli generate-approved-move-lab-proof `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript outputs\sample-assessment\move-lab-transcript.approved.json `
  --transcript-validation outputs\sample-assessment\move-lab-transcript-validation.json `
  --approved-by "Lab Migration Lead" `
  --out outputs\sample-assessment\move-lab-proof.approved.json
python -m nmrcp.cli validate-move-lab-proof `
  --proof outputs\sample-assessment\move-lab-proof.approved.json `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript-validation outputs\sample-assessment\move-lab-transcript-validation.json `
  --out outputs\sample-assessment\move-lab-proof-validation.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

See `docs/operations/move-lab-transcript.md`.

See `docs/operations/move-submit-readiness.md`.

Generate and validate pre/post validation results from the Move staging plan:

```powershell
python -m nmrcp.cli generate-validation-template `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --out outputs\validation-results.template.csv
python -m nmrcp.cli validate-validation-results `
  --results outputs\validation-results.template.csv `
  --allow-open
```

Final validation results fail closed on unchecked or failed checks unless draft
review is explicitly allowed. See `docs/operations/validation-results.md`.

## Read-Only Collection

The collector commands write normalized inventory JSON that can be passed to
`assess`. Passwords are read from environment variables or secure prompts; do
not pass passwords as command-line arguments.

Run probes before collection. Probes authenticate and perform read-only list
calls, but do not write inventory files or print endpoint, username, or password
values.

vCenter:

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_VCENTER_PASSWORD = "<local secret>"
python -m nmrcp.cli probe-vcenter `
  --endpoint https://vcenter.example.com `
  --username administrator@example.com
python -m nmrcp.cli collect-vcenter `
  --endpoint https://vcenter.example.com `
  --username administrator@example.com `
  --out outputs/vcenter-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs/vcenter-inventory.json
python -m nmrcp.cli assess --inventory outputs/vcenter-inventory.json --out outputs/vcenter-assessment
```

Prism Central:

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_PRISM_PASSWORD = "<local secret>"
python -m nmrcp.cli probe-prism `
  --endpoint https://prism-central.example.com:9440 `
  --username admin
python -m nmrcp.cli collect-prism `
  --endpoint https://prism-central.example.com:9440 `
  --username admin `
  --out outputs/prism-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs/prism-inventory.json
python -m nmrcp.cli collect-prism-capacity `
  --endpoint https://prism-central.example.com:9440 `
  --username admin `
  --out outputs/prism-capacity.json
```

The current collectors use read-only inventory flows. vCenter creates an API
session and then performs GET calls. Prism Central v3 uses POST list APIs for
inventory retrieval, which is read-only but still requires careful endpoint
allow-listing.

`collect-prism-capacity` uses the same read-only Prism cluster list path to
draft a target capacity JSON for platform-owner review before capacity-fit
validation.

Collected inventories include `source.collection_audit` with schema
`nmrcp_collection_audit_v1`. This audit block records non-secret proof such as
collection mode, read-only API path names, configured limits, observed counts,
and `mutating_calls=0`. It intentionally omits endpoint URLs, usernames, and
passwords; the raw `source.endpoint` remains in normalized inventory for local
operator traceability and is redacted in generated evidence. See
`docs/operations/collection-audit.md`.

Run `validate-collection-audit` before assessment or evidence packaging to fail
closed when the audit block is missing, mutating, inconsistent with workload
counts, or leaking endpoint/credential material.

The change-board evidence and HTML operator report promote the same audit data
into a `Collection Audit Proof` section for reviewer sign-off.

Before collecting inventory, generate a redacted live-readiness proof from
environment-configured endpoints:

```powershell
python -m nmrcp.cli live-readiness `
  --require-vcenter `
  --require-prism `
  --out outputs\live-readiness.json
```

The proof records only endpoint status, read-only call names, and counts. It does
not serialize endpoint URLs, usernames, passwords, or inventory details. See
`docs/operations/live-readiness.md`.

After approved live collection, validate the combined endpoint proof packet:

```powershell
python -m nmrcp.cli validate-live-proof `
  --live-readiness outputs\source-collection\live-readiness.json `
  --collection-summary outputs\source-collection\collection-summary.json `
  --source-dir outputs\source-collection `
  --out outputs\source-collection\live-proof-validation.json
```

See `docs/operations/live-endpoint-proof.md`.

After access is approved, collect both source systems into local artifacts:

```powershell
python -m nmrcp.cli validate-assessment-intake --intake outputs\assessment-intake.csv
python -m nmrcp.cli source-collection-plan `
  --intake outputs\assessment-intake.csv `
  --out outputs\source-collection-plan.md
python -m nmrcp.cli validate-source-collection-plan `
  --plan outputs\source-collection-plan.md `
  --intake outputs\assessment-intake.csv
python -m nmrcp.cli collect-sources `
  --assessment-intake outputs\assessment-intake.csv `
  --out-dir outputs\source-collection
python -m nmrcp.cli validate-collection-audit --inventory outputs\source-collection\vcenter-inventory.json
python -m nmrcp.cli validate-collection-audit --inventory outputs\source-collection\prism-inventory.json
python -m nmrcp.cli assess `
  --inventory outputs\source-collection\vcenter-inventory.json `
  --capacity outputs\source-collection\prism-capacity.json `
  --out outputs\source-assessment
```

`collection-summary.json` records redacted source-collection proof without
endpoint URLs, usernames, passwords, or workload details. See
`docs/operations/source-collection-workflow.md`.
`source-collection-plan.md` is a pre-collection operator brief that keeps
endpoint values and credentials out of the plan while listing the proof files
required for external closeout. See `docs/operations/source-collection-plan.md`.
`collection-proof-manifest.json` records the source artifact checksums and
read-only API allowlist so live proof validation can catch tampering or
out-of-scope collection paths. For external live proof closeout,
`validate-live-proof` also requires the assessment-intake checksum in the
collection summary and proof manifest to match.
`collect-sources` also writes `vcenter-networks.json` as explicit read-only
vCenter network inventory proof for source network review.

Use collected Prism inventory for target reconciliation before Move planning:

```powershell
python -m nmrcp.cli run-assessment `
  --inventory outputs\source-collection\vcenter-inventory.json `
  --capacity outputs\source-collection\prism-capacity.json `
  --prism-inventory outputs\source-collection\prism-inventory.json `
  --source-networks outputs\source-collection\vcenter-networks.json `
  --out outputs\source-assessment
```

See `docs/operations/target-reconciliation.md`.

## Test And Smoke

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
python scripts/security_scan.py
python scripts/live_collector_smoke.py
python -m nmrcp.cli assess --inventory examples/sample_inventory.json --out outputs/sample-assessment
```

`scripts/live_collector_smoke.py` starts local loopback vCenter and Prism
Central simulators, runs the real read-only collector CLI commands against
them, validates the generated inventories, assesses the simulated vCenter
inventory, and runs evidence redaction review.

## Local Preflight

Run `doctor` before configuring live collectors:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli doctor
python -m nmrcp.cli doctor --json
```

The doctor command verifies Python version, sample files, the sample assessment
pipeline, inventory validation, Move-plan validation, dry-run payload
generation, sample redaction, installable `nmrcp` CLI metadata, and generated
artifact ignore rules.
It reports whether vCenter and Prism Central environment variables are present
without printing their values. Missing endpoint variables are warnings, not
failures, because the local sample workflow does not require live credentials.

## Operations Console

Every assessment writes `operations-console.html`, a dependency-free local UI
for migration operators. It is shaped like a migration tool front door: connect
source and target environments, review compatibility analysis, filter workload
readiness, and prepare the Move plan while keeping endpoint-proof and Move lab
proof boundaries visible. See `docs/operations/operations-console.md`.

## Operator Report

Every assessment writes `operator-portal.html`, a dependency-free local landing
page for the generated evidence set. It gives operators one place to open the
dashboard, report, runbook, Move plan, validation checklist, closure checklist,
what-will-break brief, external proof plan, and manifest while keeping the
approved Move lab proof stop condition and external handoff boundary visible.
See `docs/operations/operator-portal.md`.

Every assessment writes `operator-report.html`, a dependency-free static report
with the executive summary, migration waves, workload readiness, findings, and
redacted source metadata. Open it locally in a browser or attach it to a change
request after human review.

## Operator Dashboard

Every assessment also writes `operator-dashboard.html`, a dependency-free local
work queue for migration operators. It embeds only the generated assessment
facts, supports filtering by readiness, owner, wave, and free-text finding
search, and keeps the stop conditions visible for the selected workload.

`run-assessment` also writes `operator-gate-summary.md` after optional evidence
gates are evaluated. For standalone assessment runs, use `summarize-gates` after
generating optional artifacts. See `docs/operations/operator-gate-summary.md`.

## Move Lab Closure Checklist

Every assessment writes `move-lab-closure-checklist.md`, a local operator
checklist for closing the approved Nutanix Move lab proof gap before external
handoff. It lists the required submit-readiness, capture-kit, transcript,
approved-proof, evidence-intake, and final gate rerun chain. `change-gate`
validates the checklist contract so the final proof steps stay visible even
when approved Move appliance evidence has not yet been supplied.

## Evidence Manifest

Every assessment writes `evidence-manifest.json` with schema
`nmrcp_evidence_manifest_v1`. It records artifact names, sizes, SHA-256 hashes,
and generation time for the core evidence bundle so operators can verify files
after handoff.

The manifest covers assessment artifacts generated together. Dry-run Move API
payloads are generated after assessment and should be reviewed separately.
`target-readiness-comparison.csv` is included so architecture teams can compare
AHV and NC2 outcomes while the selected target-specific plan remains clear.
`validate-target-comparison` binds the redacted comparison context to canonical
assessment workload identity and owner before handoff.
`remediation-tracker.csv` is included so owners can close findings before
workloads move out of hold states. Use `validate-remediation` to review draft
or final closure rows.
`owner-risk-summary.csv` is included so migration leads can review owner-level
risk before change-board handoff; its validator rejects unknown or duplicate
workload membership in assessment waves before owner accountability is trusted.

`move-lab-closure-checklist.md` is included so operators and change reviewers
can see the exact approved Move lab proof chain that remains before final
handoff readiness.

`operator-portal.html` is included so reviewers can start from one local
landing page and open the dashboard, report, runbook, Move plan, validation
checklist, Move lab closure checklist, what-will-break brief, optional external
proof plan, and evidence manifest without hunting through the assessment
directory.
`validate-operator-portal` checks it against `assessment.json`, including the
external proof plan and Move proof contract visibility, and `change-gate` runs
that validation automatically.

`business-impact-summary.csv` is included so executives and change boards can
see critical versus noncritical migration posture without reading every
workload finding. `validate-business-impact` binds the redacted business tier
context to canonical assessment workload identity, owner, and wave membership;
`change-gate` runs that validation automatically.

`executive-readiness-brief.md` is included so sponsors and change boards get a
plain-language decision ask, business-impact view, wave posture, top blockers,
and required evidence before migration approval. `validate-executive-brief`
checks it against `assessment.json`, and `change-gate` runs that validation
automatically.

`wave-readiness-summary.csv` is included so change boards and migration factory
leads can see which waves are ready, conditional, or held before opening
Nutanix Move staging work. `validate-wave-summary` checks it against
`assessment.json`, and `change-gate` runs that validation automatically.

`wave-execution-calendar.csv` is included so partners, MSPs, and migration leads
can turn readiness waves into review windows with entry gates, exit gates,
operator actions, and evidence references. It is planning evidence only and does
not schedule migrations. `validate-wave-execution-calendar` checks it against
`assessment.json`, recomputes the expected rows from workload assessments and
waves, and rejects CSV or embedded-context drift. It also fails closed when
assessment waves reference unknown workload IDs or place the same workload in
multiple waves. `change-gate` runs that validation automatically.

`dependency-review.csv` is included so migration teams can review internal
dependencies, external services, unmatched dependency imports, owners,
criticality, and staging impact before Move activity.
`validate-dependency-review` checks it against `assessment.json`, and
`change-gate` runs that validation automatically.

`connectivity-checklist.csv` is included so migration teams can turn dependency
records into firewall, DNS, routing, and application reachability validation
work before cutover. `validate-connectivity-checklist` checks it against
`assessment.json`, and `change-gate` runs that validation automatically.

`identity-cutover-plan.csv` is included so operators can validate hostname,
DNS, IPAM, and source-network identity facts before and after cutover. Raw IPs
are redacted in evidence while status still reflects whether usable source
identity was captured. `validate-identity-cutover-plan` checks it against
`assessment.json`, and `change-gate` runs that validation automatically.

`compatibility-research.csv` is included so operators can review guest OS and
vendor target-support evidence before AHV or NC2 staging. It separates known
good rows from research and blocked rows, and `validate-compatibility-research`
checks it against `assessment.json`; `change-gate` runs that validation
automatically.

`owner-signoff-matrix.csv` is included so application owners and migration leads
can track required approvals before Move staging or remediation closure.

`approval-exceptions.csv` is included so change boards can see every workload
or finding that requires explicit risk acceptance or exception approval.
`validate-approval-exceptions` checks it against `assessment.json`, and
`change-gate` runs that validation automatically.
Filled final exception registers can be validated with
`validate-approval-exception-approvals --assessment` and passed to
`change-gate`, `summarize-gates`, `package-handoff`, or `run-assessment` with
`--approval-exceptions`.

`partner-handoff-matrix.csv` maps the evidence set to migration lead,
application owner, platform owner, network owner, backup/rollback owner, risk
and change board, and Move operator responsibilities. It is local review
evidence only and does not create tasks or send messages. Validate it with
`validate-partner-handoff`; `change-gate` runs that validation automatically.
The validator recomputes role rows from `assessment.json` workload assessments
and waves, then rejects CSV or embedded-context drift. It also fails closed when
assessment waves reference unknown workload IDs or place the same workload in
multiple waves, so partner handoff ownership cannot be based on invented or
duplicated wave membership.

`recovery-readiness.csv` is included so application, backup, and migration
owners can confirm backup proof, snapshot cleanup, and rollback ownership before
Move staging. `validate-recovery-readiness` checks it against
`assessment.json`, binds recovery context to canonical workload identity and
findings-derived recovery status/action, and `change-gate` runs that validation
automatically.

`rollback-plan.csv` is included so change boards can review rollback owner,
trigger criteria, backup/snapshot evidence, and whether a workload is ready,
held, blocked, or requires rollback review. `validate-rollback-plan` checks it
against `assessment.json`, binds rollback context to canonical workload identity
and findings-derived recovery posture, and `change-gate` runs that validation
automatically.

`move-staging-readiness.csv` is included so migration leads have one
machine-verifiable queue for `ready`, `conditional`, and `hold` staging
decisions. `validate-move-staging-readiness` checks it against
`assessment.json`, and `change-gate` runs that validation automatically.

`migration-execution-queue.csv` is included so operators can see workload
execution order and the current go/review/hold reason without cross-opening
every supporting artifact. `validate-migration-execution-queue` checks it
against `assessment.json`, binds embedded queue context to canonical workload
identity and wave membership, and `change-gate` runs that validation
automatically.

`workload-validation-checklist.csv` is included so operators have per-workload
pre-migration, cutover, and post-migration validation rows with required
evidence and stop conditions. `validate-workload-validation-checklist` checks it
against `assessment.json`, and `change-gate` runs that validation automatically.

`prism-category-mapping.csv` is included so platform owners can review proposed
Prism/NCM categories such as owner, tier, readiness, wave intent, and source
tags before target-side governance work. It is review-only and does not apply
categories. `validate-prism-categories` checks it against `assessment.json`,
binds category context to canonical workload identity and readiness, and
`change-gate` runs that validation automatically.

`stakeholder-communication-plan.csv` is included so migration leads, partners,
and MSP operators can plan owner outreach by wave without sending messages from
NMRCP. It is local review evidence only. `validate-stakeholder-comms` checks it
against canonical `assessment.json` workload assessments and waves, rejects
embedded-context drift or invalid wave membership, and `change-gate` runs that
validation automatically.

`what-will-break-report.csv` is included so app owners and change reviewers can
see each workload's likely migration breakage scenario, impact, required action,
and supporting local evidence. `validate-what-will-break` rebuilds it from
canonical `assessment.json` workload assessments, waves, and inventory coverage
context; `change-gate` runs that validation automatically.
`what-will-break-brief.md` is included for the first-pass reviewer readout and
is validated from the same canonical rows with `validate-what-will-break-brief`.

Package and verify the evidence bundle:

```powershell
python -m nmrcp.cli verify-evidence --dir outputs\sample-assessment
python -m nmrcp.cli review-evidence --dir outputs\sample-assessment
python -m nmrcp.cli package-evidence `
  --dir outputs\sample-assessment `
  --out outputs\sample-evidence-bundle.zip
python -m nmrcp.cli verify-evidence --bundle outputs\sample-evidence-bundle.zip
```

`review-evidence` scans generated evidence for unredacted URLs, emails, IPs,
common internal hostnames, and secret-like assignments. See
`docs/operations/evidence-redaction-review.md`.

Run the local change gate before handoff:

```powershell
python -m nmrcp.cli change-gate `
  --dir outputs\sample-assessment `
  --bundle outputs\sample-evidence-bundle.zip
```

For post-migration closure, add final validation results with
`--validation-results`, a final remediation tracker with
`--remediation-tracker`, final owner approvals with `--signoffs`, final
exception approvals with `--approval-exceptions`, and Move lab capture
preflight proof with `--move-lab-capture-validation` when preparing an approved
lab evidence window. When approved Move proof is supplied with
`--move-lab-proof`, also supply `--move-lab-evidence-intake`. See
`docs/operations/change-gate.md`.

When a reviewer accepts remaining warning-level gate findings, validate the
filled register with `validate-warning-acceptance` and pass it to
`mvp-audit --warning-acceptance`. See
`docs/operations/change-gate-warning-acceptance.md`.

Create and verify a final handoff package when the receiver needs the assessment
artifacts, evidence bundle, validation results, owner sign-offs, and reviewed
dry-run Move payload in one archive. Add the Move lab capture kit and validation
proof when the receiver also needs preflight evidence for the approved lab
capture window:

```powershell
python -m nmrcp.cli package-handoff `
  --dir outputs\sample-assessment `
  --bundle outputs\sample-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --move-lab-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json `
  --move-lab-capture-kit outputs\move-lab-capture-kit `
  --move-lab-capture-validation outputs\move-lab-capture-kit-validation.json `
  --move-lab-readiness-packet outputs\move-lab-readiness-packet.json `
  --source-collection-plan outputs\source-collection-plan.md `
  --move-payload outputs\sample-assessment\move-api-payload.dry-run.json `
  --out outputs\sample-handoff-package.zip
python -m nmrcp.cli verify-handoff --package outputs\sample-handoff-package.zip
```

See `docs/operations/handoff-package.md`.

## Security Posture

- No credentials are written to output artifacts.
- Evidence exports redact IP addresses, emails, hostnames, URLs, and likely
  secret values.
- The HTML operator report is generated from redacted source metadata.
- The migration runbook is generated evidence for human review; it does not
  execute or submit migration actions.
- Validation results fail closed on unchecked or failed rows unless draft review
  is explicitly requested.
- Evidence manifests provide local SHA-256 integrity checks for assessment
  artifacts.
- Handoff packages provide SHA-256 integrity checks for the archived assessment,
  bundle, validation, remediation closure, sign-off, and dry-run Move payload
  files without storing local source paths. Verification also checks manifest
  roles, required assessment artifacts, nested bundle readability, and
  dry-run-only Move payload semantics.
- Evidence bundles can be packaged and verified without external tools.
- Change gates verify assessment artifacts, Move plans, evidence integrity, and
  optional validation, remediation closure, and sign-off artifacts before
  approval handoff.
- Warning acceptance registers require exact change-gate warning text plus
  approver, timestamp, and reference evidence; they do not retire external Move
  proof gaps.
- RVTools CSV imports run offline, but raw RVTools exports should still be
  treated as sensitive infrastructure inventory.
- Connector helpers default to TLS verification.
- Collector commands use environment variables or secure prompts for passwords.
- `doctor` reports credential variable presence without printing values.
- Probe commands perform read-only reachability checks without writing inventory
  files or printing connection values.
- Live collectors should use environment variables or an external secret store;
  do not commit credentials, tokens, support bundles, or customer exports.
- Metadata and dependency exports can reveal business ownership and criticality;
  keep them inside the approved migration workspace.

## Repository Layout

```text
src/nmrcp/       Local-first readiness engine, importers, and connector helpers.
tests/           Unit tests for scoring, wave planning, redaction, and CLI.
examples/        Sanitized sample inventory.
docs/            Architecture, security, and operating guides.
scripts/         Smoke-test helper.
```

GitHub review and publication expectations are documented in
`docs/operations/github-readiness.md`. Run
`python -m nmrcp.cli github-readiness --repo-root . --out outputs\github-publication-review.md --json-out outputs\github-publication-review.json`
before publishing; it checks required files, the expected GitHub remote,
tracked publication paths, generated artifacts that must not be committed, and
writes a sanitized local publication review for the branch owner. Validate that
review with
`python -m nmrcp.cli validate-github-publication-review --repo-root . --report outputs\github-publication-review.md --json-report outputs\github-publication-review.json`
before using it for pull-request or release review.
Vault documentation coverage is validated with
`python -m nmrcp.cli vault-readiness --repo-root .`; see
`docs/operations/vault-readiness.md`.
Use `python -m nmrcp.cli product-readiness --repo-root .` for the aggregate
completion gate across MVP evidence, GitHub publication, and vault coverage.
For durable aggregate evidence, include
`--mvp-proof-package outputs\smoke-mvp-proof-package.zip --publication-staging-manifest outputs\publication-staging-manifest.md --publication-staging-manifest-json outputs\publication-staging-manifest.json --out outputs\product-readiness-report.md --json-out outputs\product-readiness-report.json`,
then run
`python -m nmrcp.cli validate-product-readiness-report --repo-root . --mvp-proof-package outputs\smoke-mvp-proof-package.zip --publication-staging-manifest outputs\publication-staging-manifest.md --publication-staging-manifest-json outputs\publication-staging-manifest.json --report outputs\product-readiness-report.md --json-report outputs\product-readiness-report.json`
with the same vault, remote, and evidence flags used for generation. The
validator rejects stale JSON or Markdown that no longer reflects the current
aggregate gates.
Use
`python -m nmrcp.cli publication-handoff --repo-root . --github-publication-review outputs\github-publication-review.md --github-publication-review-json outputs\github-publication-review.json --product-readiness-report outputs\product-readiness-report.md --product-readiness-report-json outputs\product-readiness-report.json --smoke-log outputs\smoke-product-readiness-report-validation.log --security-scan-status pass --out outputs\publication-handoff.md --json-out outputs\publication-handoff.json`
to create a local branch-owner handoff record from validated readiness artifacts
without staging, committing, pushing, or claiming external handoff readiness.
Use
`python -m nmrcp.cli publication-staging-manifest --repo-root . --out outputs\publication-staging-manifest.md --json-out outputs\publication-staging-manifest.json`
to produce a hash-backed staging manifest before any operator-approved
`git add -- ...` action.
Use
`python -m nmrcp.cli pull-request-readiness --repo-root . --github-publication-review outputs\github-publication-review.md --github-publication-review-json outputs\github-publication-review.json --product-readiness-report outputs\product-readiness-report.md --product-readiness-report-json outputs\product-readiness-report.json --publication-handoff outputs\publication-handoff.md --publication-handoff-json outputs\publication-handoff.json --publication-staging-manifest outputs\publication-staging-manifest.md --publication-staging-manifest-json outputs\publication-staging-manifest.json --smoke-log outputs\smoke-pull-request-readiness.log --security-scan-status pass --out outputs\pull-request-readiness.md --json-out outputs\pull-request-readiness.json`
to create the local branch-owner PR packet before staging or opening a pull
request.
Use
`python -m nmrcp.cli external-proof-plan --repo-root . --out outputs\external-proof-plan.md --json-out outputs\external-proof-plan.json`
to create the approved endpoint and Nutanix Move proof closeout plan. Validate
it with
`python -m nmrcp.cli validate-external-proof-plan --repo-root . --report outputs\external-proof-plan.md --json-report outputs\external-proof-plan.json`.

## Product Direction

The control plane should become the assessment and evidence system around
Nutanix Move, Prism Central, NCM, and partner migration workflows. The next
major slices are real lab testing against a non-production Move appliance,
CMDB/dependency source adapters, and a small operator UI.
