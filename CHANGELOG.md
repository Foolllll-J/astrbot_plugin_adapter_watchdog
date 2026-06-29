# 📅 更新日志

## v1.3 (2026-06-29)

- 新增 通用 Webhook 通知渠道。
- 新增 QQ 官方机器人通知渠道。

## v1.2 (2026-05-27)

- 重构：将检测逻辑抽离为 `checkers/` 模块。
  - 新增 telegram、misskey、slack、kook、discord、satori、lark、dingtalk 适配器检测器。
  - 从 `monitored_adapters` 移除纯 webhook 平台。
- 重构：将通知逻辑抽离为 `notifiers/` 模块。
  - 新增 SMTP 邮件通知渠道。
  - 新增 Server酱 通知渠道。
  - 通知配置统一纳入 `notifier` 对象。
- 修复：Bark 通知图标仅在 aiocqhttp 平台时追加 QQ 头像。

## v1.1 (2026-04-19)

- 新增 Bark 通知渠道。
- 新增 自定义通知文案。

## v1.0

- 初始版本发布。
- 支持在适配器掉线或恢复时向指定会话发送通知。
