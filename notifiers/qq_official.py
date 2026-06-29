from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any

_API_BASE = "https://api.sgroup.qq.com"
_URL_TOKEN = "https://bots.qq.com/app/getAppAccessToken"

_token_cache: dict[str, tuple[str, float]] = {}


async def send_qq_official_notification(
    *,
    appid: str,
    appsecret: str,
    user_openids: list[str],
    group_openids: list[str],
    title: str,
    body: str,
    logger: Any,
) -> bool:
    if not appid or not appsecret:
        return False
    if not user_openids and not group_openids:
        return False

    token = await _get_access_token(appid, appsecret, logger)
    if not token:
        logger.error("[adapter_watchdog] QQ官方机器人 获取 access_token 失败。")
        return False

    content = f"{title}\n\n{body}"
    tasks = []

    for openid in user_openids:
        tasks.append(
            _send_user_message(token, openid, content, logger),
        )
    for openid in group_openids:
        tasks.append(
            _send_group_message(token, openid, content, logger),
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return any(r is True for r in results)


async def _get_access_token(appid: str, appsecret: str, logger: Any) -> str | None:
    cache_key = f"{appid}:{appsecret}"
    cached = _token_cache.get(cache_key)
    if cached:
        token, expires_at = cached
        if time.time() < expires_at - 60:
            return token

    try:
        result = await asyncio.to_thread(
            _do_get_token, appid, appsecret,
        )
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] QQ官方机器人 获取 token 异常。error=%s",
            exc,
            exc_info=True,
        )
        return None

    if not result:
        return None

    token = result.get("access_token")
    if not token:
        return None

    try:
        expires_in = int(result.get("expires_in", 7200))
    except (TypeError, ValueError):
        expires_in = 7200

    _token_cache[cache_key] = (token, time.time() + expires_in)
    return token


def _do_get_token(appid: str, appsecret: str) -> dict | None:
    payload = json.dumps(
        {"appId": appid, "clientSecret": appsecret},
    ).encode("utf-8")
    request = urllib.request.Request(url=_URL_TOKEN, data=payload, method="POST")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


async def _send_user_message(token: str, openid: str, content: str, logger: Any) -> bool:
    url = f"{_API_BASE}/v2/users/{openid}/messages"
    payload = json.dumps(
        {"content": content, "msg_type": 0},
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        success = await asyncio.to_thread(_do_send_message, url, token, payload)
        if not success:
            logger.warning(
                "[adapter_watchdog] QQ官方机器人 用户消息发送失败。openid=%s", openid,
            )
        return success
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] QQ官方机器人 用户消息异常。openid=%s error=%s",
            openid,
            exc,
            exc_info=True,
        )
        return False


async def _send_group_message(token: str, openid: str, content: str, logger: Any) -> bool:
    url = f"{_API_BASE}/v2/groups/{openid}/messages"
    payload = json.dumps(
        {"content": content, "msg_type": 0},
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        success = await asyncio.to_thread(_do_send_message, url, token, payload)
        if not success:
            logger.warning(
                "[adapter_watchdog] QQ官方机器人 群消息发送失败。openid=%s", openid,
            )
        return success
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] QQ官方机器人 群消息异常。openid=%s error=%s",
            openid,
            exc,
            exc_info=True,
        )
        return False


def _do_send_message(url: str, token: str, payload: bytes) -> bool:
    request = urllib.request.Request(url=url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    request.add_header("Authorization", f"QQBot {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return 200 <= resp.getcode() < 300
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        return False
    except (urllib.error.URLError, OSError):
        return False
