from pathlib import Path

import unittest


class MoveLabProofWorkflowScriptTests(unittest.TestCase):
    def test_script_keeps_lab_proof_fail_closed(self) -> None:
        script = Path("scripts/move_lab_proof_workflow.ps1").read_text(encoding="utf-8")

        required_controls = [
            "NMRCP_MOVE_LAB_ACK",
            "I_UNDERSTAND_LAB_ONLY",
            "AllowSimulatedProof",
            "approved_lab_move_appliance",
            "validate-move-submit-readiness",
            "GenerateApprovedProof",
            "ApprovedBy",
            "generate-approved-move-lab-proof",
            'Resolve-OutputPath -PathValue $MvpAudit',
            "validate-move-lab-proof",
            "MoveLabTranscriptValidation",
            "--transcript-validation",
            "--move-lab-transcript",
            "package-mvp-proof",
            "verify-mvp-proof",
            "change-gate",
            "package-handoff",
            "verify-handoff",
            "mvp-audit",
            "mvp-closure-report",
            "validate-mvp-closure-report",
            "$MvpClosureReportJson = \"$mvpClosureReportOut.json\"",
            "LaunchReadinessReport",
            "LaunchReadinessReportJson",
            "$LaunchReadinessReportJson = \"$launchReadinessReportOut.json\"",
            "LaunchRepoUrl",
            "LaunchAudience",
            "ExternalProofPlan",
            "ExternalProofPlanReport",
            "ExternalProofPlanJson",
            "external-proof-plan",
            "validate-external-proof-plan",
            "--external-proof-plan",
            "launch-readiness-report",
            "validate-launch-readiness-report",
            "--repo-url",
            "--audience",
            "--json-out",
            "--json-report",
            "MoveLabEvidenceIntake",
            "MoveLabReadinessPacket",
            "--move-lab-readiness-packet",
            "EvidenceBundle",
            "ValidationResults",
            "RemediationTracker",
            "Signoffs",
            "ApprovalExceptions",
            "OperatorReview",
            "WarningAcceptance",
            "AssessmentIntake",
            "--assessment-intake",
            "SourceCollectionPlan",
            "--source-collection-plan",
            "MvpClosureReport",
            "Reset-OutputFile",
            "Unable to reset output",
            "Remove-Item -LiteralPath",
        ]

        for control in required_controls:
            with self.subTest(control=control):
                self.assertIn(control, script)


if __name__ == "__main__":
    unittest.main()
