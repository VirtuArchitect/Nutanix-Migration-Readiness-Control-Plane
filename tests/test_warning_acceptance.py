import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.warning_acceptance import (
    WARNING_ACCEPTANCE_SCHEMA_VERSION,
    validate_warning_acceptance,
)


class WarningAcceptanceTests(unittest.TestCase):
    def test_accepts_all_expected_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            acceptance = Path(tmp) / "acceptance.csv"
            write_acceptance(acceptance, ("warning one", "warning two"))

            result = validate_warning_acceptance(acceptance, ("warning one", "warning two"))

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.accepted_count, 2)
            self.assertEqual(result.accepted_warnings, ("warning one", "warning two"))

    def test_rejects_missing_expected_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            acceptance = Path(tmp) / "acceptance.csv"
            write_acceptance(acceptance, ("warning one",))

            result = validate_warning_acceptance(acceptance, ("warning one", "warning two"))

            self.assertFalse(result.ok)
            self.assertIn("Missing accepted warning: warning two", result.errors)

    def test_rejects_unexpected_extra_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            acceptance = Path(tmp) / "acceptance.csv"
            write_acceptance(acceptance, ("warning one", "warning extra"))

            result = validate_warning_acceptance(acceptance, ("warning one",))

            self.assertFalse(result.ok)
            self.assertIn("Unexpected accepted warning: warning extra", result.errors)

    def test_cli_validates_warnings_from_change_gate_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acceptance = root / "acceptance.csv"
            warnings = root / "change-gate.json"
            warnings.write_text(json.dumps({"warnings": ["warning one", "warning two"]}), encoding="utf-8")
            write_acceptance(acceptance, ("warning one", "warning two"))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-warning-acceptance",
                        "--acceptance",
                        str(acceptance),
                        "--warnings",
                        str(warnings),
                    ]
                )

            self.assertEqual(code, 0)


def write_acceptance(path: Path, warnings: tuple[str, ...]) -> None:
    rows = [
        {
            "schema_version": WARNING_ACCEPTANCE_SCHEMA_VERSION,
            "warning_text": warning,
            "acceptance_status": "accepted",
            "acceptance_ref": f"CHG-2026-WARN-{index:03d}",
            "accepted_by": "Migration Lead",
            "accepted_at": "2026-07-25T00:00:00Z",
            "notes": "Accepted for reviewed lab closure evidence.",
        }
        for index, warning in enumerate(warnings, start=1)
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
