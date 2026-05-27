<div align="center">

# 🚨 适配器看门狗

<i>🐶 连接有迹，掉线有警</i>

![License](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white)
![AstrBot](https://img.shields.io/badge/framework-AstrBot-ff6b6b?style=flat-square)

</div>

## ✨ 简介

一款为 [**AstrBot**](https://github.com/AstrBotDevs/AstrBot) 设计的平台适配器状态监控插件。用于监控指定适配器是否在线，并在**掉线/恢复**时发送通知，方便你第一时间感知协议端状态变化。

---

## 📌 使用须知

| 项目 | 描述 |
| :--- | :--- |
| **监控对象** | 监控当前已加载的平台适配器实例。 |
| **通知方式** | 状态变化时会尝试向配置的会话、Bark、邮箱推送通知。 |
| **触发时机** | 仅在状态发生变化时通知，首次观测只建立基线不告警。 |

> [!IMPORTANT]
> - 目前仅在 `aiocqhttp` 与 `telegram` 平台实测过掉线与恢复通知，其他协议端未进行验证。  
> - Bark 推送可参考 [官方文档](https://bark.day.app/#/?id=bark>)。 

> [!TIP] 
> Bark 默认会使用当前 QQ 登录账号头像作为通知图标。  

---

## 🛠 配置说明

首次加载后，请在 AstrBot 后台 -> 插件 页面找到本插件进行设置。所有配置项都有详细的说明和介绍。

> [!TIP]
> 自定义的通知文案支持英文冒号 `:` 语法：`标题:正文`，用于为 Bark 通知设置标题。

---

## 📝 更新日志

详见 [CHANGELOG](CHANGELOG.md)

---

## ❤️ 支持

- [AstrBot 帮助文档](https://astrbot.app)
- 如果你在使用中遇到问题，欢迎在本仓库提交 [Issue](https://github.com/Foolllll-J/astrbot_plugin_adapter_watchdog/issues)。

---

<div align="center">

**如果这个插件对你有帮助，欢迎点一个 ⭐ Star 支持一下！**

</div>
