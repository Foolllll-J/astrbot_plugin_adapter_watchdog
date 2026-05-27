from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_dingtalk_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    stream_client = getattr(platform, "client_", None)
    if stream_client is not None:
        ws = getattr(stream_client, "websocket", None)
        if ws is None:
            return AdapterHealth(online=False, reason="websocket not connected")
        try:
            ws_closed = bool(
                getattr(ws, "closed", getattr(ws, "close_code", None) is not None)
            )
            if ws_closed:
                return AdapterHealth(online=False, reason="websocket closed")
        except AttributeError:
            pass

    try:
        token = await asyncio.wait_for(
            platform.get_access_token(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(online=False, reason="get_access_token timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"get_access_token failed: {type(exc).__name__}: {exc}",
        )

    if token:
        return AdapterHealth(
            online=True,
            reason="get_access_token ok",
        )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="get_access_token returned empty",
    )
