from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .approval_exceptions import validate_approval_exception_approvals
from .capacity import validate_capacity_fit_csv
from .move_lab_capture_kit import validate_move_lab_capture_kit_validation_file
from .move_lab_closure_checklist import validate_move_lab_closure_checklist
from .move_lab_evidence_intake import validate_move_lab_evidence_intake_validation_file
from .move_lab_evidence_request import validate_move_lab_evidence_request
from .move_lab_proof import validate_move_lab_proof_validation_file
from .network_mapping import validate_network_mapping_csv
from .operator_review import validate_operator_review
from .remediation import validate_remediation_tracker
from .signoff import validate_signoffs
from .source_endpoint_evidence_request import validate_source_endpoint_evidence_request
from .source_networks import validate_source_network_validation_csv
from .target_reconciliation import validate_target_reconciliation_csv
from .validation_results import validate_validation_results


REQUIRED_OPERATOR_GATE_LABELS = (
    "Source endpoint evidence request",
    "Move lab evidence request",
    "Target capacity fit",
    "Target reconciliation",
    "Source network validation",
    "Target network mapping",
    "Final validation results",
    "Final remediation closure",
    "Final owner sign-offs",
    "Approval exception closure",
    "Operator assessment review",
    "Move lab capture kit",
    "Move lab closure checklist",
    "Approved Move lab proof",
    "Move lab evidence intake",
)

ALLOWED_OPERATOR_GATE_STATUSES = {"pass", "warn", "fail", "not evaluated", "not supplied"}


@dataclass(frozen=True)
class OperatorGateSummaryValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_operator_gate_summary(
    assessment_dir: Path,
    out_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
) -> Path:
    out_path = out_path or (assessment_dir / "operator-gate-summary.md")
    rows = [
        artifact_check(
            "Source endpoint evidence request",
            assessment_dir / "source-endpoint-evidence-request.md",
            lambda path: _result(validate_source_endpoint_evidence_request(path)),
            "Read-only vCenter and Prism Central evidence request was not generated.",
        ),
        artifact_check(
            "Move lab evidence request",
            assessment_dir / "move-lab-evidence-request.md",
            lambda path: _result(validate_move_lab_evidence_request(path)),
            "Approved Move lab proof-window evidence request was not generated.",
        ),
        artifact_check(
            "Target capacity fit",
            assessment_dir / "target-capacity-fit.csv",
            lambda path: _result(validate_capacity_fit_csv(path)),
            "Target cluster/container headroom was not evaluated.",
        ),
        artifact_check(
            "Target reconciliation",
            assessment_dir / "target-reconciliation.csv",
            lambda path: _result(validate_target_reconciliation_csv(path)),
            "Current Prism inventory collisions were not evaluated.",
        ),
        artifact_check(
            "Source network validation",
            assessment_dir / "source-network-validation.csv",
            lambda path: _result(validate_source_network_validation_csv(path)),
            "Move source network hints were not checked against vCenter network inventory.",
        ),
        artifact_check(
            "Target network mapping",
            assessment_dir / "target-network-mapping.csv",
            lambda path: _result(validate_network_mapping_csv(path)),
            "Move target network mappings were not evaluated.",
        ),
        external_check(
            "Final validation results",
            validation_results_path,
            lambda path: _result(validate_validation_results(path)),
            "Final pre/post validation results were not supplied.",
        ),
        external_check(
            "Final remediation closure",
            remediation_tracker_path,
            lambda path: _result(validate_remediation_tracker(path)),
            "Final remediation tracker was not supplied.",
        ),
        external_check(
            "Final owner sign-offs",
            signoffs_path,
            lambda path: _result(validate_signoffs(path)),
            "Final owner sign-off matrix was not supplied.",
        ),
        external_check(
            "Approval exception closure",
            approval_exceptions_path,
            lambda path: _result(validate_approval_exception_approvals(path, assessment_path=assessment_dir / "assessment.json")),
            "Final approval exception closure was not supplied.",
        ),
        external_check(
            "Operator assessment review",
            operator_review_path,
            lambda path: _result(validate_operator_review(path, assessment_dir=assessment_dir)),
            "Operator/customer assessment review was not supplied.",
        ),
        external_check(
            "Move lab capture kit",
            move_lab_capture_validation_path,
            lambda path: _result(validate_move_lab_capture_kit_validation_file(path)),
            "Move lab capture-kit validation was not supplied.",
        ),
        artifact_check(
            "Move lab closure checklist",
            assessment_dir / "move-lab-closure-checklist.md",
            lambda path: _result(validate_move_lab_closure_checklist(path)),
            "Move lab closure checklist was not generated.",
        ),
        external_check(
            "Approved Move lab proof",
            move_lab_proof_path,
            lambda path: _result(validate_move_lab_proof_validation_file(path, require_approved_lab=True)),
            "Approved non-production Move appliance proof was not supplied.",
        ),
        external_check(
            "Move lab evidence intake",
            move_lab_evidence_intake_path,
            lambda path: _result(validate_move_lab_evidence_intake_validation_file(path)),
            "Final Move lab evidence intake was not supplied.",
        ),
    ]

    out_path.write_text(render_summary(rows), encoding="utf-8")
    return out_path


def artifact_check(label: str, path: Path, validator, missing_detail: str) -> dict[str, Any]:
    if not path.exists():
        return {"label": label, "status": "not evaluated", "detail": missing_detail, "warnings": [], "errors": []}
    return checked_row(label, validator(path))


def external_check(label: str, path: Path | None, validator, missing_detail: str) -> dict[str, Any]:
    if not path:
        return {"label": label, "status": "not supplied", "detail": missing_detail, "warnings": [], "errors": []}
    return checked_row(label, validator(path))


def checked_row(label: str, result: dict[str, Any]) -> dict[str, Any]:
    status = "pass" if result["ok"] and not result["warnings"] else "warn" if result["ok"] else "fail"
    return {
        "label": label,
        "status": status,
        "detail": result["summary"],
        "warnings": result["warnings"],
        "errors": result["errors"],
    }


def _result(validation: Any) -> dict[str, Any]:
    return {
        "ok": bool(validation.ok),
        "summary": validation.summary(),
        "warnings": list(getattr(validation, "warnings", ())),
        "errors": list(getattr(validation, "errors", ())),
    }


def render_summary(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Operator Gate Summary",
        "",
        "| Gate | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['label']} | {row['status']} | {row['detail']} |")

    warnings = [(row["label"], warning) for row in rows for warning in row["warnings"]]
    errors = [(row["label"], error) for row in rows for error in row["errors"]]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {label}: {warning}" for label, warning in warnings)
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {label}: {error}" for label, error in errors)
    lines.extend(
        [
            "",
            "## Use",
            "",
            "Attach this summary with the evidence bundle so operators and change reviewers can see which source, lab, and optional closure gates were evaluated.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_operator_gate_summary(path: Path) -> OperatorGateSummaryValidation:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return OperatorGateSummaryValidation("fail", 1, (f"{path}: could not read operator gate summary: {exc}",), ())

    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    required_fragments = (
        "# Operator Gate Summary",
        "| Gate | Status | Detail |",
        "| --- | --- | --- |",
        "## Use",
        "source, lab, and optional closure gates",
    )
    for fragment in required_fragments:
        checks += 1
        if fragment not in text:
            errors.append(f"Operator gate summary missing required text: {fragment}")

    rows = parse_gate_summary_rows(text)
    for label in REQUIRED_OPERATOR_GATE_LABELS:
        checks += 1
        if label not in rows:
            errors.append(f"Operator gate summary missing required gate row: {label}")

    for label, status in rows.items():
        checks += 1
        if status not in ALLOWED_OPERATOR_GATE_STATUSES:
            errors.append(f"Operator gate summary row {label} has invalid status: {status}")

    checks += 1
    if "Move lab evidence intake" in rows and "Approved Move lab proof" in rows:
        proof_status = rows["Approved Move lab proof"]
        intake_status = rows["Move lab evidence intake"]
        if proof_status == "pass" and intake_status != "pass":
            errors.append("Operator gate summary cannot mark approved Move lab proof pass without Move lab evidence intake pass")

    checks += 1
    if "Source endpoint evidence request" in rows and "Move lab evidence request" in rows:
        if rows["Source endpoint evidence request"] == "not evaluated" or rows["Move lab evidence request"] == "not evaluated":
            warnings.append("Operator gate summary has unevaluated request gates")

    return OperatorGateSummaryValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def parse_gate_summary_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| Gate ") or line.startswith("| ---"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        label, status = cells[0], cells[1]
        if label:
            rows[label] = status
    return rows
