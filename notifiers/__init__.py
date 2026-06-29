from __future__ import annotations

from typing import Any

from .base import build_transition_text, build_bark_title_body
from .session import send_session_notifications
from .bark import send_bark_notification
from .email import send_email_notification, SmtpConfig
from .serverchan import send_serverchan_notification
from .webhook import send_webhook_notification
from .qq_official import send_qq_official_notification


async def notify_transition(
    context: Any,
    *,
    notify_targets: list[str],
    bark_url: str,
    serverchan_key: str,
    smtp_config: SmtpConfig | None,
    webhook_urls: list[str] | None = None,
    qq_official_appid: str = "",
    qq_official_appsecret: str = "",
    qq_official_user_openids: list[str] | None = None,
    qq_official_group_openids: list[str] | None = None,
    user_id: str | None,
    offline_reply: str,
    online_reply: str,
    platform_label: str,
    adapter_name: str,
    platform_id: str,
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
        _targets = notify_targets
        if not is_online:
            _targets = [
                s for s in notify_targets
                if not s.startswith(f"{platform_id}:")
            ]
        if _targets:
            await send_session_notifications(context, _targets, message_text, logger)
        elif notify_targets and not _targets:
            logger.info(
                "[adapter_watchdog] 所有通知目标会话均属于已离线的 %s 适配器，跳过会话通知。",
                adapter_name,
            )

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

    if serverchan_key:
        status_label = "恢复在线" if is_online else "掉线"
        sc_title = f"[适配器{status_label}] {platform_label}"
        sc_success = await send_serverchan_notification(
            send_key=serverchan_key,
            title=sc_title,
            body=message_text,
            logger=logger,
        )
        if not sc_success:
            logger.error(
                "[adapter_watchdog] Server酱 通知发送失败。adapter=%s",
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

    status_label = "恢复在线" if is_online else "掉线"
    webhook_status = status_label

    if webhook_urls:
        wh_success = await send_webhook_notification(
            webhook_urls=webhook_urls,
            title=f"[适配器{webhook_status}] {platform_label}",
            body=message_text,
            status="online" if is_online else "offline",
            platform=platform_label,
            adapter_name=adapter_name,
            logger=logger,
        )
        if not wh_success:
            logger.error(
                "[adapter_watchdog] Webhook 通知发送失败。adapter=%s",
                adapter_name,
            )

    if qq_official_appid and qq_official_appsecret and (
        qq_official_user_openids or qq_official_group_openids
    ):
        qq_success = await send_qq_official_notification(
            appid=qq_official_appid,
            appsecret=qq_official_appsecret,
            user_openids=qq_official_user_openids or [],
            group_openids=qq_official_group_openids or [],
            title=f"[适配器{webhook_status}] {platform_label}",
            body=message_text,
            logger=logger,
        )
        if not qq_success:
            logger.error(
                "[adapter_watchdog] QQ官方机器人 通知发送失败。adapter=%s",
                adapter_name,
            )


__all__ = [
    "notify_transition",
    "SmtpConfig",
    "send_session_notifications",
    "send_bark_notification",
    "send_email_notification",
    "send_webhook_notification",
    "send_qq_official_notification",
]
