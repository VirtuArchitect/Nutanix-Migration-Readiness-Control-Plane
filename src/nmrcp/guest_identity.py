from __future__ import annotations

import ipaddress
import re
from typing import Any


def guest_identity_from_values(
    *,
    hostname: Any = "",
    dns_name: Any = "",
    ip_addresses: Any = None,
) -> dict[str, Any]:
    ips = normalize_ip_addresses(ip_addresses)
    valid_ips = [item for item in ips if is_valid_ip(item)]
    return {
        "hostname": str(hostname or "").strip(),
        "dns_name": str(dns_name or "").strip(),
        "ip_addresses": ips,
        "valid_ip_addresses": valid_ips,
        "invalid_ip_addresses": [item for item in ips if item not in valid_ips],
        "has_ipv4": any(is_ipv4(item) for item in valid_ips),
        "has_ipv6": any(is_ipv6(item) for item in valid_ips),
    }


def normalize_ip_addresses(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        candidates = value
    else:
        candidates = re.split(r"[,;|\s]+", str(value))
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        ip = str(candidate or "").strip()
        if not ip or ip.lower() in {"unknown", "none", "n/a", "na"}:
            continue
        if "/" in ip:
            ip = ip.split("/", 1)[0]
        if ip not in seen:
            seen.add(ip)
            result.append(ip)
    return result


def is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def is_ipv4(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
    except ValueError:
        return False


def is_ipv6(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv6Address)
    except ValueError:
        return False
