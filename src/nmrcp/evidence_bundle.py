from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .evidence import sha256_file


@dataclass(frozen=True)
class BundleVerification:
    checked: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checked={self.checked}, errors={len(self.errors)}"


def package_evidence(out_dir: Path, bundle_path: Path) -> Path:
    manifest_path = out_dir / "evidence-manifest.json"
    manifest = load_manifest(manifest_path)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, arcname="evidence-manifest.json")
        for artifact in manifest["artifacts"]:
            artifact_path = out_dir / artifact["name"]
            archive.write(artifact_path, arcname=artifact["name"])
    return bundle_path


def verify_evidence(out_dir: Path) -> BundleVerification:
    manifest = load_manifest(out_dir / "evidence-manifest.json")
    errors: list[str] = []
    checked = 0
    for artifact in manifest["artifacts"]:
        checked += 1
        artifact_path = out_dir / artifact["name"]
        if not artifact_path.exists():
            errors.append(f"{artifact['name']}: missing")
            continue
        size = artifact_path.stat().st_size
        if size != artifact["size_bytes"]:
            errors.append(f"{artifact['name']}: size mismatch expected={artifact['size_bytes']} actual={size}")
        digest = sha256_file(artifact_path)
        if digest != artifact["sha256"]:
            errors.append(f"{artifact['name']}: sha256 mismatch")
    return BundleVerification(checked=checked, errors=tuple(errors))


def verify_evidence_bundle(bundle_path: Path) -> BundleVerification:
    errors: list[str] = []
    checked = 0
    with zipfile.ZipFile(bundle_path, "r") as archive:
        names = set(archive.namelist())
        if "evidence-manifest.json" not in names:
            return BundleVerification(0, ("bundle missing evidence-manifest.json",))
        manifest = json.loads(archive.read("evidence-manifest.json").decode("utf-8"))
        paths_seen: set[str] = set()
        for artifact in manifest.get("artifacts", []):
            checked += 1
            name = artifact["name"]
            paths_seen.add(name)
            if name not in names:
                errors.append(f"{name}: missing from bundle")
                continue
            data = archive.read(name)
            if len(data) != artifact["size_bytes"]:
                errors.append(f"{name}: size mismatch expected={artifact['size_bytes']} actual={len(data)}")
            import hashlib

            digest = hashlib.sha256(data).hexdigest()
            if digest != artifact["sha256"]:
                errors.append(f"{name}: sha256 mismatch")
        for name in sorted(names.difference(paths_seen).difference({"evidence-manifest.json"})):
            errors.append(f"{name}: bundle entry is not listed in evidence manifest")
    return BundleVerification(checked=checked, errors=tuple(errors))


def load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        raise ValueError(f"Missing evidence manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "nmrcp_evidence_manifest_v1":
        raise ValueError("Unsupported evidence manifest schema")
    if not isinstance(manifest.get("artifacts"), list):
        raise ValueError("Evidence manifest must contain an artifacts list")
    return manifest
