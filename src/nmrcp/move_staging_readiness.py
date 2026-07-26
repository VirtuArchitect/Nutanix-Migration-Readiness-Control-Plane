from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Wave, WorkloadAssessment
from .recovery_readiness import recovery_readiness_row
from .storage_posture import storage_posture_row
from .tools_driver_readiness import tools_driver_row


MOVE_STAGING_READINESS_SCHEMA_VERSION = "nmrcp_move_staging_readiness_v1"
MOVE_STAGING_BRIEF_SCHEMA_VERSION = "nmrcp_move_staging_brief_v1"
MOVE_STAGING_READINESS_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "move_plan_decision",
    "readiness",
    "risk_score",
    "tools_driver_status",
    "storage_status",
    "recovery_status",
    "application_owner_approval",
    "rollback_owner",
    "stage_status",
    "blocking_findings",
    "required_action",
    "evidence_refs",
)


@dataclass(frozen=True)
class MoveStagingReadinessValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


@dataclass(frozen=True)
class MoveStagingBriefValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def move_staging_readiness_context(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    return {
        "schema_version": MOVE_STAGING_READINESS_SCHEMA_VERSION,
        "workloads": [
            move_staging_readiness_row(workloads.get(assessment.workload_id, {}), assessment, wave_by_workload)
            for assessment in assessments
        ],
    }


def write_move_staging_readiness_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = move_staging_readiness_context(inventory, assessments, waves)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MOVE_STAGING_READINESS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_move_staging_brief(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = move_staging_readiness_context(inventory, assessments, waves)["workloads"]
    path.write_text(render_move_staging_brief(rows), encoding="utf-8")


def validate_move_staging_readiness(path: Path, assessment_path: Path) -> MoveStagingReadinessValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return MoveStagingReadinessValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_move_staging_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("move-staging-readiness.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing Move staging readiness row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected Move staging readiness row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("move-staging-readiness.csv cannot be empty")

    return MoveStagingReadinessValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def validate_move_staging_brief(brief_path: Path, assessment_path: Path) -> MoveStagingBriefValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        actual = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        return MoveStagingBriefValidation("fail", 1, (f"{brief_path}: could not read Move staging brief: {exc}",), ())
    assessment = read_assessment(assessment_path, errors)
    checks += 1
    if errors:
        return MoveStagingBriefValidation("fail", checks, tuple(errors), tuple(warnings))
    expected_rows = expected_move_staging_rows(assessment, errors)
    checks += 1
    if errors:
        return MoveStagingBriefValidation("fail", checks, tuple(errors), tuple(warnings))
    expected = render_move_staging_brief(list(expected_rows.values()))

    for required in (
        "# Move Staging Brief",
        MOVE_STAGING_BRIEF_SCHEMA_VERSION,
        "## Staging Decision",
        "## Include Candidates",
        "## Holds And Conditional Reviews",
        "## Evidence To Inspect",
        "Do not open Nutanix Move staging for rows with `stage_status=hold`.",
        "`nutanix-move-plan.csv`",
        "`move-staging-readiness.csv`",
    ):
        checks += 1
        if required not in actual:
            errors.append(f"Move staging brief missing required text: {required}")

    checks += 1
    if normalize_markdown(actual) != normalize_markdown(expected):
        errors.append("Move staging brief does not match assessment.json Move staging readiness context")
    checks += 1
    if "vcenter01.corp.local" in actual:
        errors.append("Move staging brief leaked sample vCenter hostname")
    checks += 1
    if "migration.owner@example.com" in actual:
        errors.append("Move staging brief leaked sample operator email")

    return MoveStagingBriefValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def move_staging_readiness_row(
    workload: dict[str, Any],
    assessment: WorkloadAssessment,
    wave_by_workload: dict[str, str],
) -> dict[str, str]:
    governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
    tools = tools_driver_row(workload, assessment)
    storage = storage_posture_row(workload, assessment)
    recovery = recovery_readiness_row(workload, assessment)
    app_approval = governance_status(governance.get("application_owner_approved"))
    rollback_owner = recovery["rollback_owner"]
    move_plan_decision = "include" if assessment.readiness in {"ready", "research"} else "hold"
    blockers = staging_blockers(assessment, tools, storage, recovery, app_approval, rollback_owner)
    status = stage_status(blockers, assessment, tools, storage, recovery)
    return {
        "schema_version": MOVE_STAGING_READINESS_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
        "move_plan_decision": move_plan_decision,
        "readiness": assessment.readiness,
        "risk_score": str(assessment.risk_score),
        "tools_driver_status": tools["driver_status"],
        "storage_status": storage["storage_status"],
        "recovery_status": recovery["recovery_status"],
        "application_owner_approval": app_approval,
        "rollback_owner": rollback_owner,
        "stage_status": status,
        "blocking_findings": "; ".join(blockers),
        "required_action": required_action(status, blockers),
        "evidence_refs": ";".join(
            [
                f"assessment.json#{assessment.workload_id}",
                f"nutanix-move-plan.csv#{assessment.workload_id}",
                f"tools-driver-readiness.csv#{assessment.workload_id}",
                f"storage-posture.csv#{assessment.workload_id}",
                f"recovery-readiness.csv#{assessment.workload_id}",
            ]
        ),
    }


def render_move_staging_brief(rows: list[dict[str, str]]) -> str:
    summary = move_staging_summary(rows)
    include_rows = [row for row in sorted(rows, key=move_staging_sort_key) if row.get("stage_status") == "ready"]
    review_rows = [row for row in sorted(rows, key=move_staging_sort_key) if row.get("stage_status") != "ready"]
    lines = [
        "# Move Staging Brief",
        "",
        f"Schema: `{MOVE_STAGING_BRIEF_SCHEMA_VERSION}`",
        "",
        "## Staging Decision",
        "",
        f"- Decision signal: {move_staging_decision_signal(summary)}",
        f"- Workloads represented: {summary['workloads']}",
        f"- Ready for Move staging precheck: {summary['ready']}",
        f"- Conditional review rows: {summary['conditional']}",
        f"- Held rows: {summary['hold']}",
        f"- Included by Move plan: {summary['include']}",
        f"- Held by Move plan: {summary['move_plan_hold']}",
        "",
        "## Include Candidates",
        "",
        *move_staging_include_lines(include_rows),
        "",
        "## Holds And Conditional Reviews",
        "",
        *move_staging_review_lines(review_rows),
        "",
        "## Evidence To Inspect",
        "",
        "- `nutanix-move-plan.csv`: include or hold decision for each workload.",
        "- `move-staging-readiness.csv`: source row for every staging status in this brief.",
        "- `workload-validation-checklist.csv`: precheck, cutover, and post-migration validation evidence.",
        "- `owner-signoff-matrix.csv`: application owner, rollback owner, and approval state.",
        "- `what-will-break-brief.md`: reviewer-readable breakage scenarios that explain held workloads.",
        "",
        "## Stop Conditions",
        "",
        "- Do not open Nutanix Move staging for rows with `stage_status=hold`.",
        "- Treat `stage_status=conditional` as planning-only until the listed blockers are closed or accepted.",
        "- Re-run assessment after remediation and confirm the workload appears in `ready` before Move payload submission.",
    ]
    return "\n".join(lines) + "\n"


def move_staging_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "workloads": len({row.get("workload_id", "") for row in rows if row.get("workload_id")}),
        "ready": count_rows(rows, "stage_status", "ready"),
        "conditional": count_rows(rows, "stage_status", "conditional"),
        "hold": count_rows(rows, "stage_status", "hold"),
        "include": count_rows(rows, "move_plan_decision", "include"),
        "move_plan_hold": count_rows(rows, "move_plan_decision", "hold"),
    }


def count_rows(rows: list[dict[str, str]], field: str, value: str) -> int:
    return sum(1 for row in rows if row.get(field) == value)


def move_staging_decision_signal(summary: dict[str, int]) -> str:
    if summary["hold"]:
        return "Hold blocked workloads out of Nutanix Move and clear staging blockers before payload submission."
    if summary["conditional"]:
        return "Use planning-only review until conditional evidence is closed or accepted."
    if summary["ready"]:
        return "Proceed to controlled Move staging precheck after owner sign-off and validation evidence review."
    return "No workloads are ready for Nutanix Move staging."


def move_staging_include_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- No workloads are currently ready for Move staging precheck."]
    return [
        f"- {row.get('name') or 'unknown'} (`{row.get('workload_id') or 'unknown'}`), owner `{row.get('owner') or 'Unassigned'}`, "
        f"wave `{row.get('wave') or 'Unassigned'}`, target `{row.get('target') or 'unknown'}`: "
        f"{row.get('required_action') or 'Ready for Move staging precheck.'} Evidence: `{row.get('evidence_refs') or 'none'}`."
        for row in rows
    ]


def move_staging_review_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- No held or conditional staging rows were generated."]
    return [
        f"- {row.get('stage_status') or 'unknown'}: {row.get('name') or 'unknown'} (`{row.get('workload_id') or 'unknown'}`), "
        f"owner `{row.get('owner') or 'Unassigned'}`, wave `{row.get('wave') or 'Unassigned'}`. "
        f"Blockers: `{row.get('blocking_findings') or 'none'}`. Action: {row.get('required_action') or 'Review before staging.'} "
        f"Evidence: `{row.get('evidence_refs') or 'none'}`."
        for row in rows
    ]


def move_staging_sort_key(row: dict[str, str]) -> tuple[int, int, str]:
    status_rank = {"hold": 0, "conditional": 1, "ready": 2}.get(row.get("stage_status", ""), 3)
    try:
        risk = int(row.get("risk_score") or 0)
    except ValueError:
        risk = 0
    return (status_rank, -risk, row.get("name") or "")


def normalize_markdown(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def staging_blockers(
    assessment: WorkloadAssessment,
    tools: dict[str, str],
    storage: dict[str, str],
    recovery: dict[str, str],
    app_approval: str,
    rollback_owner: str,
) -> list[str]:
    blockers: list[str] = []
    if assessment.readiness in {"prepare", "blocked"}:
        blockers.append(f"readiness_{assessment.readiness}")
    if tools["driver_status"] == "blocked":
        blockers.append("tools_driver_blocked")
    elif tools["driver_status"] in {"research", "remediate"}:
        blockers.append(f"tools_driver_{tools['driver_status']}")
    if storage["storage_status"] == "blocked":
        blockers.append("storage_blocked")
    elif storage["storage_status"] in {"review", "remediate"}:
        blockers.append(f"storage_{storage['storage_status']}")
    if recovery["recovery_status"] == "blocked":
        blockers.append("recovery_blocked")
    elif recovery["recovery_status"] in {"review", "remediate"}:
        blockers.append(f"recovery_{recovery['recovery_status']}")
    if app_approval != "confirmed":
        blockers.append("application_owner_approval_missing")
    if rollback_owner in {"", "not confirmed"}:
        blockers.append("rollback_owner_missing")
    return blockers


def stage_status(
    blockers: list[str],
    assessment: WorkloadAssessment,
    tools: dict[str, str],
    storage: dict[str, str],
    recovery: dict[str, str],
) -> str:
    hard_blockers = {
        "readiness_prepare",
        "readiness_blocked",
        "tools_driver_blocked",
        "storage_blocked",
        "recovery_blocked",
        "application_owner_approval_missing",
        "rollback_owner_missing",
    }
    if hard_blockers.intersection(blockers):
        return "hold"
    if (
        assessment.readiness == "research"
        or tools["driver_status"] in {"research", "remediate"}
        or storage["storage_status"] in {"review", "remediate"}
        or recovery["recovery_status"] in {"review", "remediate"}
    ):
        return "conditional"
    return "ready"


def required_action(status: str, blockers: list[str]) -> str:
    actions: list[str] = []
    if any(blocker.startswith("readiness_") for blocker in blockers):
        actions.append("Close readiness findings before Move staging.")
    if any(blocker.startswith("tools_driver_") for blocker in blockers):
        actions.append("Resolve tools and VirtIO driver readiness evidence.")
    if any(blocker.startswith("storage_") for blocker in blockers):
        actions.append("Resolve storage posture findings or capture owner risk acceptance.")
    if any(blocker.startswith("recovery_") for blocker in blockers):
        actions.append("Resolve backup, snapshot, and rollback evidence.")
    if "application_owner_approval_missing" in blockers:
        actions.append("Collect confirmed application owner approval.")
    if "rollback_owner_missing" in blockers:
        actions.append("Assign and confirm rollback owner.")
    if actions:
        return " ".join(actions)
    if status == "conditional":
        return "Review remaining conditional evidence before opening Move staging."
    return "Ready for Move staging precheck and lab-only payload review."


def governance_status(value: Any) -> str:
    if value is True:
        return "confirmed"
    if value is False:
        return "not confirmed"
    return "not supplied"


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in MOVE_STAGING_READINESS_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read Move staging readiness CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_move_staging_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("move_staging_readiness_context") if isinstance(assessment.get("move_staging_readiness_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != MOVE_STAGING_READINESS_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {MOVE_STAGING_READINESS_SCHEMA_VERSION} Move staging readiness context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        workload_id = str(row.get("workload_id") or "")
        expected[workload_id] = {column: str(row.get(column) or "") for column in MOVE_STAGING_READINESS_COLUMNS}
    return expected
