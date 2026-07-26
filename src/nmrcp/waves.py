from __future__ import annotations

from typing import Any

from .dependencies import dependency_sequence
from .models import Wave, WorkloadAssessment


def plan_waves(assessments: list[WorkloadAssessment], inventory: dict[str, Any] | None = None) -> list[Wave]:
    sequence = dependency_sequence(inventory, assessments) if inventory else []
    sequence_rank = {workload_id: index for index, workload_id in enumerate(sequence)}
    ready = sorted(
        (item for item in assessments if item.readiness == "ready"),
        key=lambda item: (sequence_rank.get(item.workload_id, 999999), item.risk_score),
    )
    research = sorted(
        (item for item in assessments if item.readiness == "research"),
        key=lambda item: (sequence_rank.get(item.workload_id, 999999), item.risk_score),
    )
    prepare = sorted((item for item in assessments if item.readiness == "prepare"), key=lambda item: item.risk_score)
    blocked = sorted((item for item in assessments if item.readiness == "blocked"), key=lambda item: item.risk_score)

    waves: list[Wave] = []
    if ready:
        waves.append(
            Wave(
                "Wave 0 - Pilot Ready",
                "Low-risk workloads that can validate the migration factory and rollback evidence.",
                tuple(item.workload_id for item in ready),
            )
        )
    if research:
        waves.append(
            Wave(
                "Wave 1 - Research Required",
                "Workloads that need compatibility confirmation before scheduling.",
                tuple(item.workload_id for item in research),
            )
        )
    if prepare:
        waves.append(
            Wave(
                "Wave 2 - Remediation Required",
                "Workloads that need driver, backup, snapshot, vendor, or dependency remediation.",
                tuple(item.workload_id for item in prepare),
            )
        )
    if blocked:
        waves.append(
            Wave(
                "Excluded Until Cleared",
                "Workloads with blockers such as NSX dependency, missing backup proof, or high risk score.",
                tuple(item.workload_id for item in blocked),
            )
        )
    return waves
