from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .dependencies import DEPENDENCY_FIELDS


APP_MAP_SCHEMA_VERSION = "nmrcp_app_map_v1"
DEPENDENCY_CSV_COLUMNS = [
    "source_id",
    "source_name",
    "dependency_name",
    "dependency_id",
    "dependency_type",
    "owner",
    "criticality",
    "protocol",
    "ports",
    "direction",
    "validation_method",
    "notes",
]


def read_app_map(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("App map must be a JSON object")
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != APP_MAP_SCHEMA_VERSION:
        raise ValueError(f"App map schema_version must be {APP_MAP_SCHEMA_VERSION}")

    records: list[dict[str, str]] = []
    records.extend(_records_from_applications(payload.get("applications")))
    records.extend(_records_from_edges(payload.get("edges")))
    deduped = _dedupe_records(records)
    if not deduped:
        raise ValueError("App map did not contain any dependency records")
    return deduped


def write_dependency_csv(records: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEPENDENCY_CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in DEPENDENCY_CSV_COLUMNS})
    return path


def _records_from_applications(value: Any) -> list[dict[str, str]]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise ValueError("App map applications must be a list")
    records: list[dict[str, str]] = []
    for index, application in enumerate(value, start=1):
        if not isinstance(application, dict):
            raise ValueError(f"applications[{index}] must be an object")
        source_id = _text(application.get("source_id") or application.get("id"))
        source_name = _text(application.get("source_name") or application.get("name"))
        dependencies = application.get("dependencies")
        if dependencies is None or dependencies == "":
            continue
        if not isinstance(dependencies, list):
            raise ValueError(f"applications[{index}].dependencies must be a list")
        for dep_index, dependency in enumerate(dependencies, start=1):
            if not isinstance(dependency, dict):
                raise ValueError(f"applications[{index}].dependencies[{dep_index}] must be an object")
            records.append(
                _dependency_record(
                    source_id=source_id,
                    source_name=source_name,
                    dependency_name=_text(dependency.get("name") or dependency.get("dependency_name")),
                    dependency_id=_text(dependency.get("id") or dependency.get("dependency_id")),
                    dependency_type=_text(dependency.get("type") or dependency.get("dependency_type") or "application"),
                    owner=_text(dependency.get("owner")),
                    criticality=_text(dependency.get("criticality")),
                    protocol=_text(dependency.get("protocol")),
                    ports=_text(dependency.get("ports") or dependency.get("port")),
                    direction=_text(dependency.get("direction")),
                    validation_method=_text(dependency.get("validation_method")),
                    notes=_text(dependency.get("notes") or "Imported from app map."),
                )
            )
    return records


def _records_from_edges(value: Any) -> list[dict[str, str]]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise ValueError("App map edges must be a list")
    records: list[dict[str, str]] = []
    for index, edge in enumerate(value, start=1):
        if not isinstance(edge, dict):
            raise ValueError(f"edges[{index}] must be an object")
        records.append(
            _dependency_record(
                source_id=_text(edge.get("source_id")),
                source_name=_text(edge.get("source_name") or edge.get("source") or edge.get("from")),
                dependency_name=_text(edge.get("dependency_name") or edge.get("target_name") or edge.get("target") or edge.get("to")),
                dependency_id=_text(edge.get("dependency_id") or edge.get("target_id")),
                dependency_type=_text(edge.get("dependency_type") or edge.get("relationship") or edge.get("type") or "application"),
                owner=_text(edge.get("owner")),
                criticality=_text(edge.get("criticality")),
                protocol=_text(edge.get("protocol")),
                ports=_text(edge.get("ports") or edge.get("port")),
                direction=_text(edge.get("direction")),
                validation_method=_text(edge.get("validation_method")),
                notes=_text(edge.get("notes") or "Imported from app map edge."),
            )
        )
    return records


def _dependency_record(
    *,
    source_id: str,
    source_name: str,
    dependency_name: str,
    dependency_id: str,
    dependency_type: str,
    owner: str,
    criticality: str,
    protocol: str,
    ports: str,
    direction: str,
    validation_method: str,
    notes: str,
) -> dict[str, str]:
    if not source_id and not source_name:
        raise ValueError("App map dependency records require source_id or source_name")
    if not dependency_name:
        raise ValueError("App map dependency records require dependency name")
    record = {
        "source_id": source_id,
        "source_name": source_name,
        "dependency_name": dependency_name,
        "dependency_id": dependency_id,
        "dependency_type": dependency_type,
        "owner": owner,
        "criticality": criticality,
        "protocol": protocol,
        "ports": ports,
        "direction": direction,
        "validation_method": validation_method,
        "notes": notes,
    }
    return {key: record.get(key, "") for key in DEPENDENCY_FIELDS}


def _dedupe_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            record.get("source_id", "").strip().lower(),
            record.get("source_name", "").strip().lower(),
            record.get("dependency_id", "").strip().lower(),
            record.get("dependency_name", "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _text(value: Any) -> str:
    return str(value or "").strip()
