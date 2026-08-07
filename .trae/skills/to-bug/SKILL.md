---
name: to-bug
description: 将用户提供的 bug 描述整理后提交到 EasyTest 缺陷管理系统（默认 http://10.19.195.109:15731/），创建缺陷前需确认项目和指派对象。当用户输入 /to-bug 并提供 bug 信息时使用。
disable-model-invocation: true
---

# To Bug

把一段 bug 描述提交到 EasyTest 缺陷管理系统。默认目标环境：`http://10.19.195.109:15731/`。

## 流程

### 1. 获取登录凭据

目标环境所有 `/api` 接口（除登录外）都需要请求头 `Authorization: Bearer <token>`。

- 若本会话已登录过该环境，直接复用 token（JWT 有效期 7 天）。
- 默认使用zouyang/ll940620这个账号登录鉴权，否则询问用户该环境的登录账号/密码。
- 登录：`POST {BASE}/api/auth/login`，body `{"username": "...", "password": "..."}`
- 响应：`{"code": 200, "data": {"token": "...", "user": {...}}}`，取 `data.token`。

### 2. 解析 bug 信息

把用户给的 bug 文本整理为缺陷字段：

- **标题（title）**：一句话概括。取首行/首句，去掉"复现步骤 / 期望 / 实际"等章节词，保持简洁。
- **描述（description）**：除复现步骤外的背景、期望结果、实际结果、环境信息等。
- **复现步骤（steps）**：若文本含"复现步骤"章节，整理为 HTML（如 `<ol><li>...</li></ol>`）；没有则留空。
- **截图**：若用户提供截图，通过 `POST {BASE}/api/defects/attachments/upload`（multipart/form-data，字段名 `file`）上传，返回 `data.filepath` 后，取 `temp/` 后的部分拼接为 `/api/defects/attachments/temp/xxx.png` 并插入到对应步骤的 `<li>` 末尾（如 `<li>接口返回错误<img src=\"/api/defects/attachments/temp/image.png\"></li>`）。

### 3. 确认项目、分支、模块和指派

创建缺陷前必须与用户确认（除非用户在 `/to-bug` 中已明确指定）：

1. **项目**：`GET {BASE}/api/projects` → 展示 `id / name / description` 列表让用户选择。项目未明确时不要猜测。
2. **分支**：`GET {BASE}/api/projects/{project_id}/branches` → 有默认分支用默认分支，否则让用户选择。
3. **模块**：`GET {BASE}/api/defects/modules?project_id={project_id}` → 展示 `id / name` 列表让用户选择；若用户在 `Use Skill: to-bug` 中已提供模块相关信息可直接建议，否则给出选项让用户确定；用户也可选择"不选择模块"（`module_id: 0`）。
4. **指派对象**：优先用 `GET {BASE}/api/projects/{project_id}/members` 获取项目成员候选让用户确认；若成员列表搜索不到，再用 `GET {BASE}/api/users/search?q={昵称或用户名关键词}` 搜索候选让用户确认；用户也可选择"不指派"（`assignee_id: 0`）。
5. **可选字段**：未提及时使用默认值（severity/priority 默认 `P3`，bug_type 默认 `code_error`），不必逐个打断用户。

### 4. 创建缺陷

`POST {BASE}/api/defects`，Header `Authorization: Bearer <token>`，body：

```json
{
  "title": "缺陷标题",
  "description": "缺陷描述",
  "steps": "复现步骤 HTML",
  "project_id": 1,
  "branch_id": 1,
  "module_id": 0,
  "severity": "P3",
  "priority": "P3",
  "assignee_id": 0,
  "bug_type": "code_error",
  "deadline": "",
  "attachments": []
}
```

成功响应：`{"code": 200, "data": {"id": 12}, "msg": "缺陷创建成功"}`。

### 5. 汇报结果

- **成功**：告知缺陷 ID、所属项目/分支、指派对象，以及前端查看入口 `{BASE}`。
- **失败**：展示接口返回的 `msg`（如登录失败、项目无分支），请用户调整后重试。

## 接口速查

| 用途 | 方法与路径 | 认证 |
|---|---|---|
| 登录 | `POST /api/auth/login` | 无 |
| 项目列表 | `GET /api/projects` | Bearer |
| 分支列表 | `GET /api/projects/{project_id}/branches` | Bearer |
| 项目成员 | `GET /api/projects/{project_id}/members` | Bearer |
| 模块列表 | `GET /api/defects/modules?project_id={project_id}` | Bearer |
| 用户搜索 | `GET /api/users/search?q=xxx` | Bearer |
| 上传截图 | `POST /api/defects/attachments/upload`（multipart/form-data，字段名 `file`） | Bearer |
| 创建缺陷 | `POST /api/defects` | Bearer |

统一响应结构：`{"code": 200, "data": ..., "msg": "..."}`，`code != 200` 视为失败。
