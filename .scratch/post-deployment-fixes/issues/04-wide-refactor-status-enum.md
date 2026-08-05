# 04 — 宽重构：状态值统一为枚举（expand-contract）

**What to build:** 将散落在代码各处的状态字符串（`'waiting'`、`'running'`、`'passed'`、`'failed'`、`'broken'`、`'skipped'`、`'pass'`、`'fail'`、`'skip'` 等）统一抽取为 `Status` 枚举类型，消除 Primitive Obsession 和 Repeated Switches 气味。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

**Expand 阶段：**
- [ ] 在 `app/models/schemas.py` 中新增 `Status` 枚举，包含所有执行和用例状态值
- [ ] 在数据库模型中新增字符串列兼容性处理（保持旧值仍可读）

**Migrate 阶段（按调用方分批）：**
- [ ] 迁移 `executor.py` 中的状态引用
- [ ] 迁移 `crud.py` 中的状态引用
- [ ] 迁移 `reporter.py` 中的状态引用
- [ ] 迁移 `api/` 下的各路由文件中的状态引用
- [ ] 迁移前端 `useApi.ts` 和 `TestProjectsView.vue` 中的状态引用

**Contract 阶段：**
- [ ] 删除所有旧的状态字符串常量
- [ ] 验证整个执行流程（创建任务 → 执行 → 查看结果）状态显示正确