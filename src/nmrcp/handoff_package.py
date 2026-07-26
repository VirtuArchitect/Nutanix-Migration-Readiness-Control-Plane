from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .approval_exceptions import validate_approval_exception_approvals
from .evidence import sha256_file
from .evidence_bundle import load_manifest, verify_evidence, verify_evidence_bundle
from .move_lab_closure_checklist import validate_move_lab_closure_checklist
from .move_lab_evidence_intake import validate_move_lab_evidence_intake_validation_file
from .move_lab_evidence_request import validate_move_lab_evidence_request
from .move_lab_proof import validate_move_lab_proof_validation_file
from .move_lab_readiness_packet import validate_move_lab_readiness_packet
from .move_plan import validate_move_plan
from .operator_review import validate_operator_review
from .remediation import validate_remediation_tracker
from .signoff import validate_signoffs
from .source_collection_plan import validate_source_collection_plan_text
from .source_endpoint_evidence_request import validate_source_endpoint_evidence_request
from .validation_results import validate_validation_results


HANDOFF_SCHEMA_VERSION = "nmrcp_handoff_manifest_v1"
ALLOWED_HANDOFF_ROLES = {
    "assessment_manifest",
    "assessment_artifact",
    "evidence_bundle",
    "validation_results",
    "remediation_tracker",
    "owner_signoffs",
    "approval_exceptions",
    "operator_review",
    "move_lab_proof",
    "move_lab_readiness_packet",
    "move_lab_evidence_intake",
    "move_lab_capture_template",
    "move_lab_capture_checklist",
    "move_lab_capture_validation",
    "move_dry_run_payload",
    "source_collection_plan",
}
REQUIRED_HANDOFF_ROLES = {"assessment_manifest", "assessment_artifact"}
UNIQUE_HANDOFF_ROLES = ALLOWED_HANDOFF_ROLES.difference({"assessment_artifact"})
REQUIRED_ASSESSMENT_ARTIFACTS = {
    "assessment/assessment.json",
    "assessment/evidence-manifest.json",
    "assessment/move-lab-closure-checklist.md",
    "assessment/move-lab-evidence-request.md",
    "assessment/nutanix-move-plan.csv",
    "assessment/pre-post-validation-checklist.md",
    "assessment/source-endpoint-evidence-request.md",
}


@dataclass(frozen=True)
class HandoffVerification:
    checked: int
    roles: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checked={self.checked}, roles={len(self.roles)}, errors={len(self.errors)}"


def package_handoff(
    assessment_dir: Path,
    package_path: Path,
    bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    move_payload_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_readiness_packet_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    move_lab_capture_kit_dir: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    source_collection_plan_path: Path | None = None,
) -> Path:
    assessment_result = verify_evidence(assessment_dir)
    if not assessment_result.ok:
        raise ValueError("Assessment evidence verification failed: " + "; ".join(assessment_result.errors))

    move_plan_result = validate_move_plan(
        assessment_dir / "nutanix-move-plan.csv",
        assessment_dir / "assessment.json",
    )
    if not move_plan_result.ok:
        raise ValueError("Move plan validation failed: " + "; ".join(move_plan_result.errors))

    entries: list[dict[str, Any]] = []
    manifest = load_manifest(assessment_dir / "evidence-manifest.json")
    entries.append(file_entry(assessment_dir / "evidence-manifest.json", "assessment/evidence-manifest.json", "assessment_manifest"))
    for artifact in manifest["artifacts"]:
        name = str(artifact["name"])
        entries.append(file_entry(assessment_dir / name, f"assessment/{name}", "assessment_artifact"))

    if bundle_path:
        bundle_result = verify_evidence_bundle(bundle_path)
        if not bundle_result.ok:
            raise ValueError("Evidence bundle verification failed: " + "; ".join(bundle_result.errors))
        entries.append(file_entry(bundle_path, "bundles/evidence-bundle.zip", "evidence_bundle"))

    if validation_results_path:
        validation = validate_validation_results(validation_results_path)
        if not validation.ok:
            raise ValueError("Validation results failed: " + "; ".join(validation.errors))
        entries.append(file_entry(validation_results_path, "validation/validation-results.csv", "validation_results"))

    if remediation_tracker_path:
        remediation = validate_remediation_tracker(remediation_tracker_path)
        if not remediation.ok:
            raise ValueError("Remediation tracker validation failed: " + "; ".join(remediation.errors))
        entries.append(file_entry(remediation_tracker_path, "remediation/final-remediation-tracker.csv", "remediation_tracker"))

    if signoffs_path:
        signoffs = validate_signoffs(signoffs_path)
        if not signoffs.ok:
            raise ValueError("Sign-off validation failed: " + "; ".join(signoffs.errors))
        entries.append(file_entry(signoffs_path, "signoffs/final-owner-signoffs.csv", "owner_signoffs"))

    if approval_exceptions_path:
        approvals = validate_approval_exception_approvals(approval_exceptions_path, assessment_path=assessment_dir / "assessment.json")
        if not approvals.ok:
            raise ValueError("Approval exception validation failed: " + "; ".join(approvals.errors))
        entries.append(file_entry(approval_exceptions_path, "signoffs/final-approval-exceptions.csv", "approval_exceptions"))

    if operator_review_path:
        operator_review = validate_operator_review(operator_review_path, assessment_dir=assessment_dir)
        if not operator_review.ok:
            raise ValueError("Operator review validation failed: " + "; ".join(operator_review.errors))
        entries.append(file_entry(operator_review_path, "review/operator-review.csv", "operator_review"))

    if move_lab_proof_path:
        if not move_lab_evidence_intake_path:
            raise ValueError("Approved Move lab proof handoff requires Move lab evidence intake")
        move_lab_proof = validate_move_lab_proof_validation_file(move_lab_proof_path, require_approved_lab=True)
        if not move_lab_proof.ok:
            raise ValueError("Move lab proof validation failed: " + "; ".join(move_lab_proof.errors))
        entries.append(file_entry(move_lab_proof_path, "move/move-lab-proof-validation.json", "move_lab_proof"))

    if move_lab_evidence_intake_path:
        evidence_intake = validate_move_lab_evidence_intake_validation_file(move_lab_evidence_intake_path)
        if not evidence_intake.ok or evidence_intake.status != "pass":
            raise ValueError("Move lab evidence intake validation failed: " + "; ".join(evidence_intake.errors))
        entries.append(file_entry(move_lab_evidence_intake_path, "move/move-lab-evidence-intake.json", "move_lab_evidence_intake"))

    if move_lab_readiness_packet_path:
        readiness_packet = validate_move_lab_readiness_packet(move_lab_readiness_packet_path)
        if not readiness_packet.ok:
            raise ValueError("Move lab readiness packet validation failed: " + "; ".join(readiness_packet.errors))
        entries.append(file_entry(move_lab_readiness_packet_path, "move/move-lab-readiness-packet.json", "move_lab_readiness_packet"))

    if source_collection_plan_path:
        plan_validation = validate_source_collection_plan_text(source_collection_plan_path.read_text(encoding="utf-8"))
        if not plan_validation.ok:
            raise ValueError("Source collection plan validation failed: " + "; ".join(plan_validation.errors))
        entries.append(file_entry(source_collection_plan_path, "source/source-collection-plan.md", "source_collection_plan"))

    if bool(move_lab_capture_kit_dir) != bool(move_lab_capture_validation_path):
        raise ValueError("Move lab capture kit and validation proof must be packaged together")

    if move_lab_capture_kit_dir and move_lab_capture_validation_path:
        capture_entries = capture_kit_entries(move_lab_capture_kit_dir)
        capture_entries.append(
            file_entry(
                move_lab_capture_validation_path,
                "move/move-lab-capture-kit-validation.json",
                "move_lab_capture_validation",
            )
        )
        capture_errors: list[str] = []
        for entry in capture_entries:
            validate_handoff_role(
                str(entry["role"]),
                str(entry["path"]),
                Path(str(entry["source_path"])).read_bytes(),
                capture_errors,
            )
        if capture_errors:
            raise ValueError("Move lab capture kit validation failed: " + "; ".join(capture_errors))
        entries.extend(capture_entries)

    if move_payload_path:
        entries.append(file_entry(move_payload_path, "move/move-api-payload.dry-run.json", "move_dry_run_payload"))

    handoff_manifest = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "assessment_dir": assessment_dir.name,
        "files": [archive_manifest_entry(entry) for entry in entries],
    }

    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("handoff-manifest.json", json.dumps(handoff_manifest, indent=2).encode("utf-8"))
        for entry in entries:
            archive.write(str(entry["source_path"]), arcname=str(entry["path"]))
    return package_path


def verify_handoff_package(package_path: Path) -> HandoffVerification:
    errors: list[str] = []
    checked = 0
    with zipfile.ZipFile(package_path, "r") as archive:
        names = set(archive.namelist())
        if "handoff-manifest.json" not in names:
            return HandoffVerification(0, (), ("package missing handoff-manifest.json",))
        manifest = json.loads(archive.read("handoff-manifest.json").decode("utf-8"))
        if manifest.get("schema_version") != HANDOFF_SCHEMA_VERSION:
            return HandoffVerification(0, (), ("unsupported handoff manifest schema",))
        files = manifest.get("files")
        if not isinstance(files, list):
            return HandoffVerification(0, (), ("handoff manifest must contain a files list",))
        roles_seen: list[str] = []
        paths_seen: set[str] = set()
        for entry in files:
            checked += 1
            if not isinstance(entry, dict):
                errors.append("handoff manifest file entry must be an object")
                continue
            role = str(entry.get("role") or "")
            path = str(entry.get("path") or "")
            if not role:
                errors.append(f"{path or 'unknown'}: missing manifest role")
            elif role not in ALLOWED_HANDOFF_ROLES:
                errors.append(f"{path or role}: unsupported manifest role {role}")
            elif role in UNIQUE_HANDOFF_ROLES and role in roles_seen:
                errors.append(f"{path}: duplicate manifest role {role}")
            else:
                roles_seen.append(role)
            if not path:
                errors.append(f"{role or 'unknown'}: missing manifest archive path")
                continue
            if path in paths_seen:
                errors.append(f"{path}: duplicate manifest archive path")
            paths_seen.add(path)
            if path not in names:
                errors.append(f"{path}: missing from handoff package")
                continue
            data = archive.read(path)
            try:
                expected_size = int(entry.get("size_bytes", -1))
            except (TypeError, ValueError):
                expected_size = -1
            if len(data) != expected_size:
                errors.append(f"{path}: size mismatch expected={entry.get('size_bytes', 'missing')} actual={len(data)}")
            digest = hashlib.sha256(data).hexdigest()
            if digest != entry.get("sha256"):
                errors.append(f"{path}: sha256 mismatch")
            validate_handoff_role(role, path, data, errors)
        for role in sorted(REQUIRED_HANDOFF_ROLES.difference(roles_seen)):
            errors.append(f"missing required handoff role: {role}")
        for path in sorted(REQUIRED_ASSESSMENT_ARTIFACTS.difference(paths_seen)):
            errors.append(f"missing required assessment artifact: {path}")
        for path in sorted(names.difference(paths_seen).difference({"handoff-manifest.json"})):
            errors.append(f"{path}: archive entry is not listed in handoff manifest")
        capture_roles = {
            "move_lab_capture_template",
            "move_lab_capture_checklist",
            "move_lab_capture_validation",
        }.intersection(roles_seen)
        if capture_roles and capture_roles != {
            "move_lab_capture_template",
            "move_lab_capture_checklist",
            "move_lab_capture_validation",
        }:
            missing_capture_roles = sorted(
                {
                    "move_lab_capture_template",
                    "move_lab_capture_checklist",
                    "move_lab_capture_validation",
                }.difference(roles_seen)
            )
            errors.append(f"Move lab capture kit and validation proof must be packaged together; missing {', '.join(missing_capture_roles)}")
        if "move_lab_proof" in roles_seen and "move_lab_evidence_intake" not in roles_seen:
            errors.append("Approved Move lab proof handoff requires Move lab evidence intake")
    return HandoffVerification(checked=checked, roles=tuple(roles_seen), errors=tuple(errors))


def validate_handoff_role(role: str, path: str, data: bytes, errors: list[str]) -> None:
    if role == "assessment_manifest":
        payload = read_role_json(path, data, errors)
        if payload and payload.get("schema_version") != "nmrcp_evidence_manifest_v1":
            errors.append(f"{path}: assessment_manifest schema_version must be nmrcp_evidence_manifest_v1")
    elif role == "assessment_artifact":
        validate_assessment_artifact(path, data, errors)
    elif role == "evidence_bundle":
        validate_nested_evidence_bundle(path, data, errors)
    elif role in {"validation_results", "remediation_tracker", "owner_signoffs", "approval_exceptions", "operator_review"}:
        validate_nonempty_csv(path, data, errors)
    elif role == "move_lab_proof":
        validate_packaged_move_lab_proof(path, data, errors)
    elif role == "move_lab_readiness_packet":
        validate_packaged_move_lab_readiness_packet(path, data, errors)
    elif role == "move_lab_evidence_intake":
        validate_packaged_move_lab_evidence_intake(path, data, errors)
    elif role == "move_lab_capture_template":
        payload = read_role_json(path, data, errors)
        if not payload:
            return
        if payload.get("schema_version") != "nmrcp_move_lab_transcript_v1":
            errors.append(f"{path}: move_lab_capture_template schema_version must be nmrcp_move_lab_transcript_v1")
        if payload.get("evidence_state") != "template_only_replace_after_lab_capture":
            errors.append(f"{path}: move_lab_capture_template must remain template_only_replace_after_lab_capture")
        if payload.get("production_targets") is not False:
            errors.append(f"{path}: move_lab_capture_template must set production_targets=false")
        if payload.get("mutation_performed") is not False:
            errors.append(f"{path}: move_lab_capture_template must set mutation_performed=false")
    elif role == "move_lab_capture_checklist":
        text = read_role_text(path, data, errors)
        if text and "# Move Lab Capture Checklist" not in text:
            errors.append(f"{path}: move_lab_capture_checklist must contain Move Lab Capture Checklist heading")
    elif role == "move_lab_capture_validation":
        payload = read_role_json(path, data, errors)
        if not payload:
            return
        if payload.get("schema_version") != "nmrcp_move_lab_capture_kit_validation_v1":
            errors.append(f"{path}: move_lab_capture_validation schema_version must be nmrcp_move_lab_capture_kit_validation_v1")
        if payload.get("status") != "pass":
            errors.append(f"{path}: move_lab_capture_validation status must be pass")
        payload_errors = payload.get("errors")
        if isinstance(payload_errors, list) and payload_errors:
            errors.append(f"{path}: move_lab_capture_validation errors must be empty")
    elif role == "move_dry_run_payload":
        payload = read_role_json(path, data, errors)
        if not payload:
            return
        if payload.get("contract") != "nmrcp_move_api_payload_dry_run_v1":
            errors.append(f"{path}: move payload contract must be nmrcp_move_api_payload_dry_run_v1")
        if payload.get("dry_run_only") is not True:
            errors.append(f"{path}: move payload dry_run_only must be true")
        if payload.get("mutation_allowed") is not False:
            errors.append(f"{path}: move payload mutation_allowed must be false")
    elif role == "source_collection_plan":
        text = read_role_text(path, data, errors)
        result = validate_source_collection_plan_text(text)
        errors.extend(f"{path}: {error}" for error in result.errors)


def validate_assessment_artifact(path: str, data: bytes, errors: list[str]) -> None:
    if path == "assessment/assessment.json":
        payload = read_role_json(path, data, errors)
        if payload and not isinstance(payload.get("assessments"), list):
            errors.append(f"{path}: assessment.json must contain an assessments list")
    elif path == "assessment/nutanix-move-plan.csv":
        header = csv_header(path, data, errors)
        required = {"source_vm_id", "include_in_move_plan"}
        missing = sorted(required.difference(header))
        if missing:
            errors.append(f"{path}: move plan missing required columns {', '.join(missing)}")
    elif path == "assessment/pre-post-validation-checklist.md":
        text = read_role_text(path, data, errors)
        if text and "Validation Checklist" not in text:
            errors.append(f"{path}: validation checklist heading missing")
    elif path == "assessment/move-lab-closure-checklist.md":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                checklist_path = Path(tmp) / "move-lab-closure-checklist.md"
                checklist_path.write_text(text, encoding="utf-8")
                result = validate_move_lab_closure_checklist(checklist_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif path == "assessment/move-lab-evidence-request.md":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                request_path = Path(tmp) / "move-lab-evidence-request.md"
                request_path.write_text(text, encoding="utf-8")
                result = validate_move_lab_evidence_request(request_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif path == "assessment/source-endpoint-evidence-request.md":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                request_path = Path(tmp) / "source-endpoint-evidence-request.md"
                request_path.write_text(text, encoding="utf-8")
                result = validate_source_endpoint_evidence_request(request_path)
            errors.extend(f"{path}: {error}" for error in result.errors)


def validate_packaged_move_lab_proof(path: str, data: bytes, errors: list[str]) -> None:
    import tempfile

    payload = read_role_json(path, data, errors)
    if not payload:
        return
    with tempfile.TemporaryDirectory() as tmp:
        proof_path = Path(tmp) / "move-lab-proof-validation.json"
        proof_path.write_bytes(data)
        from .move_lab_proof import validate_move_lab_proof_validation_file

        result = validate_move_lab_proof_validation_file(proof_path, require_approved_lab=True)
    errors.extend(f"{path}: {error}" for error in result.errors)


def validate_packaged_move_lab_evidence_intake(path: str, data: bytes, errors: list[str]) -> None:
    import tempfile

    payload = read_role_json(path, data, errors)
    if not payload:
        return
    with tempfile.TemporaryDirectory() as tmp:
        intake_path = Path(tmp) / "move-lab-evidence-intake.json"
        intake_path.write_bytes(data)
        result = validate_move_lab_evidence_intake_validation_file(intake_path)
    errors.extend(f"{path}: {error}" for error in result.errors)


def validate_packaged_move_lab_readiness_packet(path: str, data: bytes, errors: list[str]) -> None:
    import tempfile

    payload = read_role_json(path, data, errors)
    if not payload:
        return
    with tempfile.TemporaryDirectory() as tmp:
        packet_path = Path(tmp) / "move-lab-readiness-packet.json"
        packet_path.write_bytes(data)
        result = validate_move_lab_readiness_packet(packet_path)
    errors.extend(f"{path}: {error}" for error in result.errors)


def validate_nested_evidence_bundle(path: str, data: bytes, errors: list[str]) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as nested:
            names = set(nested.namelist())
            if "evidence-manifest.json" not in names:
                errors.append(f"{path}: nested evidence bundle missing evidence-manifest.json")
            if not names:
                errors.append(f"{path}: nested evidence bundle is empty")
    except zipfile.BadZipFile:
        errors.append(f"{path}: evidence_bundle must be a valid zip")


def validate_nonempty_csv(path: str, data: bytes, errors: list[str]) -> None:
    header = csv_header(path, data, errors)
    if not header:
        errors.append(f"{path}: CSV header must not be empty")


def csv_header(path: str, data: bytes, errors: list[str]) -> set[str]:
    text = read_role_text(path, data, errors)
    if not text:
        return set()
    try:
        reader = csv.reader(io.StringIO(text))
        return {column.strip() for column in next(reader, []) if column.strip()}
    except csv.Error as exc:
        errors.append(f"{path}: CSV is unreadable: {exc}")
        return set()


def read_role_json(path: str, data: bytes, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: packaged JSON is unreadable: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: packaged JSON must be an object")
        return {}
    return payload


def read_role_text(path: str, data: bytes, errors: list[str]) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{path}: packaged text is not UTF-8: {exc}")
        return ""
    if not text.strip():
        errors.append(f"{path}: packaged text must not be empty")
    return text


def move_lab_scope(payload: dict[str, Any]) -> str:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    for check in checks:
        if isinstance(check, dict) and check.get("name") == "move-lab-proof-scope":
            return str(check.get("detail") or "missing")
    return "missing"


def file_entry(path: Path, archive_path: str, role: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Missing handoff file: {path}")
    return {
        "path": archive_path,
        "role": role,
        "source_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def capture_kit_entries(capture_kit_dir: Path) -> list[dict[str, Any]]:
    return [
        file_entry(
            capture_kit_dir / "move-lab-transcript.template.json",
            "move/move-lab-transcript.template.json",
            "move_lab_capture_template",
        ),
        file_entry(
            capture_kit_dir / "move-lab-capture-checklist.md",
            "move/move-lab-capture-checklist.md",
            "move_lab_capture_checklist",
        ),
    ]


def archive_manifest_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "source_path"}
