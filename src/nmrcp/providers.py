from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SOURCE_PROVIDER = "vmware_vcenter"
DEFAULT_TARGET_PROVIDER = "nutanix_ahv"


@dataclass(frozen=True)
class SourceProvider:
    id: str
    label: str
    collector: str
    status: str


@dataclass(frozen=True)
class TargetProvider:
    id: str
    label: str
    profile: str
    status: str


@dataclass(frozen=True)
class ReadinessRuleSet:
    id: str
    label: str
    source_provider: str
    target_provider: str
    status: str


@dataclass(frozen=True)
class ProviderPair:
    source: SourceProvider
    target: TargetProvider
    rule_set: ReadinessRuleSet

    @property
    def id(self) -> str:
        return f"{self.source.id}->{self.target.id}"


SOURCE_PROVIDERS: dict[str, SourceProvider] = {
    "vmware_vcenter": SourceProvider(
        id="vmware_vcenter",
        label="VMware vCenter",
        collector="read-only vCenter inventory collector",
        status="validated",
    ),
    "rvtools_import": SourceProvider(
        id="rvtools_import",
        label="RVTools / Offline Import",
        collector="offline CSV/JSON import",
        status="validated",
    ),
}

TARGET_PROVIDERS: dict[str, TargetProvider] = {
    "nutanix_ahv": TargetProvider(
        id="nutanix_ahv",
        label="Nutanix AHV",
        profile="Nutanix AHV readiness profile",
        status="validated",
    ),
    "nutanix_nc2": TargetProvider(
        id="nutanix_nc2",
        label="Nutanix NC2",
        profile="Nutanix NC2 readiness profile",
        status="validated",
    ),
}

READINESS_RULE_SETS: dict[tuple[str, str], ReadinessRuleSet] = {
    ("vmware_vcenter", "nutanix_ahv"): ReadinessRuleSet(
        id="vmware_to_nutanix_ahv",
        label="VMware to Nutanix AHV",
        source_provider="vmware_vcenter",
        target_provider="nutanix_ahv",
        status="validated",
    ),
    ("vmware_vcenter", "nutanix_nc2"): ReadinessRuleSet(
        id="vmware_to_nutanix_nc2",
        label="VMware to Nutanix NC2",
        source_provider="vmware_vcenter",
        target_provider="nutanix_nc2",
        status="validated",
    ),
    ("rvtools_import", "nutanix_ahv"): ReadinessRuleSet(
        id="rvtools_to_nutanix_ahv",
        label="RVTools import to Nutanix AHV",
        source_provider="rvtools_import",
        target_provider="nutanix_ahv",
        status="validated",
    ),
    ("rvtools_import", "nutanix_nc2"): ReadinessRuleSet(
        id="rvtools_to_nutanix_nc2",
        label="RVTools import to Nutanix NC2",
        source_provider="rvtools_import",
        target_provider="nutanix_nc2",
        status="validated",
    ),
}


def source_provider_ids() -> tuple[str, ...]:
    return tuple(SOURCE_PROVIDERS)


def target_provider_ids() -> tuple[str, ...]:
    return tuple(TARGET_PROVIDERS)


def target_provider_cli_choices() -> tuple[str, ...]:
    return (*target_provider_ids(), "ahv", "nc2")


def provider_pairs() -> tuple[ProviderPair, ...]:
    return tuple(
        ProviderPair(SOURCE_PROVIDERS[source_id], TARGET_PROVIDERS[target_id], rule_set)
        for (source_id, target_id), rule_set in READINESS_RULE_SETS.items()
    )


def resolve_provider_pair(source: str = DEFAULT_SOURCE_PROVIDER, target: str = DEFAULT_TARGET_PROVIDER) -> ProviderPair:
    source_id = normalize_source_provider(source)
    target_id = normalize_target_provider(target)
    rule_set = READINESS_RULE_SETS.get((source_id, target_id))
    if rule_set is None:
        raise ValueError(f"Unsupported provider pair: {source_id}->{target_id}")
    return ProviderPair(SOURCE_PROVIDERS[source_id], TARGET_PROVIDERS[target_id], rule_set)


def normalize_source_provider(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "vcenter": "vmware_vcenter",
        "vmware": "vmware_vcenter",
        "vmware_vsphere": "vmware_vcenter",
        "rvtools": "rvtools_import",
        "import": "rvtools_import",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SOURCE_PROVIDERS:
        raise ValueError(f"Unsupported source provider: {value}")
    return normalized


def normalize_target_provider(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "ahv": "nutanix_ahv",
        "nc2": "nutanix_nc2",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in TARGET_PROVIDERS:
        raise ValueError(f"Unsupported target provider: {value}")
    return normalized


def target_to_assessment_id(value: str) -> str:
    target_id = normalize_target_provider(value)
    if target_id == "nutanix_ahv":
        return "ahv"
    if target_id == "nutanix_nc2":
        return "nc2"
    raise ValueError(f"Unsupported assessment target provider: {value}")


def provider_catalog() -> dict[str, object]:
    return {
        "sources": [provider.__dict__ for provider in SOURCE_PROVIDERS.values()],
        "targets": [provider.__dict__ for provider in TARGET_PROVIDERS.values()],
        "pairs": [
            {
                "id": pair.id,
                "source": pair.source.id,
                "target": pair.target.id,
                "rule_set": pair.rule_set.id,
                "status": pair.rule_set.status,
            }
            for pair in provider_pairs()
        ],
    }
