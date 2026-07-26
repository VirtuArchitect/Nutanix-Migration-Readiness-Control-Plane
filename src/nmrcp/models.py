from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    recommended_action: str


@dataclass(frozen=True)
class WorkloadAssessment:
    workload_id: str
    name: str
    owner: str
    readiness: str
    risk_score: int
    target: str
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonObject:
        return {
            "workload_id": self.workload_id,
            "name": self.name,
            "owner": self.owner,
            "readiness": self.readiness,
            "risk_score": self.risk_score,
            "target": self.target,
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                    "recommended_action": finding.recommended_action,
                }
                for finding in self.findings
            ],
        }


@dataclass(frozen=True)
class Wave:
    name: str
    description: str
    workload_ids: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        return {
            "name": self.name,
            "description": self.description,
            "workload_ids": list(self.workload_ids),
        }
