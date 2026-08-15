"""Trusted proxy IP resolution for client IP extraction.

Behind a reverse proxy, `request.client.host` returns the proxy's IP,
not the real client IP. This module safely extracts the client IP from
X-Forwarded-For headers, but ONLY when the direct connection comes from
a configured trusted proxy.

NEVER trust X-Forwarded-For from arbitrary clients on the public internet.
"""

import ipaddress

from fastapi import Request

from app.core.config import settings

_TRUSTED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None


def _get_trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse TRUSTED_PROXY_CIDRS into network objects. Cached."""
    global _TRUSTED_NETWORKS
    if _TRUSTED_NETWORKS is not None:
        return _TRUSTED_NETWORKS

    _TRUSTED_NETWORKS = []
    if not settings.TRUSTED_PROXY_CIDRS:
        return _TRUSTED_NETWORKS

    for cidr in settings.TRUSTED_PROXY_CIDRS.split(","):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            _TRUSTED_NETWORKS.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            pass  # silently skip invalid CIDRs
    return _TRUSTED_NETWORKS


def _is_trusted_proxy(ip: str) -> bool:
    """Check if the direct connection IP is a trusted proxy."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _get_trusted_networks())


def get_client_ip(request: Request) -> str:
    """Extract the real client IP from a request.

    If the direct connection comes from a trusted proxy (configured via
    TRUSTED_PROXY_CIDRS), parse X-Forwarded-For and return the leftmost
    (original client) IP.

    If no trusted proxies are configured, or the connection is not from
    a trusted proxy, return the direct connection IP.

    Never trusts X-Forwarded-For from untrusted sources.
    """
    direct_ip = request.client.host if request.client else "unknown"

    if not _is_trusted_proxy(direct_ip):
        return direct_ip

    # Trusted proxy: parse X-Forwarded-For (leftmost = original client)
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2
        # Leftmost is the original client
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    return direct_ip
