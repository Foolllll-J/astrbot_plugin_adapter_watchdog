from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode


async def send_serverchan_notification(
    *,
    send_key: str,
    title: str,
    body: str,
    logger: Any,
) -> bool:
    if not send_key:
        return False

    data_bytes = urlencode({"title": title, "desp": body}).encode("utf-8")
    url = f"https://sctapi.ftqq.com/{send_key}.send"

    try:
        resp_data = await asyncio.to_thread(_do_request, url, data_bytes)
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] Server酱 通知异常。error=%s",
            exc,
            exc_info=True,
        )
        return False

    if resp_data is None:
        logger.error(
            "[adapter_watchdog] Server酱 请求失败（无响应）",
        )
        return False

    if not isinstance(resp_data, dict):
        logger.error(
            "[adapter_watchdog] Server酱 响应格式异常: %s",
            resp_data,
        )
        return False

    code = resp_data.get("code")
    if code == 0:
        return True

    data = resp_data.get("data")
    if isinstance(data, dict) and data.get("pushid"):
        return True

    pushid = resp_data.get("pushid")
    if pushid:
        return True

    err_msg = resp_data.get("message", resp_data.get("error", "未知错误"))
    logger.error(
        "[adapter_watchdog] Server酱 推送失败。code=%s message=%s",
        code,
        err_msg,
    )
    return False


def _do_request(url: str, data: bytes | None = None) -> dict | None:
    request = urllib.request.Request(url=url, data=data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
