from __future__ import annotations

import asyncio
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.star import Context, Star

from .checkers import (
    AdapterHealth,
    check_aiocqhttp_health,
    check_telegram_health,
    check_misskey_health,
    check_slack_health,
    check_kook_health,
    check_discord_health,
    check_satori_health,
    check_lark_health,
    check_dingtalk_health,
)
from .notifiers import notify_transition, SmtpConfig


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

        notifier_cfg = self.config.get("notifier", {}) or {}
        self._notify_targets = self._read_list("notify_targets", source=notifier_cfg)
        self._bark_url = str(notifier_cfg.get("bark_url", "") or "").strip()
        email_cfg = notifier_cfg.get("email", {}) or {}
        self._smtp_config = self._read_smtp_config(email_cfg)
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
            return await check_aiocqhttp_health(
                platform=platform,
                fallback_status=status_name,
                require_login_info=require_login_info,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "telegram":
            return await check_telegram_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "misskey":
            return await check_misskey_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "slack":
            return await check_slack_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "kook":
            return await check_kook_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "discord":
            return await check_discord_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "satori":
            return await check_satori_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "lark":
            return await check_lark_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if adapter_name.lower() == "dingtalk":
            return await check_dingtalk_health(
                platform=platform,
                fallback_status=status_name,
                timeout_seconds=self._probe_timeout_seconds,
            )

        if status_name == "running":
            return AdapterHealth(online=True, reason="platform.status=running")

        return AdapterHealth(
            online=False,
            reason=f"platform.status={status_name or 'unknown'}",
        )

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
        await notify_transition(
            self.context,
            notify_targets=self._notify_targets,
            bark_url=self._bark_url,
            smtp_config=self._smtp_config,
            user_id=user_id,
            offline_reply=self._offline_reply,
            online_reply=self._online_reply,
            platform_label=platform_label,
            adapter_name=platform_name,
            is_online=is_online,
            logger=logger,
        )


    def _read_smtp_config(self, email_cfg: dict) -> SmtpConfig | None:
        host = str(email_cfg.get("smtp_host", "") or "").strip()
        if not host:
            return None
        try:
            port = int(email_cfg.get("smtp_port", 465))
        except (TypeError, ValueError):
            port = 465
        use_tls = bool(email_cfg.get("smtp_use_tls", True))
        user = str(email_cfg.get("smtp_user", "") or "").strip()
        password = str(email_cfg.get("smtp_password", "") or "")
        sender = str(email_cfg.get("email_from", "") or "").strip()
        raw_recipients = email_cfg.get("email_to", [])
        if isinstance(raw_recipients, str):
            raw_recipients = [raw_recipients]
        recipients = [
            str(r).strip() for r in raw_recipients if isinstance(r, str) and r.strip()
        ]
        if not recipients:
            return None
        return SmtpConfig(
            host=host,
            port=port,
            use_tls=use_tls,
            user=user,
            password=password,
            sender=sender or user,
            recipients=recipients,
        )

    def _read_list(self, key: str, source: dict | None = None) -> list[str]:
        raw = (source or self.config).get(key, [])
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
        has_any_notifier = bool(
            self._notify_targets or self._bark_url or self._smtp_config
        )
        if not has_any_notifier:
            reasons.append("未配置任何通知渠道（会话/Bark/邮件）")
        if self._check_interval_seconds is None:
            reasons.append("监控间隔为空或<=0")
        return reasons

    def _render_status_text(self) -> str:
        adapters = ", ".join(self._monitored_adapters) if self._monitored_adapters else "（未配置）"
        interval_show = (
            str(self._check_interval_seconds)
            if self._check_interval_seconds is not None
            else "（未配置或<=0）"
        )
        enabled_label = "启用" if self._monitor_enabled else "停用"

        channels = []
        if self._notify_targets:
            sessions = ", ".join(self._notify_targets)
            channels.append(f"会话({sessions})")
        else:
            channels.append("会话(未配置)")
        channels.append("Bark(已启用)" if self._bark_url else "Bark(未配置)")
        channels.append("邮件(已启用)" if self._smtp_config else "邮件(未配置)")
        channels_str = " / ".join(channels)

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
                f"监控间隔: {interval_show}s",
                f"通知渠道: {channels_str}",
                "当前状态:",
                states,
            ]
        )
