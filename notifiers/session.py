from __future__ import annotations

from typing import Any

from astrbot.api.event import MessageEventResult


async def send_session_notifications(
    context: Any,
    sessions: list[str],
    message_text: str,
    logger: Any,
) -> None:
    for session in sessions:
        try:
            sent = await context.send_message(
                session,
                MessageEventResult().message(message_text),
            )
            if not sent:
                logger.warning(
                    "[adapter_watchdog] 通知失败，未找到会话对应的平台实例。session=%s",
                    session,
                )
        except Exception as exc:
            logger.error(
                "[adapter_watchdog] 通知发送异常。session=%s error=%s",
                session,
                exc,
                exc_info=True,
            )
