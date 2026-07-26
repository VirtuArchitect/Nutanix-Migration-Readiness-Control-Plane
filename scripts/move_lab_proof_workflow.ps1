param(
    [Parameter(Mandatory=$true)][string]$AssessmentDir,
    [Parameter(Mandatory=$true)][string]$MoveLabProof,
    [Parameter(Mandatory=$true)][string]$MoveSubmitReview,
    [Parameter(Mandatory=$true)][string]$LiveProof,
    [Parameter(Mandatory=$true)][string]$MvpAudit,
    [string]$AssessmentIntake = "",
    [string]$SourceCollectionPlan = "",
    [string]$MovePayload = "",
    [string]$MoveSubmitReadiness = "",
    [string]$MoveLabTranscript = "",
    [string]$MoveLabTranscriptValidation = "",
    [string]$MoveLabProofValidation = "",
    [string]$MoveLabEvidenceIntake = "",
    [string]$MoveLabRunbook = "",
    [string]$MoveLabCaptureKitDir = "",
    [string]$MoveLabCaptureKitValidation = "",
    [string]$MoveLabReadinessPacket = "",
    [string]$EvidenceBundle = "",
    [string]$ValidationResults = "",
    [string]$RemediationTracker = "",
    [string]$Signoffs = "",
    [string]$ApprovalExceptions = "",
    [string]$OperatorReview = "",
    [string]$WarningAcceptance = "",
    [string]$OperatorGateSummary = "",
    [string]$HandoffPackage = "",
    [string]$ExternalProofPlan = "",
    [string]$ExternalProofPlanReport = "",
    [string]$ExternalProofPlanJson = "",
    [string]$MvpProofPackage = "",
    [string]$MvpClosureReport = "",
    [string]$MvpClosureReportJson = "",
    [string]$LaunchReadinessReport = "",
    [string]$LaunchReadinessReportJson = "",
    [string]$LaunchRepoUrl = "",
    [string]$LaunchAudience = "",
    [string]$ApprovedBy = "",
    [switch]$GenerateApprovedProof,
    [switch]$AllowSimulatedProof
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $repoRoot "src"

function Resolve-RequiredPath {
    param(
        [Parameter(Mandatory=$true)][string]$PathValue,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PathValue)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Missing required $Label`: $resolved"
    }
    return $resolved
}

function Resolve-OutputPath {
    param(
        [Parameter(Mandatory=$true)][string]$PathValue,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PathValue)
    $parent = Split-Path -Parent $resolved
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    return $resolved
}

function Reset-OutputFile {
    param(
        [Parameter(Mandatory=$true)][string]$PathValue,
        [Parameter(Mandatory=$true)][string]$Label
    )

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return
    }
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            if (Test-Path -LiteralPath $PathValue) {
                Remove-Item -LiteralPath $PathValue -Force
            }
            if (-not (Test-Path -LiteralPath $PathValue)) {
                return
            }
        } catch {
            if ($attempt -eq 5) {
                throw "Unable to reset output $Label`: $PathValue. Last error: $($_.Exception.Message)"
            }
            Start-Sleep -Milliseconds (250 * $attempt)
        }
    }
    throw "Unable to reset output $Label`: $PathValue"
}

function Invoke-Nmrcp {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)

    & python -m nmrcp.cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "nmrcp command failed: $($Arguments -join ' ')"
    }
}

if ($env:NMRCP_MOVE_LAB_ACK -ne "I_UNDERSTAND_LAB_ONLY") {
    throw "Set NMRCP_MOVE_LAB_ACK=I_UNDERSTAND_LAB_ONLY before running this lab workflow."
}

$assessmentPath = Resolve-RequiredPath -PathValue $AssessmentDir -Label "AssessmentDir"
$reviewPath = Resolve-RequiredPath -PathValue $MoveSubmitReview -Label "MoveSubmitReview"
$liveProofPath = Resolve-RequiredPath -PathValue $LiveProof -Label "LiveProof"
$assessmentIntakePath = ""
if (-not [string]::IsNullOrWhiteSpace($AssessmentIntake)) {
    $assessmentIntakePath = Resolve-RequiredPath -PathValue $AssessmentIntake -Label "AssessmentIntake"
}
if ($GenerateApprovedProof) {
    $mvpAuditPath = Resolve-OutputPath -PathValue $MvpAudit -Label "MvpAudit"
} else {
    $mvpAuditPath = Resolve-RequiredPath -PathValue $MvpAudit -Label "MvpAudit"
}

if ([string]::IsNullOrWhiteSpace($MovePayload)) {
    $MovePayload = Join-Path $assessmentPath "move-api-payload.lab.dry-run.json"
}
if ([string]::IsNullOrWhiteSpace($MoveSubmitReadiness)) {
    $MoveSubmitReadiness = Join-Path $assessmentPath "move-submit-readiness.json"
}
if ([string]::IsNullOrWhiteSpace($MoveLabProofValidation)) {
    $MoveLabProofValidation = Join-Path $assessmentPath "move-lab-proof-validation.json"
}
if ([string]::IsNullOrWhiteSpace($OperatorGateSummary)) {
    $OperatorGateSummary = Join-Path $assessmentPath "operator-gate-summary.md"
}
if ([string]::IsNullOrWhiteSpace($MoveLabRunbook)) {
    $MoveLabRunbook = Join-Path $assessmentPath "move-lab-execution-runbook.md"
}
if ([string]::IsNullOrWhiteSpace($MvpProofPackage)) {
    $MvpProofPackage = Join-Path (Split-Path -Parent $assessmentPath) "$(Split-Path -Leaf $assessmentPath)-mvp-proof-package.zip"
}

$movePayloadPath = Resolve-RequiredPath -PathValue $MovePayload -Label "MovePayload"
$submitReadinessOut = Resolve-OutputPath -PathValue $MoveSubmitReadiness -Label "MoveSubmitReadiness"
$transcriptValidationPath = ""
if (-not [string]::IsNullOrWhiteSpace($MoveLabTranscriptValidation)) {
    $transcriptValidationPath = Resolve-RequiredPath -PathValue $MoveLabTranscriptValidation -Label "MoveLabTranscriptValidation"
}
$transcriptPath = ""
if (-not [string]::IsNullOrWhiteSpace($MoveLabTranscript)) {
    $transcriptPath = Resolve-RequiredPath -PathValue $MoveLabTranscript -Label "MoveLabTranscript"
}
$captureKitValidationPath = ""
if (-not [string]::IsNullOrWhiteSpace($MoveLabCaptureKitValidation)) {
    $captureKitValidationPath = Resolve-RequiredPath -PathValue $MoveLabCaptureKitValidation -Label "MoveLabCaptureKitValidation"
}
$evidenceBundlePath = ""
if (-not [string]::IsNullOrWhiteSpace($EvidenceBundle)) {
    $evidenceBundlePath = Resolve-RequiredPath -PathValue $EvidenceBundle -Label "EvidenceBundle"
}
$validationResultsPath = ""
if (-not [string]::IsNullOrWhiteSpace($ValidationResults)) {
    $validationResultsPath = Resolve-RequiredPath -PathValue $ValidationResults -Label "ValidationResults"
}
$remediationTrackerPath = ""
if (-not [string]::IsNullOrWhiteSpace($RemediationTracker)) {
    $remediationTrackerPath = Resolve-RequiredPath -PathValue $RemediationTracker -Label "RemediationTracker"
}
$signoffsPath = ""
if (-not [string]::IsNullOrWhiteSpace($Signoffs)) {
    $signoffsPath = Resolve-RequiredPath -PathValue $Signoffs -Label "Signoffs"
}
$approvalExceptionsPath = ""
if (-not [string]::IsNullOrWhiteSpace($ApprovalExceptions)) {
    $approvalExceptionsPath = Resolve-RequiredPath -PathValue $ApprovalExceptions -Label "ApprovalExceptions"
}
$operatorReviewPath = ""
if (-not [string]::IsNullOrWhiteSpace($OperatorReview)) {
    $operatorReviewPath = Resolve-RequiredPath -PathValue $OperatorReview -Label "OperatorReview"
}
$warningAcceptancePath = ""
if (-not [string]::IsNullOrWhiteSpace($WarningAcceptance)) {
    $warningAcceptancePath = Resolve-RequiredPath -PathValue $WarningAcceptance -Label "WarningAcceptance"
}
$labProofValidationOut = Resolve-OutputPath -PathValue $MoveLabProofValidation -Label "MoveLabProofValidation"
$evidenceIntakeOut = ""
if (-not [string]::IsNullOrWhiteSpace($MoveLabEvidenceIntake)) {
    $evidenceIntakeOut = Resolve-OutputPath -PathValue $MoveLabEvidenceIntake -Label "MoveLabEvidenceIntake"
}
$gateSummaryOut = Resolve-OutputPath -PathValue $OperatorGateSummary -Label "OperatorGateSummary"
$mvpProofPackageOut = Resolve-OutputPath -PathValue $MvpProofPackage -Label "MvpProofPackage"
$mvpClosureReportOut = ""
if (-not [string]::IsNullOrWhiteSpace($MvpClosureReport)) {
    $mvpClosureReportOut = Resolve-OutputPath -PathValue $MvpClosureReport -Label "MvpClosureReport"
    if ([string]::IsNullOrWhiteSpace($MvpClosureReportJson)) {
        $MvpClosureReportJson = "$mvpClosureReportOut.json"
    }
}
$mvpClosureReportJsonOut = ""
if (-not [string]::IsNullOrWhiteSpace($MvpClosureReportJson)) {
    $mvpClosureReportJsonOut = Resolve-OutputPath -PathValue $MvpClosureReportJson -Label "MvpClosureReportJson"
}
$launchReadinessReportOut = ""
if (-not [string]::IsNullOrWhiteSpace($LaunchReadinessReport)) {
    $launchReadinessReportOut = Resolve-OutputPath -PathValue $LaunchReadinessReport -Label "LaunchReadinessReport"
    if ([string]::IsNullOrWhiteSpace($LaunchReadinessReportJson)) {
        $LaunchReadinessReportJson = "$launchReadinessReportOut.json"
    }
}
$launchReadinessReportJsonOut = ""
if (-not [string]::IsNullOrWhiteSpace($LaunchReadinessReportJson)) {
    $launchReadinessReportJsonOut = Resolve-OutputPath -PathValue $LaunchReadinessReportJson -Label "LaunchReadinessReportJson"
}

Reset-OutputFile -PathValue $submitReadinessOut -Label "MoveSubmitReadiness"
Invoke-Nmrcp -Arguments @(
    "validate-move-submit-readiness",
    "--payload", $movePayloadPath,
    "--review", $reviewPath,
    "--out", $submitReadinessOut
)

if ($GenerateApprovedProof) {
    if ([string]::IsNullOrWhiteSpace($ApprovedBy)) {
        throw "-ApprovedBy is required with -GenerateApprovedProof."
    }
    if ([string]::IsNullOrWhiteSpace($transcriptPath) -or [string]::IsNullOrWhiteSpace($transcriptValidationPath)) {
        throw "-GenerateApprovedProof requires -MoveLabTranscript and -MoveLabTranscriptValidation."
    }
    $proofPath = Resolve-OutputPath -PathValue $MoveLabProof -Label "MoveLabProof"
    Reset-OutputFile -PathValue $proofPath -Label "MoveLabProof"
    Invoke-Nmrcp -Arguments @(
        "generate-approved-move-lab-proof",
        "--payload", $movePayloadPath,
        "--review", $reviewPath,
        "--transcript", $transcriptPath,
        "--transcript-validation", $transcriptValidationPath,
        "--approved-by", $ApprovedBy,
        "--out", $proofPath
    )
} else {
    $proofPath = Resolve-RequiredPath -PathValue $MoveLabProof -Label "MoveLabProof"
}

$proofArgs = @(
    "validate-move-lab-proof",
    "--proof", $proofPath,
    "--payload", $movePayloadPath,
    "--review", $reviewPath,
    "--out", $labProofValidationOut
)
if (-not [string]::IsNullOrWhiteSpace($transcriptValidationPath)) {
    $proofArgs += @("--transcript-validation", $transcriptValidationPath)
}
Reset-OutputFile -PathValue $labProofValidationOut -Label "MoveLabProofValidation"
Invoke-Nmrcp -Arguments $proofArgs

$labProofJson = Get-Content -LiteralPath $labProofValidationOut -Raw | ConvertFrom-Json
$scopeCheck = @($labProofJson.checks | Where-Object { $_.name -eq "move-lab-proof-scope" }) | Select-Object -First 1
$isApproved = (
    $labProofJson.status -eq "pass" -and
    $null -ne $scopeCheck -and
    $scopeCheck.status -eq "pass" -and
    $scopeCheck.detail -eq "approved_lab_move_appliance"
)

if (-not $isApproved -and -not $AllowSimulatedProof) {
    throw "Move lab proof is not approved_lab_move_appliance. Use -AllowSimulatedProof only for local smoke or simulated contract proof."
}

if ($isApproved) {
    if (
        -not [string]::IsNullOrWhiteSpace($evidenceIntakeOut) -and
        -not [string]::IsNullOrWhiteSpace($transcriptPath) -and
        -not [string]::IsNullOrWhiteSpace($transcriptValidationPath) -and
        -not [string]::IsNullOrWhiteSpace($captureKitValidationPath)
    ) {
        Reset-OutputFile -PathValue $evidenceIntakeOut -Label "MoveLabEvidenceIntake"
        Invoke-Nmrcp -Arguments @(
            "validate-move-lab-evidence-intake",
            "--payload", $movePayloadPath,
            "--review", $reviewPath,
            "--transcript", $transcriptPath,
            "--transcript-validation", $transcriptValidationPath,
            "--proof", $proofPath,
            "--proof-validation", $labProofValidationOut,
            "--capture-kit-validation", $captureKitValidationPath,
            "--out", $evidenceIntakeOut
        )
    } elseif (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut)) {
        throw "Move lab evidence intake requires -MoveLabTranscript, -MoveLabTranscriptValidation, and -MoveLabCaptureKitValidation."
    }

    $summaryArgs = @(
        "summarize-gates",
        "--dir", $assessmentPath,
        "--move-lab-proof", $labProofValidationOut,
        "--out", $gateSummaryOut
    )
    if (-not [string]::IsNullOrWhiteSpace($captureKitValidationPath)) {
        $summaryArgs += @("--move-lab-capture-validation", $captureKitValidationPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($validationResultsPath)) {
        $summaryArgs += @("--validation-results", $validationResultsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($remediationTrackerPath)) {
        $summaryArgs += @("--remediation-tracker", $remediationTrackerPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($signoffsPath)) {
        $summaryArgs += @("--signoffs", $signoffsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($approvalExceptionsPath)) {
        $summaryArgs += @("--approval-exceptions", $approvalExceptionsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($operatorReviewPath)) {
        $summaryArgs += @("--operator-review", $operatorReviewPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut) -and (Test-Path -LiteralPath $evidenceIntakeOut)) {
        $summaryArgs += @("--move-lab-evidence-intake", $evidenceIntakeOut)
    }
    Reset-OutputFile -PathValue $gateSummaryOut -Label "OperatorGateSummary"
    Invoke-Nmrcp -Arguments $summaryArgs

    $gateArgs = @(
        "change-gate",
        "--dir", $assessmentPath,
        "--move-lab-proof", $labProofValidationOut
    )
    if (-not [string]::IsNullOrWhiteSpace($captureKitValidationPath)) {
        $gateArgs += @("--move-lab-capture-validation", $captureKitValidationPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($evidenceBundlePath)) {
        $gateArgs += @("--bundle", $evidenceBundlePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($validationResultsPath)) {
        $gateArgs += @("--validation-results", $validationResultsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($remediationTrackerPath)) {
        $gateArgs += @("--remediation-tracker", $remediationTrackerPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($signoffsPath)) {
        $gateArgs += @("--signoffs", $signoffsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($approvalExceptionsPath)) {
        $gateArgs += @("--approval-exceptions", $approvalExceptionsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($operatorReviewPath)) {
        $gateArgs += @("--operator-review", $operatorReviewPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut) -and (Test-Path -LiteralPath $evidenceIntakeOut)) {
        $gateArgs += @("--move-lab-evidence-intake", $evidenceIntakeOut)
    }
    Invoke-Nmrcp -Arguments $gateArgs

    if (-not [string]::IsNullOrWhiteSpace($HandoffPackage)) {
        $handoffOut = Resolve-OutputPath -PathValue $HandoffPackage -Label "HandoffPackage"
        Reset-OutputFile -PathValue $handoffOut -Label "HandoffPackage"
        $handoffArgs = @(
            "package-handoff",
            "--dir", $assessmentPath,
            "--out", $handoffOut,
            "--move-lab-proof", $labProofValidationOut,
            "--move-lab-evidence-intake", $evidenceIntakeOut
        )
        if (-not [string]::IsNullOrWhiteSpace($evidenceBundlePath)) {
            $handoffArgs += @("--bundle", $evidenceBundlePath)
        }
        if (-not [string]::IsNullOrWhiteSpace($validationResultsPath)) {
            $handoffArgs += @("--validation-results", $validationResultsPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($remediationTrackerPath)) {
            $handoffArgs += @("--remediation-tracker", $remediationTrackerPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($signoffsPath)) {
            $handoffArgs += @("--signoffs", $signoffsPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($approvalExceptionsPath)) {
            $handoffArgs += @("--approval-exceptions", $approvalExceptionsPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($operatorReviewPath)) {
            $handoffArgs += @("--operator-review", $operatorReviewPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($MoveLabCaptureKitDir)) {
            $captureKitPath = Resolve-RequiredPath -PathValue $MoveLabCaptureKitDir -Label "MoveLabCaptureKitDir"
            $handoffArgs += @("--move-lab-capture-kit", $captureKitPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($captureKitValidationPath)) {
            $handoffArgs += @("--move-lab-capture-validation", $captureKitValidationPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($MoveLabReadinessPacket)) {
            $readinessPacketPath = Resolve-RequiredPath -PathValue $MoveLabReadinessPacket -Label "MoveLabReadinessPacket"
            $handoffArgs += @("--move-lab-readiness-packet", $readinessPacketPath)
        }
        if (-not [string]::IsNullOrWhiteSpace($SourceCollectionPlan)) {
            $handoffSourceCollectionPlanPath = Resolve-RequiredPath -PathValue $SourceCollectionPlan -Label "SourceCollectionPlan"
            $handoffArgs += @("--source-collection-plan", $handoffSourceCollectionPlanPath)
        }
        if (Test-Path -LiteralPath $movePayloadPath) {
            $handoffArgs += @("--move-payload", $movePayloadPath)
        }
        Invoke-Nmrcp -Arguments $handoffArgs
        Invoke-Nmrcp -Arguments @("verify-handoff", "--package", $handoffOut)
    }

    $auditArgs = @(
        "mvp-audit",
        "--repo-root", $repoRoot,
        "--assessment-dir", $assessmentPath,
        "--live-proof", $liveProofPath,
        "--move-proof", $labProofValidationOut,
        "--move-lab-evidence-intake", $evidenceIntakeOut,
        "--out", $mvpAuditPath
    )
    if (-not [string]::IsNullOrWhiteSpace($assessmentIntakePath)) {
        $auditArgs += @("--assessment-intake", $assessmentIntakePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($evidenceBundlePath)) {
        $auditArgs += @("--evidence-bundle", $evidenceBundlePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($validationResultsPath)) {
        $auditArgs += @("--validation-results", $validationResultsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($remediationTrackerPath)) {
        $auditArgs += @("--remediation-tracker", $remediationTrackerPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($signoffsPath)) {
        $auditArgs += @("--signoffs", $signoffsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($approvalExceptionsPath)) {
        $auditArgs += @("--approval-exceptions", $approvalExceptionsPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($operatorReviewPath)) {
        $auditArgs += @("--operator-review", $operatorReviewPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($captureKitValidationPath)) {
        $auditArgs += @("--move-lab-capture-validation", $captureKitValidationPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($warningAcceptancePath)) {
        $auditArgs += @("--warning-acceptance", $warningAcceptancePath)
    }
    Reset-OutputFile -PathValue $mvpAuditPath -Label "MvpAudit"
    Invoke-Nmrcp -Arguments $auditArgs
} else {
    Write-Warning "Simulated Move proof accepted for proof packaging only; final change gate and handoff remain unproven."
}

$externalProofPlanForPackage = ""
if (-not [string]::IsNullOrWhiteSpace($ExternalProofPlan)) {
    $externalProofPlanForPackage = Resolve-RequiredPath -PathValue $ExternalProofPlan -Label "ExternalProofPlan"
}

if (-not [string]::IsNullOrWhiteSpace($ExternalProofPlanJson)) {
    $externalProofPlanJsonOut = Resolve-OutputPath -PathValue $ExternalProofPlanJson -Label "ExternalProofPlanJson"
    $externalProofPlanReportOut = ""
    if (-not [string]::IsNullOrWhiteSpace($ExternalProofPlanReport)) {
        $externalProofPlanReportOut = Resolve-OutputPath -PathValue $ExternalProofPlanReport -Label "ExternalProofPlanReport"
        Reset-OutputFile -PathValue $externalProofPlanReportOut -Label "ExternalProofPlanReport"
    }
    Reset-OutputFile -PathValue $externalProofPlanJsonOut -Label "ExternalProofPlanJson"

    $externalPlanArgs = @(
        "external-proof-plan",
        "--repo-root", $repoRoot,
        "--live-proof", $liveProofPath,
        "--move-proof", $labProofValidationOut,
        "--json-out", $externalProofPlanJsonOut
    )
    if (-not [string]::IsNullOrWhiteSpace($assessmentIntakePath)) {
        $externalPlanArgs += @("--assessment-intake", $assessmentIntakePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut) -and (Test-Path -LiteralPath $evidenceIntakeOut)) {
        $externalPlanArgs += @("--move-lab-evidence-intake", $evidenceIntakeOut)
    }
    if (-not [string]::IsNullOrWhiteSpace($externalProofPlanReportOut)) {
        $externalPlanArgs += @("--out", $externalProofPlanReportOut)
    }
    Invoke-Nmrcp -Arguments $externalPlanArgs

    $validateExternalPlanArgs = @(
        "validate-external-proof-plan",
        "--repo-root", $repoRoot,
        "--live-proof", $liveProofPath,
        "--move-proof", $labProofValidationOut,
        "--json-report", $externalProofPlanJsonOut
    )
    if (-not [string]::IsNullOrWhiteSpace($assessmentIntakePath)) {
        $validateExternalPlanArgs += @("--assessment-intake", $assessmentIntakePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut) -and (Test-Path -LiteralPath $evidenceIntakeOut)) {
        $validateExternalPlanArgs += @("--move-lab-evidence-intake", $evidenceIntakeOut)
    }
    if (-not [string]::IsNullOrWhiteSpace($externalProofPlanReportOut)) {
        $validateExternalPlanArgs += @("--report", $externalProofPlanReportOut)
    }
    Invoke-Nmrcp -Arguments $validateExternalPlanArgs
    $externalProofPlanForPackage = $externalProofPlanJsonOut
}

$packageArgs = @(
    "package-mvp-proof",
    "--mvp-audit", $mvpAuditPath,
    "--live-proof", $liveProofPath,
    "--move-submit-readiness", $submitReadinessOut,
    "--move-lab-proof", $labProofValidationOut,
    "--out", $mvpProofPackageOut
)

if (-not [string]::IsNullOrWhiteSpace($transcriptValidationPath)) {
    $packageArgs += @("--move-lab-transcript", $transcriptValidationPath)
}

if (Test-Path -LiteralPath $gateSummaryOut) {
    $packageArgs += @("--operator-gate-summary", $gateSummaryOut)
}

if (-not [string]::IsNullOrWhiteSpace($MoveLabRunbook)) {
    $runbookPath = Resolve-RequiredPath -PathValue $MoveLabRunbook -Label "MoveLabRunbook"
    $packageArgs += @("--move-lab-runbook", $runbookPath)
}

$closureChecklistPath = Join-Path $assessmentPath "move-lab-closure-checklist.md"
if (Test-Path -LiteralPath $closureChecklistPath) {
    $packageArgs += @("--move-lab-closure-checklist", $closureChecklistPath)
}

$sourceEndpointRequestPath = Join-Path $assessmentPath "source-endpoint-evidence-request.md"
if (Test-Path -LiteralPath $sourceEndpointRequestPath) {
    $packageArgs += @("--source-endpoint-evidence-request", $sourceEndpointRequestPath)
}

if (-not [string]::IsNullOrWhiteSpace($SourceCollectionPlan)) {
    $sourceCollectionPlanPath = Resolve-RequiredPath -PathValue $SourceCollectionPlan -Label "SourceCollectionPlan"
    $packageArgs += @("--source-collection-plan", $sourceCollectionPlanPath)
}

$moveLabRequestPath = Join-Path $assessmentPath "move-lab-evidence-request.md"
if (Test-Path -LiteralPath $moveLabRequestPath) {
    $packageArgs += @("--move-lab-evidence-request", $moveLabRequestPath)
}

if (-not [string]::IsNullOrWhiteSpace($MoveLabCaptureKitDir)) {
    $captureKitPath = Resolve-RequiredPath -PathValue $MoveLabCaptureKitDir -Label "MoveLabCaptureKitDir"
    $packageArgs += @("--move-lab-capture-kit", $captureKitPath)
}

if (-not [string]::IsNullOrWhiteSpace($captureKitValidationPath)) {
    $packageArgs += @("--move-lab-capture-validation", $captureKitValidationPath)
}

if (-not [string]::IsNullOrWhiteSpace($MoveLabReadinessPacket)) {
    $readinessPacketPath = Resolve-RequiredPath -PathValue $MoveLabReadinessPacket -Label "MoveLabReadinessPacket"
    $packageArgs += @("--move-lab-readiness-packet", $readinessPacketPath)
}

if (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut) -and (Test-Path -LiteralPath $evidenceIntakeOut)) {
    $packageArgs += @("--move-lab-evidence-intake", $evidenceIntakeOut)
}

if (-not [string]::IsNullOrWhiteSpace($HandoffPackage)) {
    $handoffPath = Resolve-RequiredPath -PathValue $HandoffPackage -Label "HandoffPackage"
    $packageArgs += @("--handoff-package", $handoffPath)
}

if (-not [string]::IsNullOrWhiteSpace($externalProofPlanForPackage)) {
    $packageArgs += @("--external-proof-plan", $externalProofPlanForPackage)
}

Reset-OutputFile -PathValue $mvpProofPackageOut -Label "MvpProofPackage"
Invoke-Nmrcp -Arguments $packageArgs
Invoke-Nmrcp -Arguments @("verify-mvp-proof", "--package", $mvpProofPackageOut)

if (-not [string]::IsNullOrWhiteSpace($mvpClosureReportOut)) {
    Reset-OutputFile -PathValue $mvpClosureReportOut -Label "MvpClosureReport"
    Reset-OutputFile -PathValue $mvpClosureReportJsonOut -Label "MvpClosureReportJson"
    $closureArgs = @(
        "mvp-closure-report",
        "--package", $mvpProofPackageOut,
        "--out", $mvpClosureReportOut,
        "--json-out", $mvpClosureReportJsonOut
    )
    Invoke-Nmrcp -Arguments $closureArgs
    Invoke-Nmrcp -Arguments @(
        "validate-mvp-closure-report",
        "--package", $mvpProofPackageOut,
        "--report", $mvpClosureReportOut,
        "--json-report", $mvpClosureReportJsonOut
    )
}

if (-not [string]::IsNullOrWhiteSpace($launchReadinessReportOut)) {
    Reset-OutputFile -PathValue $launchReadinessReportOut -Label "LaunchReadinessReport"
    Reset-OutputFile -PathValue $launchReadinessReportJsonOut -Label "LaunchReadinessReportJson"
    $launchArgs = @(
        "launch-readiness-report",
        "--package", $mvpProofPackageOut,
        "--out", $launchReadinessReportOut,
        "--json-out", $launchReadinessReportJsonOut
    )
    if (-not [string]::IsNullOrWhiteSpace($LaunchRepoUrl)) {
        $launchArgs += @("--repo-url", $LaunchRepoUrl)
    }
    if (-not [string]::IsNullOrWhiteSpace($LaunchAudience)) {
        $launchArgs += @("--audience", $LaunchAudience)
    }
    Invoke-Nmrcp -Arguments $launchArgs
    Invoke-Nmrcp -Arguments @(
        "validate-launch-readiness-report",
        "--package", $mvpProofPackageOut,
        "--report", $launchReadinessReportOut,
        "--json-report", $launchReadinessReportJsonOut
    )
}

Write-Host "Move lab proof workflow completed"
Write-Host "Move submit readiness: $submitReadinessOut"
Write-Host "Move lab proof validation: $labProofValidationOut"
if (-not [string]::IsNullOrWhiteSpace($evidenceIntakeOut)) {
    Write-Host "Move lab evidence intake: $evidenceIntakeOut"
}
Write-Host "MVP proof package: $mvpProofPackageOut"
if (-not [string]::IsNullOrWhiteSpace($mvpClosureReportOut)) {
    Write-Host "MVP closure report: $mvpClosureReportOut"
}
if (-not [string]::IsNullOrWhiteSpace($launchReadinessReportOut)) {
    Write-Host "Launch readiness report: $launchReadinessReportOut"
}
if ($isApproved) {
    Write-Host "Approved lab Move proof accepted for final change gate."
} else {
    Write-Host "Simulated proof mode: MVP audit remains partial until approved lab Move appliance proof is supplied."
}
