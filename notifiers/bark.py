from __future__ import annotations

import asyncio
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode


def _build_bark_url(
    *,
    bark_url: str,
    title: str,
    text: str,
    user_id: str | None = None,
    adapter_name: str | None = None,
) -> str:
    title_enc = quote(title or "", safe="")
    text_enc = quote(text or "", safe="")
    base = bark_url.rstrip("/")

    icon_suffix = ""
    if user_id and adapter_name == "aiocqhttp":
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        icon_suffix = f"?{urlencode({'icon': avatar_url})}"

    if not title:
        return f"{base}/{text_enc}{icon_suffix}"
    return f"{base}/{title_enc}/{text_enc}{icon_suffix}"


def _send_bark_request(url: str) -> bool:
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            status = resp.getcode()
            return 200 <= status < 300
    except urllib.error.HTTPError:
        return False
    except (OSError, urllib.error.URLError):
        return False


async def send_bark_notification(
    *,
    bark_url: str,
    title: str,
    text: str,
    user_id: str | None = None,
    adapter_name: str | None = None,
    logger: Any,
) -> bool:
    if not bark_url:
        return False

    push_url = _build_bark_url(
        bark_url=bark_url,
        title=title,
        text=text,
        user_id=user_id,
        adapter_name=adapter_name,
    )
    try:
        success = await asyncio.to_thread(_send_bark_request, push_url)
        return success
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] Bark 通知异常。url=%s error=%s",
            push_url,
            exc,
            exc_info=True,
        )
        return False
