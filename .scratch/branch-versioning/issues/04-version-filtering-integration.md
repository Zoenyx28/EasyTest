# 04 — 版本过滤集成（后端 + 前端）

**What to build:** 后端所有现有 API 端点支持 `?version=<branch_id>` 参数进行数据过滤，前端所有 API 调用携带版本参数。切换分支时页面数据同步刷新，实现完整的数据隔离。

**Blocked by:** 03 — 前端分支管理 UI

**Status:** ready-for-agent

**后端：**
- [ ] 在路由层解析 `?version=` 参数，没有时自动使用项目默认分支的 branch_id
- [ ] `GET /api/tests?version={id}` — 按 `branch_id` 过滤 TestCaseDefinition
- [ ] `GET /api/tasks?version={id}` — 按 `branch_id` 过滤 Task
- [ ] `POST /api/tasks` — 从 `?version=` 自动填充 `task.branch_id`
- [ ] `GET /api/executions?version={id}` — 按 `branch_id` 过滤 Execution
- [ ] `POST /api/executions` — 从 `?version=` 自动填充 `execution.branch_id`
- [ ] `GET /api/execution-cases/{id}/log` — 确认 execution 属于当前分支上下文
- [ ] `GET /api/reports?version={id}` — 按 `branch_id` 过滤 Report
- [ ] CRUD 层：为所有版本相关查询添加 `branch_id = ?` 过滤条件

**前端：**
- [ ] `useApi.ts` 扩展：接受可选的 `version` 参数，追加到请求 URL
- [ ] 路由守卫：读取 `?version=` 参数，存入全局状态
- [ ] 所有 API 调用点：从路由 query 获取 `version` 并传入 `useApi`
- [ ] 切换分支时：更新 URL → 路由守卫检测变更 → 触发组件数据重新加载
- [ ] `useProject.ts` 联动：激活项目后自动加载该项目的分支列表，切到默认分支

**测试：**
- [ ] `tests/test_version_filtering.py` — 创建两个分支，各自填充独立数据，验证 `?version=` 过滤正确
- [ ] 省略 `?version=` 时验证回退到默认分支
