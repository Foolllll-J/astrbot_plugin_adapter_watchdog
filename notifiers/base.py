from __future__ import annotations


def build_transition_text(
    *,
    platform_label: str,
    is_online: bool,
    adapter_name: str,
    offline_reply: str,
    online_reply: str,
) -> str:
    status_label = "恢复在线" if is_online else "掉线"
    status_text = online_reply if is_online else offline_reply

    if not status_text:
        return "\n".join(
            [
                "[适配器恢复通知]" if is_online else "[适配器掉线通知]",
                f"{platform_label} {status_label}",
                f"适配器类型：{adapter_name}",
            ]
        )

    colon_pos = status_text.find(":")
    if colon_pos == -1:
        return status_text

    custom_title = status_text[:colon_pos].strip()
    custom_text = status_text[colon_pos + 1 :].lstrip()
    if not custom_title:
        return status_text
    return custom_text


def build_bark_title_body(
    *,
    platform_label: str,
    is_online: bool,
    adapter_name: str,
    offline_reply: str,
    online_reply: str,
) -> tuple[str, str]:
    status_label = "恢复在线" if is_online else "掉线"
    status_text = online_reply if is_online else offline_reply
    bark_title = f"适配器{status_label}"

    if not status_text:
        text = "\n".join(
            [
                f"{platform_label} {status_label}",
                f"适配器类型：{adapter_name}",
            ]
        )
        return text, bark_title

    colon_pos = status_text.find(":")
    if colon_pos == -1:
        return status_text, bark_title

    custom_title = status_text[:colon_pos].strip()
    custom_text = status_text[colon_pos + 1 :].lstrip()
    if not custom_title:
        return status_text, bark_title
    return custom_text, custom_title
