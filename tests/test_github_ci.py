import unittest
from pathlib import Path


class GitHubCiTests(unittest.TestCase):
    def test_ci_covers_mvp_proof_and_move_lab_evidence(self):
        workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

        for expected in (
            "github-readiness --repo-root . --expected-remote https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane",
            "validate-github-publication-review",
            "outputs/ci-github-publication-review.md",
            "outputs/ci-github-publication-review.json",
            "validate-live-proof",
            "generate-assessment-intake",
            "validate-assessment-intake",
            "source-collection-plan",
            "validate-source-collection-plan",
            "validate-collection-proof-report",
            "validate-move-plan-brief",
            "import-cmdb-metadata",
            "validate-operator-portal",
            "validate-partner-handoff",
            "validate-prism-categories",
            "validate-stakeholder-comms",
            "validate-what-will-break",
            "validate-wave-execution-calendar",
            "generate-move-lab-capture-kit",
            "move-lab-evidence-preflight",
            "move-lab-readiness-packet",
            "validate-move-lab-readiness-packet",
            "validate-move-submit-readiness",
            "validate-move-lab-transcript",
            "generate-approved-move-lab-proof",
            "validate-move-lab-proof",
            "validate-move-lab-evidence-intake",
            "validate-move-lab-evidence-request",
            "validate-source-endpoint-evidence-request",
            "validate-operator-gate-summary",
            "validate-warning-acceptance",
            "external-proof-plan",
            "validate-external-proof-plan",
            "outputs/ci-external-proof-plan.json",
            "package-mvp-proof",
            "verify-mvp-proof",
            "summarize-mvp-proof",
            "validate-mvp-proof-summary",
            "mvp-closure-report",
            "validate-mvp-closure-report",
            "launch-readiness-report",
            "validate-launch-readiness-report",
            '"external_handoff_decision": "blocked_for_external_handoff"',
            "External handoff decision: `blocked_for_external_handoff`",
            "outputs/ci-handoff-package.zip",
            "outputs/ci-smoke/move-lab-proof.generated-approved.json",
            "outputs/ci-smoke/move-lab-evidence-intake.generated-proof-rehearsal.json",
            "outputs/ci-smoke/move-lab-readiness-packet.json",
            "outputs/ci-smoke/move-lab-readiness-packet.md",
            "outputs/live-collector-smoke/collection-proof-report.md",
        ):
            self.assertIn(expected, workflow)

        package_command = next(line for line in workflow.splitlines() if "package-mvp-proof --mvp-audit outputs/ci-mvp-audit.json" in line)
        for expected_flag in (
            "--move-lab-runbook outputs/ci-smoke/move-lab-execution-runbook.md",
            "--move-lab-closure-checklist outputs/ci-smoke/move-lab-closure-checklist.md",
            "--move-lab-readiness-packet outputs/ci-smoke/move-lab-readiness-packet.json",
            "--source-collection-plan outputs/ci-source-collection-plan.md",
            "--source-endpoint-evidence-request outputs/ci-smoke/source-endpoint-evidence-request.md",
            "--move-lab-evidence-request outputs/ci-smoke/move-lab-evidence-request.md",
            "--operator-gate-summary outputs/ci-smoke/operator-gate-summary.md",
            "--handoff-package outputs/ci-handoff-package.zip",
            "--external-proof-plan outputs/ci-external-proof-plan.json",
        ):
            self.assertIn(expected_flag, package_command)

        handoff_command = next(line for line in workflow.splitlines() if "package-handoff --dir outputs/ci-smoke" in line)
        self.assertIn("--move-lab-readiness-packet outputs/ci-smoke/move-lab-readiness-packet.json", handoff_command)
        self.assertIn("--source-collection-plan outputs/ci-source-collection-plan.md", handoff_command)


if __name__ == "__main__":
    unittest.main()
