from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any


async def send_webhook_notification(
    *,
    webhook_urls: list[str],
    title: str,
    body: str,
    status: str,
    platform: str,
    adapter_name: str,
    logger: Any,
) -> bool:
    if not webhook_urls:
        return False

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "status": status,
            "platform": platform,
            "adapter": adapter_name,
            "timestamp": time.time(),
        },
        ensure_ascii=False,
    ).encode("utf-8")

    results = await asyncio.gather(
        *[_post_webhook(url, payload, logger) for url in webhook_urls],
        return_exceptions=True,
    )
    return any(r is True for r in results)


async def _post_webhook(url: str, payload: bytes, logger: Any) -> bool:
    try:
        success = await asyncio.to_thread(_do_post, url, payload)
        if not success:
            logger.warning(
                "[adapter_watchdog] Webhook 请求失败。url=%s", url,
            )
        return success
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] Webhook 通知异常。url=%s error=%s",
            url,
            exc,
            exc_info=True,
        )
        return False


def _do_post(url: str, payload: bytes) -> bool:
    request = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
    )
    request.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return 200 <= resp.getcode() < 300
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False
