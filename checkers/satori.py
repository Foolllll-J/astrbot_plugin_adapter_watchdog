from __future__ import annotations

from typing import Any

from .base import AdapterHealth


async def check_satori_health(
    *,
    platform: Any,
    fallback_status: str,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    running = getattr(platform, "running", False)
    if not running:
        return AdapterHealth(online=False, reason="adapter not running")

    if not getattr(platform, "ready_received", False):
        return AdapterHealth(online=False, reason="ready not received")

    ws = getattr(platform, "ws", None)
    ws_closed = True
    if ws is not None:
        try:
            ws_closed = bool(
                getattr(ws, "closed", getattr(ws, "close_code", None) is not None)
            )
        except AttributeError:
            ws_closed = True
    if ws_closed:
        return AdapterHealth(online=False, reason="websocket closed")

    logins = getattr(platform, "logins", [])
    if logins and isinstance(logins, list):
        login = logins[0]
        if isinstance(login, dict):
            user = login.get("user") or {}
            user_id = user.get("id") if isinstance(user, dict) else None
            nickname = user.get("name") if isinstance(user, dict) else None
            if user_id:
                return AdapterHealth(
                    online=True,
                    reason=f"connected via satori user_id={user_id}",
                    user_id=str(user_id),
                    nickname=nickname,
                )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="no login info from ready frame",
    )
