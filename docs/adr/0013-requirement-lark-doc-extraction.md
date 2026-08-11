# ADR-0013: 飞书文档经 lark-cli 提取正文，每用户授权 + 失败降级手动粘贴

## Status

Accepted (更新于 2026-08-10：鉴权模型由共享账号改为每用户 token)

## Context

需求来源支持「粘贴飞书文档链接」。飞书文档（docx/wiki）受登录权限保护，无法从后端直接 HTTP 抓取。开发/部署环境已具备 `lark-cli`（v1.0.81，`/usr/local/bin/lark-cli`，appId `cli_aadf15eaa478dcb6`，appSecret 存 keychain，user token 通过 Device Flow 授权），支持读取飞书文档正文，与本环境 lark-doc skill 的路由逻辑一致。

鉴权现实：user token 为短期授权（refresh token 约 7 天），过期后需重新 Device Flow 登录；生产服务器无法人工扫码。同时考虑两个候选方案：

- **每用户独立 user token**：lark-cli 原生支持多用户（`auth list` users 数组、`defaultAs: auto`），`auth login --no-wait --json` + `--device-code` 两段式可在前端完成授权
- **app 凭证 tenant_access_token**：应用级单一身份，无人工，但存在用户隔离问题

## Decision

### 每用户独立授权（采纳）

- 用户首次需要提取飞书文档时，系统发起 **Device Flow 两段式授权**：
  1. 后端 `lark-cli auth login --no-wait --json --domain docs` → 返回验证 URL + device_code，前端展示链接/二维码
  2. 用户在浏览器打开链接扫码/确认授权 → 后端 `lark-cli auth login --device-code <code>` 轮询完成
- 数据库存绑定表 `user_lark_bindings`：`user_id ↔ (app_id, lark_open_id)`，token 生命周期由 lark-cli 管理
- 提取文档正文时，后端以**该用户身份**调用 `lark-cli`（subprocess，超时与并发受控）
- **鉴权超时**：识别 CLI 返回的鉴权错误 → 前端提示「飞书授权已过期」+ 一键重新授权（同一 Device Flow 界面）
- **未授权 / 提取失败**（无 CLI / 无权限 / 非文档链接）：仅保存链接本身，前端提示用户手动粘贴文档关键内容作为补充来源；成功提取与降级两条路径均在 UI 可见标识

### app 凭证不采用

tenant_access_token 为应用级单一身份：所有用户共用，无法区分操作人（审计/权限隔离失效）；且只能读取授权给应用或应用可见范围内的文档，用户私有文档（未分享给应用）读取失败。不符合「每个用户粘贴自己链接」的场景。

## Considered Options

- **每用户独立 user token（Device Flow 两段式 + DB 绑定）**：采纳（如上）
- **app 凭证 tenant_access_token**：无人工但用户隔离失败、读私有文档受限，未选
- **共享账号（现有邹洋）**：所有用户提交的链接走同一身份，权限/审计受限，未选（仅作实现期临时调试身份）
- **仅存链接不提取**：智能体拿不到正文，价值低，未选

## Consequences

- **Positive**：权限语义正确——每个用户读自己有权限的文档，审计可溯源到操作人
- **Positive**：授权全程浏览器交互，无需登录服务器
- **Positive**：失败降级保证功能不中断
- **Negative**：每个用户首次使用需一次 Device Flow 授权；refresh token 过期后需重新授权（前端引导）
- **Negative**：引入对部署环境 lark-cli 的运行时依赖（含多用户配置）；subprocess 调用需处理超时与并发
- **Negative**：绑定表与授权状态接口增加后端面（`user_lark_bindings` 表 + auth 发起/完成/状态 3 个接口）
