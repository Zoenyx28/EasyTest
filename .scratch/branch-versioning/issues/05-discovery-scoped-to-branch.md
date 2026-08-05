# 05 — 发现流程关联分支

**What to build:** 测试发现（导入）流程关联到当前分支。发现的 TestCaseDefinition 归属于当前激活的 branch_id。分支如果是通过复制创建的，发现流程会替换（刷新）已有的复制 TCD。

**Blocked by:** 04 — 版本过滤集成

**Status:** ready-for-agent

- [ ] `POST /api/discovery` 接受 `?version=` 参数，将发现的 TCD 关联到 `branch_id`
- [ ] 当分支是复制创建的（`source_branch_id` 不为空且 `is_empty=false`）：
  - 运行发现后，删除该分支下已有的 TCD（即之前从源分支复制的那些）
  - 改用新发现的 TCD 填充
- [ ] 当分支是空白分支（`is_empty=true`）：
  - 直接填充发现的 TCD，无需删除操作
- [ ] 前端发现流程：触发发现时从当前路由获取 `version` 参数并传递
- [ ] `ProjectCase` 表不再需要写入（TCD 现在由 branch_id 关联）
- [ ] 测试：在分支上下文中执行发现，验证 TCD 正确关联到 branch_id
