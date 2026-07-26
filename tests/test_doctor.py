import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.doctor import run_doctor


class DoctorTests(unittest.TestCase):
    def test_doctor_passes_sample_pipeline_with_missing_endpoint_warnings(self):
        with patch.dict("os.environ", {}, clear=True):
            result = run_doctor()

        self.assertEqual(result["status"], "pass")
        env_checks = [check for check in result["checks"] if check["name"].startswith("env:")]
        self.assertEqual({check["status"] for check in env_checks}, {"warn"})
        self.assertIn(
            {"name": "packaging:nmrcp-console-script", "status": "pass", "detail": "nmrcp=nmrcp.cli:main"},
            result["checks"],
        )
        self.assertTrue(any(check["name"] == "workspace:generated-artifact-ignore" and check["status"] == "pass" for check in result["checks"]))
        self.assertTrue(any(check["name"] == "sample:move-plan-validation" for check in result["checks"]))

    def test_doctor_json_does_not_print_secret_values(self):
        stream = io.StringIO()
        with patch.dict(
            "os.environ",
            {
                "NMRCP_VCENTER_URL": "https://vcenter.example.test",
                "NMRCP_VCENTER_USERNAME": "admin@example.test",
                "NMRCP_VCENTER_PASSWORD": "super-secret-value",
            },
            clear=True,
        ), redirect_stdout(stream):
            code = main(["doctor", "--json"])

        output = stream.getvalue()
        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "pass")
        self.assertNotIn("super-secret-value", output)
        self.assertNotIn("admin@example.test", output)

    def test_doctor_fails_on_missing_console_script_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_minimal_repo(Path(tmp))
            pyproject = root / "pyproject.toml"
            pyproject.write_text(pyproject.read_text(encoding="utf-8").replace('nmrcp = "nmrcp.cli:main"', ""), encoding="utf-8")

            result = run_doctor(root)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any(check["name"] == "packaging:nmrcp-console-script" and check["status"] == "fail" for check in result["checks"]))

    def test_doctor_fails_when_generated_artifacts_are_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_minimal_repo(Path(tmp))
            gitignore = root / ".gitignore"
            gitignore.write_text(gitignore.read_text(encoding="utf-8").replace("*.egg-info/\n", ""), encoding="utf-8")

            result = run_doctor(root)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any(check["name"] == "workspace:generated-artifact-ignore" and "*.egg-info/" in check["detail"] for check in result["checks"]))


def copy_minimal_repo(root: Path) -> Path:
    source = Path.cwd()
    shutil.copy(source / "pyproject.toml", root / "pyproject.toml")
    shutil.copy(source / ".gitignore", root / ".gitignore")
    examples = root / "examples"
    examples.mkdir()
    for name in ("sample_inventory.json", "sample_dependencies.csv", "sample_move_payload_config.json"):
        shutil.copy(source / "examples" / name, examples / name)
    return root


if __name__ == "__main__":
    unittest.main()
