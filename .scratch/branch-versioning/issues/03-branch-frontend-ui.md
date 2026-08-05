# 03 — 前端分支管理 UI

**What to build:** 实现前端分支管理功能，包括分支状态管理 composable、分支选择器下拉菜单、创建/删除分支的交互界面。用户可以在项目内切换分支，URL 中携带版本标识。

**Blocked by:** 02 — 分支管理后端 API

**Status:** ready-for-agent

- [ ] 新增 `src/composables/useBranch.ts`：
  - `branches` — 分支列表 ref
  - `activeBranch` — 当前分支 ref
  - `loadBranches(projectId)` — 调用 GET 获取分支列表
  - `switchBranch(branch)` — 切换当前分支，更新 URL
  - `createBranch(projectId, {name, sourceBranchId?})` — 创建分支
  - `deleteBranch(id)` — 删除分支
- [ ] 在 `Header.vue` 中新增**分支选择器下拉菜单**（仅在有激活项目时显示）：
  - 显示 `branch.name` + 默认分支标记
  - 切换时调用 `switchBranch()`，确认是否需要刷新页面数据
  - 如果 URL 中的 `version` 参数不存在或无效，自动回退到默认分支
- [ ] 新增**创建分支弹窗**（可从 Header 或项目管理页触发）：
  - 输入分支名称
  - 选择创建方式：复制自某个已有分支 / 空白分支
  - 调用 API 创建后自动切换到新分支
- [ ] 新增**删除分支确认弹窗**（并有权限提示：级联删除所有相关数据）
- [ ] 路由更新：在导航守卫中读取 `?version=` 参数，传递给所有 API 调用
- [ ] 当当前项目变更时（例如切换项目），重置分支状态
