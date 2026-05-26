"""Rate-limit monitoring API router for the free-claude-code proxy.

Exposes per-provider rate-limit stats read from GlobalRateLimiter's in-memory state.
Mount this router on the proxy FastAPI app to enable the dashboard endpoint.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

from providers.rate_limit import GlobalRateLimiter

router = APIRouter(prefix="/api/rate-limits", tags=["rate-limits"])


async def _require_api_key():
    """Lazy wrapper to avoid circular import with api.dependencies."""
    from api.dependencies import require_api_key
    return await require_api_key()


def _provider_status(
    name: str, limiter: GlobalRateLimiter
) -> dict[str, Any]:
    """Read live state from a single scoped GlobalRateLimiter."""
    status = limiter.status()
    return {"provider_name": name, **status}


@router.get("/status", dependencies=[Depends(_require_api_key)])
def rate_limits_status() -> dict[str, Any]:
    """Return per-provider rate-limit status from in-memory limiter state."""
    scoped = dict(GlobalRateLimiter._scoped_instances)
    providers: list[dict[str, Any]] = []

    for name, limiter in sorted(scoped.items()):
        providers.append(_provider_status(name, limiter))

    # Also include the global singleton if it exists and is distinct
    singleton = GlobalRateLimiter._instance
    if singleton is not None and not scoped:
        providers.append(_provider_status("global", singleton))

    return {
        "ok": True,
        "providers": providers,
        "total_providers": len(providers),
        "timestamp": time.time(),
    }
