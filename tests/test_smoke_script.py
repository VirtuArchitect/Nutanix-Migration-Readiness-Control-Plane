import unittest
from pathlib import Path


class SmokeScriptTests(unittest.TestCase):
    def test_smoke_script_fails_fast_on_native_command_errors(self) -> None:
        script = Path("scripts/smoke.ps1").read_text(encoding="utf-8")

        self.assertIn('$ErrorActionPreference = "Stop"', script)
        self.assertIn("function Invoke-CheckedNative", script)
        self.assertIn("if ($LASTEXITCODE -ne 0)", script)
        self.assertIn("function python", script)
        self.assertIn("function powershell", script)
        self.assertIn("Native command failed with exit code", script)

    def test_smoke_script_revalidates_reviewer_reports_after_late_workflow_steps(self) -> None:
        script = Path("scripts/smoke.ps1").read_text(encoding="utf-8")

        final_workflow = script.rfind("python -m nmrcp.cli run-assessment")
        final_closure_validation = script.rfind("validate-mvp-closure-report")
        final_launch_validation = script.rfind("validate-launch-readiness-report")

        self.assertGreater(final_closure_validation, final_workflow)
        self.assertGreater(final_launch_validation, final_workflow)

    def test_smoke_script_packages_external_proof_plans(self) -> None:
        script = Path("scripts/smoke.ps1").read_text(encoding="utf-8")

        for expected in (
            "$externalProofPlanJson",
            "$generatedExternalProofPlanJson",
            "external-proof-plan.generated-proof-rehearsal.json",
            "validate-external-proof-plan",
            "-ExternalProofPlanJson $generatedExternalProofPlanJson",
            "--external-proof-plan $externalProofPlanJson",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, script)

    def test_smoke_script_validates_product_readiness_with_proof_package(self) -> None:
        script = Path("scripts/smoke.ps1").read_text(encoding="utf-8")

        for expected in (
            "$productReadinessReport",
            "$productReadinessReportJson",
            "$publicationStagingManifest",
            "$publicationStagingManifestJson",
            "publication-staging-manifest --repo-root $repoRoot",
            "validate-publication-staging-manifest --repo-root $repoRoot",
            "product-readiness --repo-root $repoRoot --mvp-proof-package $mvpProofPackage --publication-staging-manifest $publicationStagingManifest --publication-staging-manifest-json $publicationStagingManifestJson",
            "$LASTEXITCODE -notin @(0, 1)",
            "validate-product-readiness-report --repo-root $repoRoot --mvp-proof-package $mvpProofPackage --publication-staging-manifest $publicationStagingManifest --publication-staging-manifest-json $publicationStagingManifestJson",
            "smoke-publication-staging-manifest.md",
            "smoke-publication-staging-manifest.json",
            "smoke-product-readiness-report.md",
            "smoke-product-readiness-report.json",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, script)


if __name__ == "__main__":
    unittest.main()
