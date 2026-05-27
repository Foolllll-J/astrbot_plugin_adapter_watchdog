from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_misskey_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    client = platform.get_client()

    try:
        user_info = await asyncio.wait_for(
            client.get_current_user(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(online=False, reason="get_current_user timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"get_current_user failed: {type(exc).__name__}: {exc}",
        )

    if isinstance(user_info, dict):
        user_id = user_info.get("id")
        username = user_info.get("username")
        name = user_info.get("name")
        nickname = name or username
        if user_id:
            return AdapterHealth(
                online=True,
                reason=f"get_current_user ok id={user_id}",
                user_id=str(user_id),
                nickname=nickname,
            )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="get_current_user returned invalid payload",
    )
