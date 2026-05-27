from __future__ import annotations

import asyncio
from typing import Any

from .base import AdapterHealth


async def check_aiocqhttp_health(
    *,
    platform: Any,
    fallback_status: str,
    require_login_info: bool = False,
    timeout_seconds: int = 6,
) -> AdapterHealth:
    client = platform.get_client()

    api_clients = getattr(client, "_wsr_api_clients", None)
    event_clients = getattr(client, "_wsr_event_clients", None)

    api_count = len(api_clients) if isinstance(api_clients, dict) else -1
    event_count = len(event_clients) if isinstance(event_clients, set) else -1

    if api_count == 0 or event_count == 0:
        return AdapterHealth(
            online=False,
            reason=f"reverse_ws_clients api={api_count} event={event_count}",
        )

    try:
        status_ret = await asyncio.wait_for(
            client.call_action("get_status"),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        status_ret = None
    except Exception:
        status_ret = None

    online_by_status = _extract_aiocqhttp_online(status_ret)
    if online_by_status is False:
        return AdapterHealth(online=False, reason="get_status online=false")

    if online_by_status is True and not require_login_info:
        return AdapterHealth(online=True, reason="get_status online=true")

    try:
        probe_ret = await asyncio.wait_for(
            client.call_action("get_login_info"),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        return AdapterHealth(
            online=False,
            reason="get_login_info timeout",
        )
    except Exception as exc:
        return AdapterHealth(
            online=False,
            reason=f"get_login_info failed: {type(exc).__name__}: {exc}",
        )

    if isinstance(probe_ret, dict):
        user_id, nickname = _extract_login_info_from_payload(probe_ret)
        if user_id:
            user_id_text = str(user_id)
            return AdapterHealth(
                online=True,
                reason=f"get_login_info ok user_id={user_id_text}",
                user_id=user_id_text,
                nickname=nickname,
            )

    if fallback_status == "running":
        return AdapterHealth(online=True, reason="fallback platform.status=running")

    return AdapterHealth(
        online=False,
        reason="get_login_info returned invalid payload",
    )


def _extract_aiocqhttp_online(payload: Any) -> bool | None:
    if not isinstance(payload, dict):
        return None

    target: dict[str, Any] = payload
    data = payload.get("data")
    if isinstance(data, dict):
        target = data

    online_raw = target.get("online")
    if isinstance(online_raw, bool):
        return online_raw
    if isinstance(online_raw, (int, float)):
        return bool(online_raw)
    if isinstance(online_raw, str):
        text = online_raw.strip().lower()
        if text in {"true", "1", "yes", "online"}:
            return True
        if text in {"false", "0", "no", "offline"}:
            return False
    return None


def _extract_login_info_from_payload(
    payload: Any,
) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None

    source: dict[str, Any] = payload
    data = payload.get("data")
    if isinstance(data, dict):
        source = data

    user_id = source.get("user_id")
    if user_id is not None and not isinstance(user_id, str):
        user_id = str(user_id)

    nickname = source.get("nickname")
    if isinstance(nickname, str):
        nickname = nickname.strip()
    if not nickname:
        nickname = None

    if user_id:
        return str(user_id).strip(), nickname
    return None, nickname
