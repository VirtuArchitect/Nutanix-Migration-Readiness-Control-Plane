from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_SECTIONS = (
    "# Pre/Post Migration Validation Checklist",
    "## Pre-Migration",
    "## Cutover",
    "## Post-Migration",
)

REQUIRED_CHECKLIST_ITEMS = (
    "- Confirm source VM owner and application owner.",
    "- Confirm recent recoverable backup and restore point.",
    "- Confirm guest OS and application vendor support for target.",
    "- Confirm network mapping, VLAN, IPAM, DNS, firewall, and load-balancer dependencies.",
    "- Confirm snapshots are removed or consolidated.",
    "- Confirm Nutanix VirtIO readiness where required.",
    "- Confirm migration window, rollback owner, and rollback stop condition.",
    "- Export preflight evidence pack and attach it to the change request.",
    "- Capture source VM power state and final sync status.",
    "- Execute migration only for workloads cleared for the selected wave.",
    "- Stop if an excluded or blocked workload appears in the execution list.",
    "- Record start time, operator, source, target, and migration tool run identifier.",
    "- Confirm VM power state, IP configuration, DNS, time sync, and tools/drivers.",
    "- Confirm application health check from the application owner.",
    "- Confirm backup policy on target.",
    "- Confirm monitoring, alerting, and log collection on target.",
    "- Capture post-cutover evidence and close or roll back per change criteria.",
)


@dataclass(frozen=True)
class ValidationChecklistValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_validation_checklist(path: Path) -> ValidationChecklistValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationChecklistValidation("fail", 1, (f"{path}: could not read validation checklist: {exc}",), ())

    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Validation checklist missing required section: {section}")

    for item in REQUIRED_CHECKLIST_ITEMS:
        checks += 1
        if item not in text:
            errors.append(f"Validation checklist missing required item: {item}")

    checks += 1
    if "Stop if an excluded or blocked workload appears in the execution list." not in text:
        errors.append("Validation checklist must include the excluded or blocked workload stop condition")

    checks += 1
    if "rollback stop condition" not in text or "close or roll back per change criteria" not in text:
        errors.append("Validation checklist must include rollback stop and post-cutover closure criteria")

    checks += 1
    if "evidence" not in text.lower():
        errors.append("Validation checklist must require preflight or post-cutover evidence capture")

    checks += 1
    bullet_count = sum(1 for line in text.splitlines() if line.startswith("- "))
    if bullet_count < len(REQUIRED_CHECKLIST_ITEMS):
        errors.append(
            f"Validation checklist has too few checklist items: expected at least {len(REQUIRED_CHECKLIST_ITEMS)}, found {bullet_count}"
        )

    return ValidationChecklistValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))
