from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_telegram_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    client = platform.get_client()

    try:
        me = await asyncio.wait_for(
            client.get_me(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(online=False, reason="get_me timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"get_me failed: {type(exc).__name__}: {exc}",
        )

    user_id = getattr(me, "id", None)
    username = getattr(me, "username", None)
    full_name = getattr(me, "full_name", None)
    nickname = _pick_telegram_nickname(
        full_name=full_name,
        username=username,
    )

    if user_id is not None:
        return AdapterHealth(
            online=True,
            reason=f"get_me ok user_id={user_id}",
            user_id=str(user_id),
            nickname=nickname,
        )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="get_me returned invalid payload",
    )


def _pick_telegram_nickname(
    *,
    full_name: Any,
    username: Any,
) -> str | None:
    if isinstance(full_name, str):
        full_name = full_name.strip()
    else:
        full_name = ""

    if isinstance(username, str):
        username = username.strip()
    else:
        username = ""

    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return None
