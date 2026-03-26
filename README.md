<div align="center">

# 🚨 适配器看门狗

<i>🐶 连接有迹，掉线有警</i>

![License](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white)
![AstrBot](https://img.shields.io/badge/framework-AstrBot-ff6b6b?style=flat-square)

</div>

## ✨ 简介

一款为 [**AstrBot**](https://github.com/AstrBotDevs/AstrBot) 设计的平台适配器状态监控插件。用于监控指定适配器是否在线，并在**掉线/恢复**时向指定会话发送通知，方便你第一时间感知协议端状态变化（如 NapCat 被踢下线）。

---

## 📌 使用须知

| 项目 | 描述 |
| :--- | :--- |
| **监控对象** | 监控 AstrBot 当前已加载的平台适配器实例。 |
| **通知方式** | 状态变化时向 `notify_targets` 中的所有 sid 尝试主动发送。 |
| **触发时机** | 仅在状态发生变化时通知，首次观测只建立基线不告警。 |
| **特殊适配** | 对 `aiocqhttp` 额外调用 `get_login_info` 探测，提高离线识别准确性。 |

---

## 🛠 配置说明

本插件仅使用 3 个配置项：

| 配置项 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| **`monitored_adapters`** | `list[str]` | `["aiocqhttp"]` | 要监控的适配器类型；留空表示不监控。 |
| **`check_interval_seconds`** | `int` | `300` | 轮询间隔（秒），最小 5 秒；配置为 `0` 或留空表示不监控。 |
| **`notify_targets`** | `list[str]` | `[]` | 通知目标会话 sid 列表；留空表示不监控。 |

---

## 🎯 指令说明

| 指令 | 参数 | 描述 |
| :--- | :--- | :--- |
| **`adapter_watchdog_status`** | 无 | 查看插件启用状态、停用原因、监控配置和最近缓存状态。 |

---

## ⚠️ 已知限制

- AstrBot 当前没有直接暴露“适配器掉线事件”给插件，故采用轮询检测机制。
- 非 `aiocqhttp` 适配器主要依赖 `platform.status`，静默断链场景可能存在延迟识别。
- 若目标 sid 对应平台不支持主动发送，发送会失败并记录日志，但不会影响其他目标会话。

---

## ❤️ 支持

- [AstrBot 帮助文档](https://astrbot.app)
- 如果你在使用中遇到问题，欢迎在本仓库提交 [Issue](https://github.com/Foolllll-J/astrbot_plugin_/issues)。

---

<div align="center">

**如果这个插件对你有帮助，欢迎点一个 ⭐ Star 支持一下！**

</div>

