import ipaddress
import re
import uuid
from contextvars import ContextVar

from fastapi import Request

from app.core.config import settings

trace_id: ContextVar[str] = ContextVar("trace_id", default="-")

_VALID_ID = re.compile(r"[A-Za-z0-9-]{8,64}")


def _trusted(host: str | None) -> bool:
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:  # e.g. "testclient"
        return False
    return any(ip in net for net in settings.trusted_networks)


def resolve_trace_id(request: Request) -> str:
    """Adopt X-Request-ID only from a trusted peer and only if well-formed; else generate."""
    incoming = request.headers.get("x-request-id", "")
    if _trusted(request.client.host if request.client else None) and _VALID_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex
