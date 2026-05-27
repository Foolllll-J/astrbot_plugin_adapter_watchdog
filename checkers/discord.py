from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_discord_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    client = getattr(platform, "client", None)
    if client is None:
        return AdapterHealth(online=False, reason="no discord client attr")

    if not client.is_ready():
        return AdapterHealth(online=False, reason="client not ready")

    user = client.user
    if user is not None:
        user_id = str(user.id)
        nickname = str(user)
        return AdapterHealth(
            online=True,
            reason=f"client.user available id={user_id}",
            user_id=user_id,
            nickname=nickname,
        )

    try:
        app_info = await asyncio.wait_for(
            client.application_info(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        if fallback_status == "running":
            return AdapterHealth(online=True, reason="fallback platform.status=running")
        return AdapterHealth(online=False, reason="application_info timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"application_info failed: {type(exc).__name__}: {exc}",
        )

    bot_id = str(app_info.id) if hasattr(app_info, "id") else None
    bot_name = str(app_info.name) if hasattr(app_info, "name") else None

    if bot_id:
        return AdapterHealth(
            online=True,
            reason=f"application_info ok id={bot_id}",
            user_id=bot_id,
            nickname=bot_name,
        )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="application_info returned no id",
    )
