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
| **监控对象** | 监控当前已加载的平台适配器实例。 |
| **通知方式** | 状态变化时向配置的所有会话尝试主动发送。 |
| **触发时机** | 仅在状态发生变化时通知，首次观测只建立基线不告警。 |


> [!IMPORTANT]
> 目前仅在 NapCat 场景下实测过掉线与恢复通知，其他协议端未进行验证。  

---

## 🛠 配置说明

本插件使用以下 5 个配置项：

| 配置项 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| **`monitored_adapters`** | `list[str]` | `["aiocqhttp"]` | 要监控的适配器类型；留空表示不监控。 |
| **`check_interval_seconds`** | `int` | `300` | 轮询间隔（秒），最小 5 秒；配置为 `0` 或留空表示不监控。 |
| **`notify_targets`** | `list[str]` | `[]` | 通知目标会话 sid 列表；留空表示不监控。 |
| **`offline_reply`** | `str` | `[]` | 当适配器掉线通知时使用的自定义文案。留空则使用默认文案。 |
| **`online_reply`** | `str` | `[]` | 当适配器恢复在线时使用的自定义文案。留空则使用默认文案。 |

---

## ❤️ 支持

- [AstrBot 帮助文档](https://astrbot.app)
- 如果你在使用中遇到问题，欢迎在本仓库提交 [Issue](https://github.com/Foolllll-J/astrbot_plugin_adapter_watchdog/issues)。

---

<div align="center">

**如果这个插件对你有帮助，欢迎点一个 ⭐ Star 支持一下！**

</div>
