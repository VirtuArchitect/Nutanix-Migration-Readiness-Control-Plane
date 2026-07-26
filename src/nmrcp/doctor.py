from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dependencies import apply_dependency_readiness_gates, merge_dependencies, read_dependency_csv
from .evidence import write_assessment
from .inventory_validation import validate_inventory
from .move_plan import validate_move_plan
from .move_payload import build_move_payload
from .redaction import redact_dict
from .scoring import assess_inventory
from .waves import plan_waves


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def run_doctor(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    checks: list[DoctorCheck] = []
    checks.append(
        DoctorCheck(
            "python",
            "pass" if sys.version_info >= (3, 11) else "fail",
            f"{platform.python_version()} at {sys.executable}",
        )
    )
    checks.append(file_check(root / "examples" / "sample_inventory.json"))
    checks.append(file_check(root / "examples" / "sample_dependencies.csv"))
    checks.append(file_check(root / "examples" / "sample_move_payload_config.json"))
    checks.extend(project_metadata_checks(root))
    checks.extend(gitignore_checks(root))
    checks.extend(endpoint_env_checks())
    checks.extend(sample_pipeline_checks(root))

    status = "pass" if all(check.status != "fail" for check in checks) else "fail"
    return {
        "status": status,
        "checks": [check.to_dict() for check in checks],
    }


def file_check(path: Path) -> DoctorCheck:
    return DoctorCheck(
        f"file:{path.name}",
        "pass" if path.exists() else "fail",
        "present" if path.exists() else f"missing: {path}",
    )


def project_metadata_checks(root: Path) -> list[DoctorCheck]:
    path = root / "pyproject.toml"
    if not path.exists():
        return [DoctorCheck("packaging:pyproject", "fail", f"missing: {path}")]
    try:
        pyproject = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [DoctorCheck("packaging:pyproject", "fail", f"unreadable: {exc}")]

    scripts = pyproject.get("project", {}).get("scripts", {})
    entrypoint = scripts.get("nmrcp") if isinstance(scripts, dict) else None
    package_dir = pyproject.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    return [
        DoctorCheck(
            "packaging:nmrcp-console-script",
            "pass" if entrypoint == "nmrcp.cli:main" else "fail",
            f"nmrcp={entrypoint or 'missing'}",
        ),
        DoctorCheck(
            "packaging:src-layout",
            "pass" if isinstance(package_dir, dict) and package_dir.get("") == "src" else "fail",
            f"package-dir={package_dir.get('') if isinstance(package_dir, dict) else 'missing'}",
        ),
    ]


def gitignore_checks(root: Path) -> list[DoctorCheck]:
    path = root / ".gitignore"
    if not path.exists():
        return [DoctorCheck("workspace:gitignore", "fail", f"missing: {path}")]
    try:
        entries = set(path.read_text(encoding="utf-8").splitlines())
    except OSError as exc:
        return [DoctorCheck("workspace:gitignore", "fail", f"unreadable: {exc}")]

    required = ("outputs/", "*.egg-info/", "build/", "dist/", ".env")
    missing = [entry for entry in required if entry not in entries]
    return [
        DoctorCheck(
            "workspace:generated-artifact-ignore",
            "pass" if not missing else "fail",
            "required generated artifacts ignored" if not missing else f"missing ignore entries: {', '.join(missing)}",
        )
    ]


def endpoint_env_checks() -> list[DoctorCheck]:
    checks = []
    for prefix, label in (("NMRCP_VCENTER", "vCenter"), ("NMRCP_PRISM", "Prism Central")):
        url = os.getenv(f"{prefix}_URL")
        username = os.getenv(f"{prefix}_USERNAME")
        password = os.getenv(f"{prefix}_PASSWORD")
        present = [name for name, value in (("URL", url), ("USERNAME", username), ("PASSWORD", password)) if value]
        missing = [name for name, value in (("URL", url), ("USERNAME", username), ("PASSWORD", password)) if not value]
        status = "pass" if len(present) == 3 else "warn"
        detail = f"{label} env present: {', '.join(present) if present else 'none'}"
        if missing:
            detail += f"; missing: {', '.join(missing)}"
        checks.append(DoctorCheck(f"env:{prefix}", status, detail))
    return checks


def sample_pipeline_checks(root: Path) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            inventory = json.loads((root / "examples" / "sample_inventory.json").read_text(encoding="utf-8"))
            dependencies = read_dependency_csv(root / "examples" / "sample_dependencies.csv")
            inventory = merge_dependencies(inventory, dependencies)
            inventory_validation = validate_inventory(inventory)
            checks.append(
                DoctorCheck(
                    "sample:inventory-validation",
                    "pass" if inventory_validation.ok else "fail",
                    inventory_validation.summary(),
                )
            )
            assessments = apply_dependency_readiness_gates(inventory, assess_inventory(inventory))
            waves = plan_waves(assessments, inventory)
            write_assessment(inventory, assessments, waves, out_dir)
            checks.append(artifact_check(out_dir / "assessment.json"))
            checks.append(artifact_check(out_dir / "dependency-sequence.csv"))
            checks.append(artifact_check(out_dir / "nutanix-move-plan.csv"))
            validation = validate_move_plan(out_dir / "nutanix-move-plan.csv")
            checks.append(
                DoctorCheck(
                    "sample:move-plan-validation",
                    "pass" if validation.ok else "fail",
                    validation.summary(),
                )
            )
            payload = build_move_payload(
                out_dir / "nutanix-move-plan.csv",
                root / "examples" / "sample_move_payload_config.json",
            )
            checks.append(
                DoctorCheck(
                    "sample:dry-run-payload",
                    "pass" if payload.get("dry_run_only") and payload.get("mutation_allowed") is False else "fail",
                    f"workloads={len(payload.get('workloads', []))}",
                )
            )
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))
            redacted_source = redact_dict(assessment.get("source", {}))
            checks.append(
                DoctorCheck(
                    "sample:redaction",
                    "pass" if "[REDACTED" in json.dumps(redacted_source) else "warn",
                    "sample source metadata redacted",
                )
            )
    except Exception as exc:
        checks.append(DoctorCheck("sample:pipeline", "fail", str(exc)))
    return checks


def artifact_check(path: Path) -> DoctorCheck:
    return DoctorCheck(
        f"artifact:{path.name}",
        "pass" if path.exists() and path.stat().st_size > 0 else "fail",
        "generated" if path.exists() and path.stat().st_size > 0 else "missing or empty",
    )
