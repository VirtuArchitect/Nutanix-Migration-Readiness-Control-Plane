$ErrorActionPreference = "Stop"

$script:PythonExe = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
$script:PowerShellExe = (Get-Command powershell.exe -CommandType Application | Select-Object -First 1).Source

function Invoke-CheckedNative {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [object[]]$Arguments = @()
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code $LASTEXITCODE`: $Executable $($Arguments -join ' ')"
    }
}

function python {
    param([Parameter(ValueFromRemainingArguments=$true)][object[]]$Arguments)

    Invoke-CheckedNative -Executable $script:PythonExe -Arguments $Arguments
}

function powershell {
    param([Parameter(ValueFromRemainingArguments=$true)][object[]]$Arguments)

    Invoke-CheckedNative -Executable $script:PowerShellExe -Arguments $Arguments
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $repoRoot "src"
$outDir = Join-Path $repoRoot "outputs\smoke"
$workflowOutDir = Join-Path $repoRoot "outputs\smoke-workflow"
$cmdbMetadata = Join-Path $repoRoot "outputs\smoke-cmdb-metadata.csv"
$metadataInventory = Join-Path $repoRoot "outputs\smoke-metadata-inventory.json"
$enrichedInventory = Join-Path $repoRoot "outputs\smoke-enriched-inventory.json"
$rvtoolsInventory = Join-Path $repoRoot "outputs\smoke-rvtools-inventory.json"
$rvtoolsOutDir = Join-Path $repoRoot "outputs\smoke-rvtools"
$appMapDependencies = Join-Path $repoRoot "outputs\smoke-app-map-dependencies.csv"
$appMapInventory = Join-Path $repoRoot "outputs\smoke-app-map-inventory.json"
$appMapOutDir = Join-Path $repoRoot "outputs\smoke-app-map"
$assessmentIntakeTemplate = Join-Path $repoRoot "outputs\smoke-assessment-intake.template.csv"
$sourceCollectionPlan = Join-Path $repoRoot "outputs\smoke-source-collection-plan.md"
$validationTemplate = Join-Path $repoRoot "outputs\smoke-validation-results.template.csv"
$operatorReviewTemplate = Join-Path $repoRoot "outputs\smoke-operator-review.template.csv"
$workflowOperatorReview = Join-Path $repoRoot "outputs\smoke-workflow-operator-review.csv"
$approvalExceptionsApproved = Join-Path $repoRoot "examples\sample_approval_exceptions_approved.csv"
$warningAcceptance = Join-Path $repoRoot "examples\sample_change_gate_warning_acceptance.csv"
$labMovePayload = Join-Path $repoRoot "outputs\smoke\move-api-payload.lab.dry-run.json"
$moveLabRunbook = Join-Path $repoRoot "outputs\smoke\move-lab-execution-runbook.md"
$moveLabCaptureKitDir = Join-Path $repoRoot "outputs\smoke\move-lab-capture-kit"
$moveLabCaptureKitValidation = Join-Path $repoRoot "outputs\smoke\move-lab-capture-kit-validation.json"
$moveSubmitReadiness = Join-Path $repoRoot "outputs\smoke\move-submit-readiness.json"
$moveLabEvidencePreflight = Join-Path $repoRoot "outputs\smoke\move-lab-evidence-preflight.json"
$moveLabEvidencePreflightReport = Join-Path $repoRoot "outputs\smoke\move-lab-evidence-preflight.md"
$moveLabReadinessPacket = Join-Path $repoRoot "outputs\smoke\move-lab-readiness-packet.json"
$moveLabReadinessPacketReport = Join-Path $repoRoot "outputs\smoke\move-lab-readiness-packet.md"
$moveLabTranscript = Join-Path $repoRoot "outputs\smoke\move-lab-transcript.approved.example.json"
$moveLabTranscriptValidation = Join-Path $repoRoot "outputs\smoke\move-lab-transcript-validation.json"
$moveLabProofValidation = Join-Path $repoRoot "outputs\smoke\move-lab-proof-validation.simulated.json"
$generatedProofPayload = Join-Path $repoRoot "outputs\smoke\move-api-payload.generated-proof-rehearsal.json"
$generatedProofTranscript = Join-Path $repoRoot "outputs\smoke\move-lab-transcript.generated-proof-rehearsal.json"
$generatedProofTranscriptValidation = Join-Path $repoRoot "outputs\smoke\move-lab-transcript-validation.generated-proof-rehearsal.json"
$generatedApprovedProof = Join-Path $repoRoot "outputs\smoke\move-lab-proof.generated-approved.json"
$generatedApprovedProofValidation = Join-Path $repoRoot "outputs\smoke\move-lab-proof-validation.generated-approved.json"
$generatedProofEvidenceIntake = Join-Path $repoRoot "outputs\smoke\move-lab-evidence-intake.generated-proof-rehearsal.json"
$generatedProofMvpAudit = Join-Path $repoRoot "outputs\smoke-mvp-audit-generated-proof-rehearsal.json"
$generatedProofPackage = Join-Path $repoRoot "outputs\smoke-generated-proof-rehearsal-package.zip"
$generatedExternalProofPlan = Join-Path $repoRoot "outputs\external-proof-plan.generated-proof-rehearsal.md"
$generatedExternalProofPlanJson = Join-Path $repoRoot "outputs\external-proof-plan.generated-proof-rehearsal.json"
$bundlePath = Join-Path $repoRoot "outputs\smoke-evidence-bundle.zip"
$handoffPath = Join-Path $repoRoot "outputs\smoke-handoff-package.zip"
$finalChangeGateJson = Join-Path $repoRoot "outputs\smoke-change-gate-final.json"
$liveReadinessPath = Join-Path $repoRoot "outputs\smoke-live-readiness.json"
$liveProofPath = Join-Path $repoRoot "outputs\smoke-live-proof-validation.json"
$externalProofPlan = Join-Path $repoRoot "outputs\external-proof-plan.md"
$externalProofPlanJson = Join-Path $repoRoot "outputs\external-proof-plan.json"
$mvpAuditPath = Join-Path $repoRoot "outputs\smoke-mvp-audit.json"
$mvpProofPackage = Join-Path $repoRoot "outputs\smoke-mvp-proof-package.zip"
$mvpProofSummary = Join-Path $repoRoot "outputs\smoke-mvp-proof-summary.md"
$mvpClosureReport = Join-Path $repoRoot "outputs\smoke-mvp-closure-report.md"
$mvpClosureReportJson = Join-Path $repoRoot "outputs\smoke-mvp-closure-report.json"
$launchReadinessReport = Join-Path $repoRoot "outputs\smoke-launch-readiness-report.md"
$launchReadinessReportJson = Join-Path $repoRoot "outputs\smoke-launch-readiness-report.json"
$publicationStagingManifest = Join-Path $repoRoot "outputs\smoke-publication-staging-manifest.md"
$publicationStagingManifestJson = Join-Path $repoRoot "outputs\smoke-publication-staging-manifest.json"
$productReadinessReport = Join-Path $repoRoot "outputs\smoke-product-readiness-report.md"
$productReadinessReportJson = Join-Path $repoRoot "outputs\smoke-product-readiness-report.json"
$workflowMvpProofPackage = Join-Path $repoRoot "outputs\smoke-move-lab-workflow-proof-package.zip"
$workflowLaunchReadinessReport = Join-Path $repoRoot "outputs\smoke-move-lab-workflow-launch-readiness-report.md"
$workflowLaunchReadinessReportJson = Join-Path $repoRoot "outputs\smoke-move-lab-workflow-launch-readiness-report.json"
$generatedProofLaunchReadinessReport = Join-Path $repoRoot "outputs\smoke-generated-proof-rehearsal-launch-readiness-report.md"
$generatedProofLaunchReadinessReportJson = Join-Path $repoRoot "outputs\smoke-generated-proof-rehearsal-launch-readiness-report.json"
$liveCollectorSmokeDir = Join-Path $repoRoot "outputs\live-collector-smoke"

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
if (Test-Path -LiteralPath $workflowOutDir) {
    Remove-Item -LiteralPath $workflowOutDir -Recurse -Force
}
if (Test-Path -LiteralPath $cmdbMetadata) {
    Remove-Item -LiteralPath $cmdbMetadata -Force
}
if (Test-Path -LiteralPath $enrichedInventory) {
    Remove-Item -LiteralPath $enrichedInventory -Force
}
if (Test-Path -LiteralPath $metadataInventory) {
    Remove-Item -LiteralPath $metadataInventory -Force
}
if (Test-Path -LiteralPath $rvtoolsInventory) {
    Remove-Item -LiteralPath $rvtoolsInventory -Force
}
if (Test-Path -LiteralPath $rvtoolsOutDir) {
    Remove-Item -LiteralPath $rvtoolsOutDir -Recurse -Force
}
if (Test-Path -LiteralPath $appMapDependencies) {
    Remove-Item -LiteralPath $appMapDependencies -Force
}
if (Test-Path -LiteralPath $appMapInventory) {
    Remove-Item -LiteralPath $appMapInventory -Force
}
if (Test-Path -LiteralPath $appMapOutDir) {
    Remove-Item -LiteralPath $appMapOutDir -Recurse -Force
}
if (Test-Path -LiteralPath $assessmentIntakeTemplate) {
    Remove-Item -LiteralPath $assessmentIntakeTemplate -Force
}
if (Test-Path -LiteralPath $validationTemplate) {
    Remove-Item -LiteralPath $validationTemplate -Force
}
if (Test-Path -LiteralPath $operatorReviewTemplate) {
    Remove-Item -LiteralPath $operatorReviewTemplate -Force
}
if (Test-Path -LiteralPath $workflowOperatorReview) {
    Remove-Item -LiteralPath $workflowOperatorReview -Force
}
if (Test-Path -LiteralPath $bundlePath) {
    Remove-Item -LiteralPath $bundlePath -Force
}
if (Test-Path -LiteralPath $handoffPath) {
    Remove-Item -LiteralPath $handoffPath -Force
}
if (Test-Path -LiteralPath $finalChangeGateJson) {
    Remove-Item -LiteralPath $finalChangeGateJson -Force
}
if (Test-Path -LiteralPath $liveReadinessPath) {
    Remove-Item -LiteralPath $liveReadinessPath -Force
}
if (Test-Path -LiteralPath $liveProofPath) {
    Remove-Item -LiteralPath $liveProofPath -Force
}
if (Test-Path -LiteralPath $mvpAuditPath) {
    Remove-Item -LiteralPath $mvpAuditPath -Force
}
if (Test-Path -LiteralPath $mvpProofPackage) {
    Remove-Item -LiteralPath $mvpProofPackage -Force
}
if (Test-Path -LiteralPath $mvpProofSummary) {
    Remove-Item -LiteralPath $mvpProofSummary -Force
}
if (Test-Path -LiteralPath $mvpClosureReport) {
    Remove-Item -LiteralPath $mvpClosureReport -Force
}
if (Test-Path -LiteralPath $mvpClosureReportJson) {
    Remove-Item -LiteralPath $mvpClosureReportJson -Force
}
if (Test-Path -LiteralPath $launchReadinessReport) {
    Remove-Item -LiteralPath $launchReadinessReport -Force
}
if (Test-Path -LiteralPath $launchReadinessReportJson) {
    Remove-Item -LiteralPath $launchReadinessReportJson -Force
}
if (Test-Path -LiteralPath $publicationStagingManifest) {
    Remove-Item -LiteralPath $publicationStagingManifest -Force
}
if (Test-Path -LiteralPath $publicationStagingManifestJson) {
    Remove-Item -LiteralPath $publicationStagingManifestJson -Force
}
if (Test-Path -LiteralPath $productReadinessReport) {
    Remove-Item -LiteralPath $productReadinessReport -Force
}
if (Test-Path -LiteralPath $productReadinessReportJson) {
    Remove-Item -LiteralPath $productReadinessReportJson -Force
}
if (Test-Path -LiteralPath $workflowMvpProofPackage) {
    Remove-Item -LiteralPath $workflowMvpProofPackage -Force
}
if (Test-Path -LiteralPath $moveLabProofValidation) {
    Remove-Item -LiteralPath $moveLabProofValidation -Force
}
if (Test-Path -LiteralPath $moveLabReadinessPacket) {
    Remove-Item -LiteralPath $moveLabReadinessPacket -Force
}
if (Test-Path -LiteralPath $moveLabReadinessPacketReport) {
    Remove-Item -LiteralPath $moveLabReadinessPacketReport -Force
}
if (Test-Path -LiteralPath $liveCollectorSmokeDir) {
    Remove-Item -LiteralPath $liveCollectorSmokeDir -Recurse -Force
}

python (Join-Path $repoRoot "scripts\live_collector_smoke.py")
python -m nmrcp.cli generate-assessment-intake --out $assessmentIntakeTemplate
python -m nmrcp.cli validate-assessment-intake --intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv")
python -m nmrcp.cli source-collection-plan --intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") --out $sourceCollectionPlan
python -m nmrcp.cli validate-source-collection-plan --plan $sourceCollectionPlan --intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv")
python -m nmrcp.cli validate-collection-audit --inventory (Join-Path $liveCollectorSmokeDir "vcenter-inventory.json")
python -m nmrcp.cli validate-collection-audit --inventory (Join-Path $liveCollectorSmokeDir "prism-inventory.json")
python -m nmrcp.cli validate-collection-proof-report --report (Join-Path $liveCollectorSmokeDir "collection-proof-report.md") --collection-summary (Join-Path $liveCollectorSmokeDir "collection-summary.json")
python -m nmrcp.cli live-readiness --out $liveReadinessPath
python -m nmrcp.cli validate-live-proof --live-readiness (Join-Path $liveCollectorSmokeDir "live-readiness.json") --collection-summary (Join-Path $liveCollectorSmokeDir "collection-summary.json") --source-dir $liveCollectorSmokeDir --out $liveProofPath
python -m nmrcp.cli import-rvtools --dir (Join-Path $repoRoot "examples\rvtools") --source-name "synthetic-rvtools" --out $rvtoolsInventory
python -m nmrcp.cli validate-inventory --inventory $rvtoolsInventory
python -m nmrcp.cli validate-collection-audit --inventory $rvtoolsInventory
python -m nmrcp.cli assess --inventory $rvtoolsInventory --policy (Join-Path $repoRoot "examples\sample_readiness_policy.json") --out $rvtoolsOutDir
python -m nmrcp.cli import-cmdb-metadata --export (Join-Path $repoRoot "examples\sample_cmdb_export.csv") --out $cmdbMetadata
python -m nmrcp.cli enrich-metadata --inventory (Join-Path $repoRoot "examples\sample_inventory.json") --metadata $cmdbMetadata --out $metadataInventory
python -m nmrcp.cli import-app-map --map (Join-Path $repoRoot "examples\sample_app_map.json") --out $appMapDependencies
python -m nmrcp.cli enrich-dependencies --inventory $metadataInventory --dependencies $appMapDependencies --out $appMapInventory
python -m nmrcp.cli validate-inventory --inventory $appMapInventory
python -m nmrcp.cli assess --inventory $appMapInventory --out $appMapOutDir
python -m nmrcp.cli enrich-dependencies --inventory $metadataInventory --dependencies (Join-Path $repoRoot "examples\sample_dependencies.csv") --out $enrichedInventory
python -m nmrcp.cli validate-inventory --inventory $enrichedInventory
python -m nmrcp.cli validate-collection-audit --inventory $enrichedInventory
python -m nmrcp.cli assess --inventory $enrichedInventory --capacity (Join-Path $repoRoot "examples\sample_target_capacity.json") --out $outDir
python -m nmrcp.cli validate-wave-execution-calendar --calendar (Join-Path $outDir "wave-execution-calendar.csv") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-partner-handoff --matrix (Join-Path $outDir "partner-handoff-matrix.csv") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-move-lab-evidence-request --request (Join-Path $outDir "move-lab-evidence-request.md")
python -m nmrcp.cli validate-source-endpoint-evidence-request --request (Join-Path $outDir "source-endpoint-evidence-request.md")
python -m nmrcp.cli validate-operator-portal --portal (Join-Path $outDir "operator-portal.html") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-prism-categories --mapping (Join-Path $outDir "prism-category-mapping.csv") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-stakeholder-comms --plan (Join-Path $outDir "stakeholder-communication-plan.csv") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-what-will-break --report (Join-Path $outDir "what-will-break-report.csv") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-move-plan --plan (Join-Path $outDir "nutanix-move-plan.csv")
python -m nmrcp.cli validate-move-plan-brief --brief (Join-Path $outDir "move-plan-brief.md") --plan (Join-Path $outDir "nutanix-move-plan.csv") --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli validate-capacity --inventory $enrichedInventory --plan (Join-Path $outDir "nutanix-move-plan.csv") --capacity (Join-Path $repoRoot "examples\sample_target_capacity.json") --out (Join-Path $outDir "target-capacity-fit.csv")
python -m nmrcp.cli reconcile-target --inventory $enrichedInventory --target-inventory (Join-Path $repoRoot "examples\sample_prism_inventory.json") --plan (Join-Path $outDir "nutanix-move-plan.csv") --out (Join-Path $outDir "target-reconciliation.csv")
python -m nmrcp.cli validate-target-reconciliation --reconciliation (Join-Path $outDir "target-reconciliation.csv")
python -m nmrcp.cli validate-source-networks --plan (Join-Path $outDir "nutanix-move-plan.csv") --networks (Join-Path $repoRoot "outputs\live-collector-smoke\vcenter-networks.json") --out (Join-Path $outDir "source-network-validation.csv")
python -m nmrcp.cli validate-source-network-results --results (Join-Path $outDir "source-network-validation.csv")
python -m nmrcp.cli validate-network-mappings --plan (Join-Path $outDir "nutanix-move-plan.csv") --config (Join-Path $repoRoot "examples\sample_move_payload_config.json") --out (Join-Path $outDir "target-network-mapping.csv")
python -m nmrcp.cli generate-validation-template --plan (Join-Path $outDir "nutanix-move-plan.csv") --out $validationTemplate
python -m nmrcp.cli validate-validation-results --results $validationTemplate --allow-open
python -m nmrcp.cli validate-validation-results --results (Join-Path $repoRoot "examples\sample_validation_results.csv")
python -m nmrcp.cli generate-operator-review --dir $outDir --out $operatorReviewTemplate
python -m nmrcp.cli validate-operator-review --review $operatorReviewTemplate --allow-draft
python -m nmrcp.cli validate-operator-review --review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv")
python -m nmrcp.cli validate-remediation --tracker (Join-Path $outDir "remediation-tracker.csv") --allow-open
python -m nmrcp.cli validate-remediation --tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv")
python -m nmrcp.cli validate-signoffs --signoffs (Join-Path $outDir "owner-signoff-matrix.csv") --allow-pending
python -m nmrcp.cli validate-signoffs --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv")
python -m nmrcp.cli validate-approval-exception-approvals --exceptions $approvalExceptionsApproved --assessment (Join-Path $outDir "assessment.json")
python -m nmrcp.cli generate-move-payload --plan (Join-Path $outDir "nutanix-move-plan.csv") --config (Join-Path $repoRoot "examples\sample_move_payload_config.json") --out (Join-Path $outDir "move-api-payload.dry-run.json")
python -m nmrcp.cli generate-move-payload --plan (Join-Path $outDir "nutanix-move-plan.csv") --config (Join-Path $repoRoot "examples\sample_move_payload_lab_config.json") --out $labMovePayload
$labPayloadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $labMovePayload).Hash.ToLowerInvariant()
@{
    schema_version = "nmrcp_move_lab_transcript_v1"
    proof_scope = "approved_lab_move_appliance"
    environment = "lab"
    lab_move_appliance = "move-lab-01"
    payload_sha256 = $labPayloadHash
    dry_run_only = $true
    mutation_performed = $false
    production_targets = $false
    interactions = @(
        @{
            name = "create-reviewed-dry-run-plan"
            method = "POST"
            path = "/api/move/lab/dry-run-plans"
            status_code = 202
            dry_run = $true
            mutating = $false
            redacted = $true
        }
    )
    results = @{
        accepted_payloads = 1
        created_plans = 1
        started_migrations = 0
    }
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $moveLabTranscript -Encoding ASCII
python -m nmrcp.cli generate-move-lab-proof-template --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --proof-scope approved_lab_move_appliance --out (Join-Path $outDir "move-lab-proof.template.json")
python -m nmrcp.cli generate-move-lab-runbook --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --proof-template (Join-Path $outDir "move-lab-proof.template.json") --out $moveLabRunbook
python -m nmrcp.cli validate-move-lab-runbook --runbook $moveLabRunbook
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli generate-move-lab-capture-kit --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --out-dir $moveLabCaptureKitDir
python -m nmrcp.cli validate-move-lab-capture-kit --kit-dir $moveLabCaptureKitDir --payload $labMovePayload --out $moveLabCaptureKitValidation
python -m nmrcp.cli move-lab-evidence-preflight --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --capture-kit-validation $moveLabCaptureKitValidation --transcript $moveLabTranscript --transcript-validation $moveLabTranscriptValidation --proof (Join-Path $outDir "move-lab-proof.approved.json") --proof-validation (Join-Path $outDir "move-lab-proof-validation.json") --evidence-intake (Join-Path $outDir "move-lab-evidence-intake.json") --out $moveLabEvidencePreflight --report $moveLabEvidencePreflightReport
python -m nmrcp.cli validate-inventory-coverage --coverage (Join-Path $outDir "inventory-coverage.csv") --move-plan (Join-Path $outDir "nutanix-move-plan.csv")
python -m nmrcp.cli validate-move-submit-readiness --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --out $moveSubmitReadiness
python -m nmrcp.cli move-lab-readiness-packet --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --move-submit-readiness $moveSubmitReadiness --capture-kit $moveLabCaptureKitDir --capture-kit-validation $moveLabCaptureKitValidation --evidence-preflight $moveLabEvidencePreflight --evidence-preflight-report $moveLabEvidencePreflightReport --runbook $moveLabRunbook --evidence-request (Join-Path $outDir "move-lab-evidence-request.md") --closure-checklist (Join-Path $outDir "move-lab-closure-checklist.md") --out $moveLabReadinessPacket --report $moveLabReadinessPacketReport
python -m nmrcp.cli validate-move-lab-readiness-packet --packet $moveLabReadinessPacket --report $moveLabReadinessPacketReport
python -m nmrcp.cli validate-move-lab-transcript --transcript $moveLabTranscript --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --out $moveLabTranscriptValidation
python -m nmrcp.cli validate-move-lab-proof --proof (Join-Path $repoRoot "examples\sample_move_lab_proof_simulated.json") --payload $labMovePayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --out $moveLabProofValidation
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
python -m nmrcp.cli summarize-gates --dir $outDir --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") --move-lab-capture-validation $moveLabCaptureKitValidation
python -m nmrcp.cli validate-operator-gate-summary --summary (Join-Path $outDir "operator-gate-summary.md")
python -m nmrcp.cli external-proof-plan --repo-root $repoRoot --assessment-intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") --live-proof $liveProofPath --move-proof $moveLabProofValidation --out $externalProofPlan --json-out $externalProofPlanJson
python -m nmrcp.cli validate-external-proof-plan --repo-root $repoRoot --assessment-intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") --live-proof $liveProofPath --move-proof $moveLabProofValidation --report $externalProofPlan --json-report $externalProofPlanJson
python -m nmrcp.cli doctor
python -m nmrcp.cli verify-evidence --dir $outDir
python -m nmrcp.cli review-evidence --dir $outDir
python -m nmrcp.cli package-evidence --dir $outDir --out $bundlePath
python -m nmrcp.cli verify-evidence --bundle $bundlePath
python -m nmrcp.cli change-gate --dir $outDir --bundle $bundlePath
python -m nmrcp.cli change-gate --dir $outDir --bundle $bundlePath --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") --move-lab-capture-validation $moveLabCaptureKitValidation
python -m nmrcp.cli change-gate --dir $outDir --bundle $bundlePath --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") --move-lab-capture-validation $moveLabCaptureKitValidation --json | Set-Content -LiteralPath $finalChangeGateJson -Encoding ASCII
python -m nmrcp.cli validate-warning-acceptance --acceptance $warningAcceptance --warnings $finalChangeGateJson
python -m nmrcp.cli package-handoff --dir $outDir --bundle $bundlePath --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") --move-lab-capture-kit $moveLabCaptureKitDir --move-lab-capture-validation $moveLabCaptureKitValidation --move-lab-readiness-packet $moveLabReadinessPacket --source-collection-plan $sourceCollectionPlan --move-payload (Join-Path $outDir "move-api-payload.dry-run.json") --out $handoffPath
python -m nmrcp.cli verify-handoff --package $handoffPath
python -m nmrcp.cli mvp-audit --repo-root $repoRoot --assessment-dir $outDir --assessment-intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") --live-proof $liveProofPath --evidence-bundle $bundlePath --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") --move-lab-capture-validation $moveLabCaptureKitValidation --warning-acceptance $warningAcceptance --out $mvpAuditPath
python -m nmrcp.cli package-mvp-proof --mvp-audit $mvpAuditPath --live-proof $liveProofPath --move-submit-readiness $moveSubmitReadiness --move-lab-transcript $moveLabTranscriptValidation --move-lab-proof $moveLabProofValidation --move-lab-runbook $moveLabRunbook --move-lab-closure-checklist (Join-Path $outDir "move-lab-closure-checklist.md") --move-lab-capture-kit $moveLabCaptureKitDir --move-lab-capture-validation $moveLabCaptureKitValidation --move-lab-readiness-packet $moveLabReadinessPacket --source-collection-plan $sourceCollectionPlan --source-endpoint-evidence-request (Join-Path $outDir "source-endpoint-evidence-request.md") --move-lab-evidence-request (Join-Path $outDir "move-lab-evidence-request.md") --operator-gate-summary (Join-Path $outDir "operator-gate-summary.md") --handoff-package $handoffPath --external-proof-plan $externalProofPlanJson --out $mvpProofPackage
python -m nmrcp.cli verify-mvp-proof --package $mvpProofPackage
python -m nmrcp.cli summarize-mvp-proof --package $mvpProofPackage --out $mvpProofSummary
python -m nmrcp.cli validate-mvp-proof-summary --package $mvpProofPackage --summary $mvpProofSummary
python -m nmrcp.cli mvp-closure-report --package $mvpProofPackage --out $mvpClosureReport --json-out $mvpClosureReportJson
python -m nmrcp.cli validate-mvp-closure-report --package $mvpProofPackage --report $mvpClosureReport --json-report $mvpClosureReportJson
python -m nmrcp.cli launch-readiness-report --package $mvpProofPackage --repo-url "https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane" --out $launchReadinessReport --json-out $launchReadinessReportJson
python -m nmrcp.cli validate-launch-readiness-report --package $mvpProofPackage --report $launchReadinessReport --json-report $launchReadinessReportJson
python -m nmrcp.cli publication-staging-manifest --repo-root $repoRoot --out $publicationStagingManifest --json-out $publicationStagingManifestJson
python -m nmrcp.cli validate-publication-staging-manifest --repo-root $repoRoot --report $publicationStagingManifest --json-report $publicationStagingManifestJson
& $script:PythonExe -m nmrcp.cli product-readiness --repo-root $repoRoot --mvp-proof-package $mvpProofPackage --publication-staging-manifest $publicationStagingManifest --publication-staging-manifest-json $publicationStagingManifestJson --out $productReadinessReport --json-out $productReadinessReportJson
if ($LASTEXITCODE -notin @(0, 1)) {
    throw "Native command failed with exit code $LASTEXITCODE`: python -m nmrcp.cli product-readiness"
}
python -m nmrcp.cli validate-product-readiness-report --repo-root $repoRoot --mvp-proof-package $mvpProofPackage --publication-staging-manifest $publicationStagingManifest --publication-staging-manifest-json $publicationStagingManifestJson --report $productReadinessReport --json-report $productReadinessReportJson
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\move_lab_proof_workflow.ps1") -AssessmentDir $outDir -AssessmentIntake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") -SourceCollectionPlan $sourceCollectionPlan -MovePayload $labMovePayload -MoveLabProof (Join-Path $repoRoot "examples\sample_move_lab_proof_simulated.json") -MoveSubmitReview (Join-Path $repoRoot "examples\sample_move_submit_review.json") -LiveProof $liveProofPath -MvpAudit $mvpAuditPath -MoveSubmitReadiness $moveSubmitReadiness -MoveLabTranscriptValidation $moveLabTranscriptValidation -MoveLabProofValidation $moveLabProofValidation -MoveLabRunbook $moveLabRunbook -MoveLabCaptureKitDir $moveLabCaptureKitDir -MoveLabCaptureKitValidation $moveLabCaptureKitValidation -MoveLabReadinessPacket $moveLabReadinessPacket -OperatorGateSummary (Join-Path $outDir "operator-gate-summary.md") -HandoffPackage $handoffPath -ExternalProofPlan $externalProofPlanJson -MvpProofPackage $workflowMvpProofPackage -LaunchReadinessReport $workflowLaunchReadinessReport -LaunchReadinessReportJson $workflowLaunchReadinessReportJson -LaunchRepoUrl "https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane" -AllowSimulatedProof
Remove-Item Env:\NMRCP_MOVE_LAB_ACK

$cleanPayload = Get-Content -LiteralPath $labMovePayload -Raw | ConvertFrom-Json
$cleanPayload.PSObject.Properties.Remove("operator_notes")
$cleanPayload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $generatedProofPayload -Encoding ASCII
$generatedPayloadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $generatedProofPayload).Hash.ToLowerInvariant()
@{
    schema_version = "nmrcp_move_lab_transcript_v1"
    proof_scope = "approved_lab_move_appliance"
    evidence_state = "captured_approved_lab"
    environment = "lab"
    lab_move_appliance = "move-lab-01"
    payload_sha256 = $generatedPayloadHash
    dry_run_only = $true
    mutation_performed = $false
    production_targets = $false
    interactions = @(
        @{
            name = "create-reviewed-dry-run-plan"
            method = "POST"
            path = "/api/move/lab/dry-run-plans"
            status_code = 202
            dry_run = $true
            mutating = $false
            redacted = $true
            request_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            response_sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        }
    )
    results = @{
        accepted_payloads = 1
        created_plans = 1
        started_migrations = 0
    }
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $generatedProofTranscript -Encoding ASCII
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-lab-transcript --transcript $generatedProofTranscript --payload $generatedProofPayload --review (Join-Path $repoRoot "examples\sample_move_submit_review.json") --out $generatedProofTranscriptValidation
powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\move_lab_proof_workflow.ps1") -AssessmentDir $outDir -AssessmentIntake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") -SourceCollectionPlan $sourceCollectionPlan -MovePayload $generatedProofPayload -MoveLabProof $generatedApprovedProof -GenerateApprovedProof -ApprovedBy "Smoke Lab Reviewer" -MoveLabTranscript $generatedProofTranscript -MoveLabTranscriptValidation $generatedProofTranscriptValidation -MoveSubmitReview (Join-Path $repoRoot "examples\sample_move_submit_review.json") -LiveProof $liveProofPath -MvpAudit $generatedProofMvpAudit -MoveSubmitReadiness (Join-Path $outDir "move-submit-readiness.generated-proof-rehearsal.json") -MoveLabProofValidation $generatedApprovedProofValidation -MoveLabEvidenceIntake $generatedProofEvidenceIntake -MoveLabRunbook $moveLabRunbook -MoveLabCaptureKitDir $moveLabCaptureKitDir -MoveLabCaptureKitValidation $moveLabCaptureKitValidation -MoveLabReadinessPacket $moveLabReadinessPacket -EvidenceBundle $bundlePath -ValidationResults (Join-Path $repoRoot "examples\sample_validation_results.csv") -RemediationTracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") -Signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") -ApprovalExceptions $approvalExceptionsApproved -OperatorReview (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") -OperatorGateSummary (Join-Path $outDir "operator-gate-summary.generated-proof-rehearsal.md") -HandoffPackage $handoffPath -ExternalProofPlanReport $generatedExternalProofPlan -ExternalProofPlanJson $generatedExternalProofPlanJson -MvpProofPackage $generatedProofPackage -LaunchReadinessReport $generatedProofLaunchReadinessReport -LaunchReadinessReportJson $generatedProofLaunchReadinessReportJson -LaunchRepoUrl "https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane"
Remove-Item Env:\NMRCP_MOVE_LAB_ACK

@"
schema_version,assessment_dir,review_status,reviewed_by,reviewed_at,change_reference,coverage_reviewed,readiness_reviewed,move_plan_reviewed,evidence_reviewed,redaction_reviewed,rollback_reviewed,capacity_reviewed,target_reconciliation_reviewed,network_mapping_reviewed,app_map_reviewed,notes
nmrcp_operator_review_v1,$workflowOutDir,approved,Lab Migration Lead,2026-07-24T12:00:00+00:00,CHG-LAB-WORKFLOW,yes,yes,yes,yes,yes,yes,yes,yes,yes,yes,Lab operator reviewed smoke workflow assessment coverage readiness Move staging evidence redaction rollback and target context.
"@ | Set-Content -LiteralPath $workflowOperatorReview -Encoding ASCII

python -m nmrcp.cli run-assessment --inventory (Join-Path $repoRoot "examples\sample_inventory.json") --metadata (Join-Path $repoRoot "examples\sample_metadata.csv") --dependencies (Join-Path $repoRoot "examples\sample_dependencies.csv") --capacity (Join-Path $repoRoot "examples\sample_target_capacity.json") --prism-inventory (Join-Path $repoRoot "examples\sample_prism_inventory.json") --source-networks (Join-Path $repoRoot "outputs\live-collector-smoke\vcenter-networks.json") --move-config (Join-Path $repoRoot "examples\sample_move_payload_config.json") --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review $workflowOperatorReview --move-lab-capture-kit $moveLabCaptureKitDir --move-lab-capture-validation $moveLabCaptureKitValidation --out $workflowOutDir

python -m nmrcp.cli mvp-audit --repo-root $repoRoot --assessment-dir $outDir --assessment-intake (Join-Path $repoRoot "examples\sample_assessment_intake.csv") --live-proof $liveProofPath --evidence-bundle $bundlePath --validation-results (Join-Path $repoRoot "examples\sample_validation_results.csv") --remediation-tracker (Join-Path $repoRoot "examples\sample_remediation_tracker_closed.csv") --signoffs (Join-Path $repoRoot "examples\sample_owner_signoffs_approved.csv") --approval-exceptions $approvalExceptionsApproved --operator-review (Join-Path $repoRoot "examples\sample_operator_review_approved.csv") --move-lab-capture-validation $moveLabCaptureKitValidation --warning-acceptance $warningAcceptance --out $mvpAuditPath
python -m nmrcp.cli package-mvp-proof --mvp-audit $mvpAuditPath --live-proof $liveProofPath --move-submit-readiness $moveSubmitReadiness --move-lab-transcript $moveLabTranscriptValidation --move-lab-proof $moveLabProofValidation --move-lab-runbook $moveLabRunbook --move-lab-closure-checklist (Join-Path $outDir "move-lab-closure-checklist.md") --move-lab-capture-kit $moveLabCaptureKitDir --move-lab-capture-validation $moveLabCaptureKitValidation --move-lab-readiness-packet $moveLabReadinessPacket --source-collection-plan $sourceCollectionPlan --source-endpoint-evidence-request (Join-Path $outDir "source-endpoint-evidence-request.md") --move-lab-evidence-request (Join-Path $outDir "move-lab-evidence-request.md") --operator-gate-summary (Join-Path $outDir "operator-gate-summary.md") --handoff-package $handoffPath --external-proof-plan $externalProofPlanJson --out $mvpProofPackage
python -m nmrcp.cli verify-mvp-proof --package $mvpProofPackage
python -m nmrcp.cli summarize-mvp-proof --package $mvpProofPackage --out $mvpProofSummary
python -m nmrcp.cli validate-mvp-proof-summary --package $mvpProofPackage --summary $mvpProofSummary
python -m nmrcp.cli mvp-closure-report --package $mvpProofPackage --out $mvpClosureReport --json-out $mvpClosureReportJson
python -m nmrcp.cli validate-mvp-closure-report --package $mvpProofPackage --report $mvpClosureReport --json-report $mvpClosureReportJson
python -m nmrcp.cli launch-readiness-report --package $mvpProofPackage --repo-url "https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane" --out $launchReadinessReport --json-out $launchReadinessReportJson
python -m nmrcp.cli validate-launch-readiness-report --package $mvpProofPackage --report $launchReadinessReport --json-report $launchReadinessReportJson

if (-not (Test-Path -LiteralPath $liveReadinessPath)) {
    throw "Missing smoke artifact: smoke-live-readiness.json"
}
if (-not (Test-Path -LiteralPath $liveProofPath)) {
    throw "Missing smoke artifact: smoke-live-proof-validation.json"
}
if (-not (Test-Path -LiteralPath $externalProofPlan)) {
    throw "Missing smoke artifact: external-proof-plan.md"
}
if (-not (Test-Path -LiteralPath $externalProofPlanJson)) {
    throw "Missing smoke artifact: external-proof-plan.json"
}
if (-not (Test-Path -LiteralPath $mvpAuditPath)) {
    throw "Missing smoke artifact: smoke-mvp-audit.json"
}
if (-not (Test-Path -LiteralPath $finalChangeGateJson)) {
    throw "Missing smoke artifact: smoke-change-gate-final.json"
}
if (-not (Test-Path -LiteralPath $mvpProofPackage)) {
    throw "Missing smoke artifact: smoke-mvp-proof-package.zip"
}
if (-not (Test-Path -LiteralPath $mvpProofSummary)) {
    throw "Missing smoke artifact: smoke-mvp-proof-summary.md"
}
if (-not (Test-Path -LiteralPath $mvpClosureReport)) {
    throw "Missing smoke artifact: smoke-mvp-closure-report.md"
}
if (-not (Test-Path -LiteralPath $mvpClosureReportJson)) {
    throw "Missing smoke artifact: smoke-mvp-closure-report.json"
}
if (-not (Test-Path -LiteralPath $launchReadinessReport)) {
    throw "Missing smoke artifact: smoke-launch-readiness-report.md"
}
if (-not (Test-Path -LiteralPath $launchReadinessReportJson)) {
    throw "Missing smoke artifact: smoke-launch-readiness-report.json"
}
if (-not (Test-Path -LiteralPath $publicationStagingManifest)) {
    throw "Missing smoke artifact: smoke-publication-staging-manifest.md"
}
if (-not (Test-Path -LiteralPath $publicationStagingManifestJson)) {
    throw "Missing smoke artifact: smoke-publication-staging-manifest.json"
}
if (-not (Test-Path -LiteralPath $productReadinessReport)) {
    throw "Missing smoke artifact: smoke-product-readiness-report.md"
}
if (-not (Test-Path -LiteralPath $productReadinessReportJson)) {
    throw "Missing smoke artifact: smoke-product-readiness-report.json"
}
if (-not (Test-Path -LiteralPath $workflowMvpProofPackage)) {
    throw "Missing smoke artifact: smoke-move-lab-workflow-proof-package.zip"
}
if (-not (Test-Path -LiteralPath $workflowLaunchReadinessReport)) {
    throw "Missing smoke artifact: smoke-move-lab-workflow-launch-readiness-report.md"
}
if (-not (Test-Path -LiteralPath $workflowLaunchReadinessReportJson)) {
    throw "Missing smoke artifact: smoke-move-lab-workflow-launch-readiness-report.json"
}
if (-not (Test-Path -LiteralPath $generatedApprovedProof)) {
    throw "Missing smoke artifact: move-lab-proof.generated-approved.json"
}
if (-not (Test-Path -LiteralPath $generatedApprovedProofValidation)) {
    throw "Missing smoke artifact: move-lab-proof-validation.generated-approved.json"
}
if (-not (Test-Path -LiteralPath $generatedProofEvidenceIntake)) {
    throw "Missing smoke artifact: move-lab-evidence-intake.generated-proof-rehearsal.json"
}
if (-not (Test-Path -LiteralPath $generatedExternalProofPlan)) {
    throw "Missing smoke artifact: external-proof-plan.generated-proof-rehearsal.md"
}
if (-not (Test-Path -LiteralPath $generatedExternalProofPlanJson)) {
    throw "Missing smoke artifact: external-proof-plan.generated-proof-rehearsal.json"
}
if (-not (Test-Path -LiteralPath $generatedProofPackage)) {
    throw "Missing smoke artifact: smoke-generated-proof-rehearsal-package.zip"
}
if (-not (Test-Path -LiteralPath $generatedProofLaunchReadinessReport)) {
    throw "Missing smoke artifact: smoke-generated-proof-rehearsal-launch-readiness-report.md"
}
if (-not (Test-Path -LiteralPath $generatedProofLaunchReadinessReportJson)) {
    throw "Missing smoke artifact: smoke-generated-proof-rehearsal-launch-readiness-report.json"
}
if (-not (Test-Path -LiteralPath $moveLabProofValidation)) {
    throw "Missing smoke artifact: move-lab-proof-validation.simulated.json"
}
if (-not (Test-Path -LiteralPath $moveLabTranscriptValidation)) {
    throw "Missing smoke artifact: move-lab-transcript-validation.json"
}
if (-not (Test-Path -LiteralPath $moveLabRunbook)) {
    throw "Missing smoke artifact: move-lab-execution-runbook.md"
}
if (-not (Test-Path -LiteralPath (Join-Path $moveLabCaptureKitDir "move-lab-transcript.template.json"))) {
    throw "Missing smoke artifact: move-lab-capture-kit\move-lab-transcript.template.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $moveLabCaptureKitDir "move-lab-capture-checklist.md"))) {
    throw "Missing smoke artifact: move-lab-capture-kit\move-lab-capture-checklist.md"
}
if (-not (Test-Path -LiteralPath $moveLabCaptureKitValidation)) {
    throw "Missing smoke artifact: move-lab-capture-kit-validation.json"
}
if (-not (Test-Path -LiteralPath $moveLabEvidencePreflight)) {
    throw "Missing smoke artifact: move-lab-evidence-preflight.json"
}
if (-not (Test-Path -LiteralPath $moveLabEvidencePreflightReport)) {
    throw "Missing smoke artifact: move-lab-evidence-preflight.md"
}
if (-not (Test-Path -LiteralPath $moveLabReadinessPacket)) {
    throw "Missing smoke artifact: move-lab-readiness-packet.json"
}
if (-not (Test-Path -LiteralPath $moveLabReadinessPacketReport)) {
    throw "Missing smoke artifact: move-lab-readiness-packet.md"
}
if (-not (Test-Path -LiteralPath (Join-Path $liveCollectorSmokeDir "vcenter-inventory.json"))) {
    throw "Missing smoke artifact: live-collector-smoke\vcenter-inventory.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $liveCollectorSmokeDir "prism-inventory.json"))) {
    throw "Missing smoke artifact: live-collector-smoke\prism-inventory.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $liveCollectorSmokeDir "prism-capacity.json"))) {
    throw "Missing smoke artifact: live-collector-smoke\prism-capacity.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $liveCollectorSmokeDir "collection-summary.json"))) {
    throw "Missing smoke artifact: live-collector-smoke\collection-summary.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $liveCollectorSmokeDir "assessment\evidence-manifest.json"))) {
    throw "Missing smoke artifact: live-collector-smoke\assessment\evidence-manifest.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $liveCollectorSmokeDir "assessment\target-capacity-fit.csv"))) {
    throw "Missing smoke artifact: live-collector-smoke\assessment\target-capacity-fit.csv"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "outputs\smoke-workflow-handoff-package.zip"))) {
    throw "Missing smoke artifact: smoke-workflow-handoff-package.zip"
}
if (-not (Test-Path -LiteralPath $operatorReviewTemplate)) {
    throw "Missing smoke artifact: smoke-operator-review.template.csv"
}
if (-not (Test-Path -LiteralPath $assessmentIntakeTemplate)) {
    throw "Missing smoke artifact: smoke-assessment-intake.template.csv"
}
if (-not (Test-Path -LiteralPath $sourceCollectionPlan)) {
    throw "Missing smoke artifact: smoke-source-collection-plan.md"
}
if (-not (Test-Path -LiteralPath $cmdbMetadata)) {
    throw "Missing smoke artifact: smoke-cmdb-metadata.csv"
}
if (-not (Test-Path -LiteralPath (Join-Path $appMapOutDir "dependency-sequence.csv"))) {
    throw "Missing smoke artifact: smoke-app-map\dependency-sequence.csv"
}

$required = @(
    "assessment.json",
    "inventory-coverage.csv",
    "migration-waves.csv",
    "target-readiness-comparison.csv",
    "dependency-sequence.csv",
    "dependency-review.csv",
    "tools-driver-readiness.csv",
    "storage-posture.csv",
    "recovery-readiness.csv",
    "move-staging-readiness.csv",
    "remediation-tracker.csv",
    "owner-risk-summary.csv",
    "owner-signoff-matrix.csv",
    "approval-exceptions.csv",
    "nutanix-move-plan.csv",
    "target-capacity-fit.csv",
    "target-reconciliation.csv",
    "source-network-validation.csv",
    "target-network-mapping.csv",
    "compatibility-research.csv",
    "operator-gate-summary.md",
    "move-api-payload.dry-run.json",
    "move-api-payload.lab.dry-run.json",
    "move-lab-execution-runbook.md",
    "move-lab-proof.template.json",
    "move-lab-evidence-request.md",
    "move-lab-evidence-preflight.json",
    "move-lab-evidence-preflight.md",
    "move-lab-readiness-packet.json",
    "move-lab-readiness-packet.md",
    "source-endpoint-evidence-request.md",
    "move-submit-readiness.json",
    "move-lab-proof-validation.simulated.json",
    "rollback-plan.csv",
    "change-board-evidence.md",
    "wave-execution-calendar.csv",
    "partner-handoff-matrix.csv",
    "migration-runbook.md",
    "operator-portal.html",
    "operator-report.html",
    "operator-dashboard.html",
    "pre-post-validation-checklist.md",
    "workload-validation-checklist.csv",
    "migration-execution-queue.csv",
    "prism-category-mapping.csv",
    "stakeholder-communication-plan.csv",
    "what-will-break-report.csv",
    "connectivity-checklist.csv",
    "identity-cutover-plan.csv",
    "evidence-manifest.json"
)

foreach ($name in $required) {
    $path = Join-Path $outDir $name
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing smoke artifact: $name"
    }
}

Write-Host "Smoke test passed: $outDir"
