from __future__ import annotations

import asyncio
from typing import Any

from astrbot.core.platform.sources.lark.bot_info import request_lark_bot_info

from .base import AdapterHealth


async def check_lark_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    if getattr(platform, "connection_mode", "") == "socket":
        client = getattr(platform, "client", None)
        if client is not None:
            conn = getattr(client, "_conn", None)
            if conn is None:
                return AdapterHealth(
                    online=False, reason="websocket client not connected"
                )

    try:
        bot_info = await asyncio.wait_for(
            request_lark_bot_info(
                domain=platform.domain,
                app_id=platform.appid,
                app_secret=platform.appsecret,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(online=False, reason="request_bot_info timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"request_bot_info failed: {type(exc).__name__}: {exc}",
        )

    if bot_info.open_id:
        return AdapterHealth(
            online=True,
            reason=f"request_bot_info ok open_id={bot_info.open_id}",
            user_id=bot_info.open_id,
            nickname=bot_info.app_name or None,
        )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="request_bot_info returned no open_id",
    )
