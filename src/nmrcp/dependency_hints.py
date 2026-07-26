from __future__ import annotations

import re
from typing import Any


DEPENDENCY_HINT_KEYS = {
    "dependency",
    "dependencies",
    "depends_on",
    "depends",
    "application_dependency",
    "application_dependencies",
    "app_dependency",
    "app_dependencies",
}


def dependencies_from_metadata(
    tags: list[Any] | dict[str, Any] | None = None,
    notes: list[Any] | None = None,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for value in _dependency_values_from_tags(tags):
        records.extend(_records_from_value(value))
    for note in notes or []:
        records.extend(_records_from_note(str(note or "")))
    return _dedupe(records)


def _dependency_values_from_tags(tags: list[Any] | dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    if isinstance(tags, dict):
        iterable = tags.items()
    else:
        iterable = []
        for tag in tags or []:
            if isinstance(tag, str) and ":" in tag:
                key, value = tag.split(":", 1)
                iterable.append((key, value))
            elif isinstance(tag, dict):
                key = tag.get("key") or tag.get("category") or tag.get("name")
                value = tag.get("value")
                iterable.append((key, value))
    for key, value in iterable:
        if _normalize_key(str(key or "")) in DEPENDENCY_HINT_KEYS and value not in {None, ""}:
            if isinstance(value, list):
                values.extend(str(item) for item in value if item not in {None, ""})
            else:
                values.append(str(value))
    return values


def _records_from_note(note: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for match in re.finditer(
        r"(?im)(?:^|[;\n])\s*([A-Za-z][A-Za-z0-9 _-]{0,40})\s*[:=]\s*([^;\n]+)",
        note,
    ):
        key, value = match.groups()
        if _normalize_key(key) in DEPENDENCY_HINT_KEYS:
            records.extend(_records_from_value(value))
    return records


def _records_from_value(value: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for name in re.split(r"[,|]", value):
        dependency_name = name.strip()
        if not dependency_name:
            continue
        records.append(
            {
                "name": dependency_name,
                "id": "",
                "type": "declared",
                "owner": "",
                "criticality": "",
                "notes": "Declared in source metadata.",
            }
        )
    return records


def _dedupe(records: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        key = str(record.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")
