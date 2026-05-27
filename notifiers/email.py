from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any


@dataclass
class SmtpConfig:
    host: str = ""
    port: int = 465
    use_tls: bool = True
    user: str = ""
    password: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)


def _send_email_sync(config: SmtpConfig, subject: str, body: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.sender
    msg["To"] = ", ".join(config.recipients)
    msg.set_content(body, charset="utf-8")

    if config.use_tls:
        with smtplib.SMTP_SSL(config.host, config.port, timeout=15) as server:
            if config.user:
                server.login(config.user, config.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(config.host, config.port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if config.user:
                server.login(config.user, config.password)
            server.send_message(msg)

    return True


async def send_email_notification(
    *,
    config: SmtpConfig | None,
    subject: str,
    body: str,
    logger: Any,
) -> bool:
    if not config or not config.host or not config.recipients:
        return False

    try:
        await asyncio.to_thread(_send_email_sync, config, subject, body)
        return True
    except smtplib.SMTPException as exc:
        logger.error(
            "[adapter_watchdog] 邮件通知 SMTP 异常。host=%s error=%s",
            config.host,
            exc,
            exc_info=True,
        )
    except OSError as exc:
        logger.error(
            "[adapter_watchdog] 邮件通知网络异常。host=%s error=%s",
            config.host,
            exc,
            exc_info=True,
        )
    except Exception as exc:
        logger.error(
            "[adapter_watchdog] 邮件通知异常。host=%s error=%s",
            config.host,
            exc,
            exc_info=True,
        )
    return False
