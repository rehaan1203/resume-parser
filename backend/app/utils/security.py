"""Security utilities: SSRF-safe URL validation and admin route authentication."""
import hmac
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

from fastapi import Header, HTTPException, status

from app.config import settings
from app.utils.logger import logger


def validate_public_http_url(url: str) -> str:
    """
    Validate that an outbound fetch target is an http/https public URL and not
    a loopback, private RFC-1918, link-local, or cloud metadata address (SSRF defense).
    """
    clean_url = (url or "").strip()
    if not clean_url:
        raise ValueError("URL must not be empty.")

    parsed = urlparse(clean_url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Only http and https URLs are supported.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("URL must contain a valid hostname.")

    if hostname in ("localhost", "localhost.localdomain") or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError(f"Blocked internal hostname: {hostname}")

    # Direct IP literal check
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if _is_disallowed_ip(ip_obj):
            raise ValueError(f"Blocked non-public IP address: {hostname}")
        return clean_url
    except ValueError as err:
        if "Blocked" in str(err):
            raise

    # Resolve DNS addresses and verify every resolved endpoint is globally routable
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}'") from exc

    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0].split("%")[0]
        ip_obj = ipaddress.ip_address(ip_str)
        if _is_disallowed_ip(ip_obj):
            raise ValueError(f"Blocked resolution to non-public address for host '{hostname}'")

    return clean_url


def _is_disallowed_ip(ip_obj: ipaddress._BaseAddress) -> bool:
    """Return True if an IP address is loopback, private, link-local, multicast, or reserved."""
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


async def require_admin_access(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """
    Enforce admin authentication for operational/destructive endpoints.
    - When ADMIN_API_KEY is configured, requests must supply a matching X-Admin-Key header.
    - When ADMIN_API_KEY is unset, requests are permitted only in debug mode.
    """
    configured_key = (getattr(settings, "admin_api_key", None) or "").strip()
    if configured_key:
        supplied = (x_admin_key or "").strip()
        if not supplied or not hmac.compare_digest(supplied, configured_key):
            logger.warning("Unauthorized admin route access attempt rejected.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin authentication required.",
            )
        return

    if not getattr(settings, "debug", True):
        logger.warning("Blocked operational endpoint in production without configured ADMIN_API_KEY.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operational endpoints require ADMIN_API_KEY in production mode.",
        )

