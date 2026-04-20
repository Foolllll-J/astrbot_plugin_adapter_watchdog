from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.star import Context, Star


@dataclass(slots=True)
class AdapterHealth:
    online: bool
    reason: str
    user_id: str | None = None
    nickname: str | None = None


class AdapterWatchdogPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

        self._stop_event = asyncio.Event()
        self._monitor_task: asyncio.Task | None = None
        self._last_online: dict[str, bool] = {}
        self._last_user_ids: dict[str, str] = {}
        self._last_nicknames: dict[str, str] = {}

        self._monitored_adapters = [
            item.lower() for item in self._read_list("monitored_adapters")
        ]
        self._notify_targets = self._read_list("notify_targets")
        self._bark_url = str(self.config.get("bark_url", "") or "").strip()
        self._offline_reply = "" if (offline_reply := self.config.get("offline_reply")) is None else str(offline_reply).strip()
        self._online_reply = "" if (online_reply := self.config.get("online_reply")) is None else str(online_reply).strip()
        self._check_interval_seconds = self._read_check_interval_seconds()
        self._probe_timeout_seconds = 6
        self._offline_recheck_delay_seconds = 10
        self._enable_offline_recheck = (
            self._check_interval_seconds is not None
            and self._check_interval_seconds > 30
        )
        self._disable_reasons = self._build_disable_reasons()
        self._monitor_enabled = len(self._disable_reasons) == 0


    async def _prime_user_id_cache(self) -> None:
        await self._monitor_once(send_transition_notify=False)


    async def initialize(self) -> None:
        if not self._monitor_enabled:
            logger.warning(
                "[adapter_watchdog] 监控未启用。原因: %s",
                "; ".join(self._disable_reasons),
            )
            return

        logger.info(
            "[adapter_watchdog] 启动监控。adapters=%s interval=%ss targets=%s bark_url=%s",
            self._monitored_adapters if self._monitored_adapters else ["*"],
            self._check_interval_seconds,
            self._notify_targets,
            "已配置" if self._bark_url else "未配置",
        )
        self._stop_event.clear()
        await self._prime_user_id_cache()
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(),
            name="adapter_watchdog_monitor_loop",
        )

    async def terminate(self) -> None:
        self._stop_event.set()
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("平台状态", alias={"适配器状态"})
    async def watchdog_status(self, event: AstrMessageEvent):
        """立即刷新并查看当前监控状态"""
        try:
            await self._monitor_once(send_transition_notify=False)
        except Exception as exc:
            yield event.plain_result(f"[适配器看门狗] 刷新失败: {exc}")
            return
        yield event.plain_result(self._render_status_text())


    async def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._monitor_once(send_transition_notify=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("[adapter_watchdog] 监控循环异常: %s", exc, exc_info=True)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._check_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _monitor_once(self, send_transition_notify: bool = True) -> None:
        platform_insts = list(self.context.platform_manager.platform_insts)
        active_platform_ids: set[str] = set()

        for platform in platform_insts:
            meta = platform.meta()
            adapter_name = str(meta.name or "").strip()
            platform_id = str(meta.id or "").strip()
            if not platform_id:
                continue
            if self._monitored_adapters and adapter_name.lower() not in self._monitored_adapters:
                continue

            active_platform_ids.add(platform_id)
            has_cached_user_id = bool(self._last_user_ids.get(platform_id))
            health = await self._check_platform_health(platform, require_login_info=not has_cached_user_id)
            previous_online = self._last_online.get(platform_id)
            self._last_online[platform_id] = health.online

            if health.user_id:
                self._last_user_ids[platform_id] = health.user_id
                if health.nickname:
                    self._last_nicknames[platform_id] = health.nickname

            display_name = self._build_platform_display_name(
                platform_id=platform_id,
                adapter_name=adapter_name,
            )

            # 首次观测仅建立缓存基线，不发送告警。
            if previous_online is None:
                continue

            if previous_online == health.online:
                continue

            if send_transition_notify:
                final_health = health
                if previous_online and not health.online and self._enable_offline_recheck:
                    recheck_health = await self._recheck_offline_health(
                        platform=platform,
                        platform_id=platform_id,
                        adapter_name=adapter_name,
                        first_reason=health.reason,
                    )
                    if recheck_health is None:
                        continue
                    final_health = recheck_health
                    self._last_online[platform_id] = final_health.online
                    if final_health.user_id:
                        self._last_user_ids[platform_id] = final_health.user_id
                        if final_health.nickname:
                            self._last_nicknames[platform_id] = final_health.nickname
                        display_name = self._build_platform_display_name(
                            platform_id=platform_id,
                            adapter_name=adapter_name,
                        )

                if previous_online == final_health.online:
                    continue

                logger.info(
                    "[adapter_watchdog] 状态变化。platform_id=%s adapter=%s from=%s to=%s reason=%s",
                    platform_id,
                    adapter_name,
                    previous_online,
                    final_health.online,
                    final_health.reason,
                )
                await self._notify_transition(
                    platform_id=platform_id,
                    platform_name=adapter_name,
                    platform_label=display_name,
                    is_online=final_health.online,
                    user_id=self._last_user_ids.get(platform_id),
                )

        # 平台实例被移除或重载时，同步清理缓存。
        for platform_id in list(self._last_online.keys()):
            if platform_id not in active_platform_ids:
                self._last_online.pop(platform_id, None)
                self._last_user_ids.pop(platform_id, None)
                self._last_nicknames.pop(platform_id, None)

    async def _check_platform_health(self, platform: Any, require_login_info: bool = False) -> AdapterHealth:
        meta = platform.meta()
        adapter_name = str(meta.name or "").strip()

        status = getattr(platform, "status", None)
        status_name = str(getattr(status, "value", status) or "").lower()

        if status_name in {"error", "stopped"}:
            return AdapterHealth(online=False, reason=f"platform.status={status_name}")

        if adapter_name.lower() == "aiocqhttp":
            return await self._check_aiocqhttp_health(
                platform=platform,
                fallback_status=status_name,
                require_login_info=require_login_info,
            )

        if status_name == "running":
            return AdapterHealth(online=True, reason="platform.status=running")

        return AdapterHealth(
            online=False,
            reason=f"platform.status={status_name or 'unknown'}",
        )

    async def _check_aiocqhttp_health(
        self,
        platform: Any,
        fallback_status: str,
        require_login_info: bool = False,
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
                timeout=self._probe_timeout_seconds,
            )
        except asyncio.TimeoutError:
            status_ret = None
        except Exception as exc:
            status_ret = None

        online_by_status = self._extract_aiocqhttp_online(status_ret)
        if online_by_status is False:
            return AdapterHealth(online=False, reason="get_status online=false")

        if online_by_status is True and not require_login_info:
            return AdapterHealth(online=True, reason="get_status online=true")

        try:
            probe_ret = await asyncio.wait_for(
                client.call_action("get_login_info"),
                timeout=self._probe_timeout_seconds,
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
            user_id, nickname = self._extract_login_info_from_payload(probe_ret)
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

    def _extract_aiocqhttp_online(self, payload: Any) -> bool | None:
        """从 OneBot get_status 返回中提取 online 布尔值。"""
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

    def _extract_login_info_from_payload(self, payload: Any) -> tuple[str | None, str | None]:
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

    def _build_platform_display_name(
        self,
        *,
        platform_id: str,
        adapter_name: str,
    ) -> str:
        user_id = self._last_user_ids.get(platform_id)
        if not user_id:
            return adapter_name

        nickname = self._last_nicknames.get(platform_id)
        if nickname:
            return f"{nickname} ({user_id})"
        return user_id


    async def _recheck_offline_health(
        self,
        *,
        platform: Any,
        platform_id: str,
        adapter_name: str,
        first_reason: str,
    ) -> AdapterHealth | None:
        logger.info(
            "[adapter_watchdog] 检测到掉线，%ss后复核。platform_id=%s adapter=%s reason=%s",
            self._offline_recheck_delay_seconds,
            platform_id,
            adapter_name,
            first_reason,
        )
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=self._offline_recheck_delay_seconds,
            )
            logger.info(
                "[adapter_watchdog] 监控停止，取消掉线复核。platform_id=%s adapter=%s",
                platform_id,
                adapter_name,
            )
            return None
        except asyncio.TimeoutError:
            pass

        try:
            recheck_health = await self._check_platform_health(platform, require_login_info=not bool(self._last_user_ids.get(platform_id)))
        except Exception as exc:
            recheck_health = AdapterHealth(
                online=False,
                reason=f"recheck failed: {type(exc).__name__}: {exc}",
            )

        logger.debug(
            "[adapter_watchdog] 掉线复核结果。platform_id=%s adapter=%s online=%s reason=%s",
            platform_id,
            adapter_name,
            recheck_health.online,
            recheck_health.reason,
        )
        return recheck_health

    async def _notify_transition(
        self,
        *,
        platform_id: str,
        platform_name: str,
        platform_label: str,
        is_online: bool,
        user_id: str | None = None,
    ) -> None:
        if not self._notify_targets and not self._bark_url:
            return

        message_text = self._build_transition_message(
            platform_label=platform_label,
            is_online=is_online,
            adapter_name=platform_name,
        )

        for session in self._notify_targets:
            try:
                sent = await self.context.send_message(
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

        if self._bark_url:
            bark_text, bark_title = self._build_bark_transition_message(
                platform_label=platform_label,
                adapter_name=platform_name,
                is_online=is_online,
            )
            bark_success = await self._send_bark_notification(
                title=bark_title,
                text=bark_text,
                user_id=user_id,
            )
            if not bark_success:
                logger.error(
                    "[adapter_watchdog] Bark 通知发送失败。platform_id=%s adapter=%s",
                    platform_id,
                    platform_name,
                )

    def _build_transition_message(
        self,
        *,
        platform_label: str,
        is_online: bool,
        adapter_name: str,
    ) -> str:
        status_label = "恢复在线" if is_online else "掉线"
        status_text = self._online_reply if is_online else self._offline_reply

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

    def _build_bark_transition_message(
        self,
        *,
        platform_label: str,
        is_online: bool,
        adapter_name: str,
    ) -> tuple[str, str]:
        status_label = "恢复在线" if is_online else "掉线"
        status_text = self._online_reply if is_online else self._offline_reply
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


    async def _send_bark_notification(
        self,
        *,
        title: str,
        text: str,
        user_id: str | None = None,
    ) -> bool:
        if not self._bark_url:
            return False

        push_url = self._build_bark_url(title=title, text=text, user_id=user_id)
        try:
            success = await asyncio.to_thread(self._send_bark_request, push_url)
            return success
        except Exception as exc:
            logger.error(
                "[adapter_watchdog] Bark 通知异常。url=%s error=%s",
                push_url,
                exc,
                exc_info=True,
            )
            return False

    def _build_bark_url(
        self,
        *,
        title: str,
        text: str,
        user_id: str | None = None,
    ) -> str:
        title_enc = quote(title or "", safe="")
        text_enc = quote(text or "", safe="")
        base = self._bark_url.rstrip("/")

        icon_suffix = ""
        if user_id:
            avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
            icon_suffix = f"?{urlencode({'icon': avatar_url})}"

        if not title:
            return f"{base}/{text_enc}{icon_suffix}"
        return f"{base}/{title_enc}/{text_enc}{icon_suffix}"

    def _send_bark_request(self, url: str) -> bool:
        request = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                status = resp.getcode()
                return 200 <= status < 300
        except urllib.error.HTTPError as exc:
            return False
        except (OSError, urllib.error.URLError) as exc:
            return False


    def _read_list(self, key: str) -> list[str]:
        raw = self.config.get(key, [])
        if not isinstance(raw, list):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for item in raw:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _read_check_interval_seconds(self) -> int | None:
        raw = self.config.get("check_interval_seconds")
        if raw in (None, ""):
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        return max(value, 5)

    def _build_disable_reasons(self) -> list[str]:
        reasons: list[str] = []
        if not self._monitored_adapters:
            reasons.append("未选择监控适配器")
        if not self._notify_targets and not self._bark_url:
            reasons.append("未配置通知目标会话或Bark 推送地址")
        if self._check_interval_seconds is None:
            reasons.append("监控间隔为空或<=0")
        return reasons

    def _render_status_text(self) -> str:
        adapters = ", ".join(self._monitored_adapters) if self._monitored_adapters else "（未配置）"
        targets = ", ".join(self._notify_targets) if self._notify_targets else "（未配置）"
        interval_show = (
            str(self._check_interval_seconds)
            if self._check_interval_seconds is not None
            else "（未配置或<=0）"
        )
        enabled_label = "启用" if self._monitor_enabled else "停用"

        if not self._last_online:
            states = "（暂无缓存）"
        else:
            lines = []
            for platform_id, online in sorted(self._last_online.items()):
                lines.append(f"- {platform_id}: {'在线' if online else '离线'}")
            states = "\n".join(lines)

        return "\n".join(
            [
                "[适配器看门狗]",
                f"监控状态: {enabled_label}",
                f"监控适配器: {adapters}",
                f"监控间隔: {interval_show}",
                f"通知会话: {targets}",
                "当前状态:",
                states,
            ]
        )
