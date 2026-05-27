from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_kook_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    client = getattr(platform, "client", None)
    if client is None:
        return AdapterHealth(online=False, reason="no kook client attr")

    if not getattr(client, "running", False):
        return AdapterHealth(online=False, reason="client not running")

    if getattr(client, "ws", None) is None:
        return AdapterHealth(online=False, reason="ws not connected")

    try:
        await asyncio.wait_for(
            client.get_bot_info(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(online=False, reason="get_bot_info timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"get_bot_info failed: {type(exc).__name__}: {exc}",
        )

    bot_id = getattr(client, "bot_id", None)
    if bot_id:
        nickname = getattr(client, "bot_nickname", None)
        return AdapterHealth(
            online=True,
            reason=f"get_bot_info ok user_id={bot_id}",
            user_id=str(bot_id),
            nickname=nickname,
        )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="get_bot_info returned no bot_id",
    )
