from __future__ import annotations

from typing import Any

from .base import build_transition_text, build_bark_title_body
from .session import send_session_notifications
from .bark import send_bark_notification
from .email import send_email_notification, SmtpConfig


async def notify_transition(
    context: Any,
    *,
    notify_targets: list[str],
    bark_url: str,
    smtp_config: SmtpConfig | None,
    user_id: str | None,
    offline_reply: str,
    online_reply: str,
    platform_label: str,
    adapter_name: str,
    is_online: bool,
    logger: Any,
) -> None:
    message_text = build_transition_text(
        platform_label=platform_label,
        is_online=is_online,
        adapter_name=adapter_name,
        offline_reply=offline_reply,
        online_reply=online_reply,
    )

    if notify_targets:
        await send_session_notifications(context, notify_targets, message_text, logger)

    if bark_url:
        bark_text, bark_title = build_bark_title_body(
            platform_label=platform_label,
            is_online=is_online,
            adapter_name=adapter_name,
            offline_reply=offline_reply,
            online_reply=online_reply,
        )
        bark_success = await send_bark_notification(
            bark_url=bark_url,
            title=bark_title,
            text=bark_text,
            user_id=user_id,
            adapter_name=adapter_name,
            logger=logger,
        )
        if not bark_success:
            logger.error(
                "[adapter_watchdog] Bark 通知发送失败。adapter=%s",
                adapter_name,
            )

    if smtp_config:
        status_label = "恢复在线" if is_online else "掉线"
        subject = f"[适配器{status_label}] {platform_label}"
        email_success = await send_email_notification(
            config=smtp_config,
            subject=subject,
            body=message_text,
            logger=logger,
        )
        if not email_success:
            logger.error(
                "[adapter_watchdog] 邮件通知发送失败。adapter=%s",
                adapter_name,
            )


__all__ = [
    "notify_transition",
    "SmtpConfig",
    "send_session_notifications",
    "send_bark_notification",
    "send_email_notification",
]
