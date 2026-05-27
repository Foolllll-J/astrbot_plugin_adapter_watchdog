from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_slack_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    client = platform.get_client()

    try:
        auth_info = await asyncio.wait_for(
            client.auth_test(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(online=False, reason="auth_test timeout")
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"auth_test failed: {type(exc).__name__}: {exc}",
        )

    if isinstance(auth_info, dict):
        user_id = auth_info.get("user_id")
        team = auth_info.get("team")
        if user_id:
            return AdapterHealth(
                online=True,
                reason=f"auth_test ok user_id={user_id}",
                user_id=str(user_id),
                nickname=team,
            )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="auth_test returned invalid payload",
    )
