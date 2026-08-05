# 02 — 分支管理后端 API

**What to build:** 实现完整的 Branch CRUD 后端 API，包括创建分支（从已有分支复制用例/创建空白分支）、列出分支、删除分支、设置默认分支。创建项目时自动创建 `main` 分支。

**Blocked by:** 01 — 添加 Branch 数据模型和 branch_id 字段

**Status:** ready-for-agent

- [ ] 新增 CRUD 函数：`create_branch`、`list_branches`、`delete_branch`、`set_default_branch`
- [ ] `POST /api/projects/{project_id}/branches` — 请求体 `{name, source_branch_id?}`。如果传了 `source_branch_id`，深拷贝该分支的所有 TestCaseDefinition（新 ID）；否则创建空白分支（`is_empty=true`）
- [ ] `GET /api/projects/{project_id}/branches` — 返回项目的所有分支列表
- [ ] `DELETE /api/branches/{id}` — 级联删除分支及其作用域下所有数据（TCD、Task、TaskCase、Execution、ExecutionCase、Report）
- [ ] `POST /api/branches/{id}/set-default` — 将某分支设为项目默认分支，取消其他分支的 `is_default`
- [ ] 修改项目创建逻辑：`POST /api/projects` 时自动创建名为 `main` 的默认分支，将项目级的 `server_path`/`test_path` 复制到分支
- [ ] 新增迁移逻辑：为已有项目自动创建 `main` 分支，从项目级字段复制路径信息
- [ ] 在对应 Pydantic schema 中添加 Branch 相关模型（如已有）
- [ ] API 层测试：创建空白分支、复制创建分支、列出、删除、设置默认、默认分支自动创建
