# 05 — 宽重构：移除遗留 RunRecord/TestResultRecord 模型

**What to build:** 删除 `RunRecord`、`TestResultRecord` 及其全套 CRUD 函数，消除与 CONTEXT.md 中"遗留模型已移除"声明的矛盾。这是一次宽重构的 contract 阶段——旧模型已无人使用，可直接删除。

**Blocked by:** 04 — 宽重构：状态值统一为枚举（先完成状态枚举化，确保迁移安全）

**Status:** ready-for-agent

**Expand 阶段（如尚未完成）：**
- [ ] 确认所有旧模型调用方已迁移到新 Execution/ExecutionCase 模型

**Contract 阶段：**
- [ ] 从 `db/models.py` 中删除 `RunRecord`、`TestResultRecord` 类定义
- [ ] 从 `db/crud.py` 中删除 `save_run`、`update_run`、`get_run`、`save_test_result`、`save_test_results`、`get_test_history`（旧版）、`get_recent_history`、`get_run_logs`、`get_run_results`、`get_all_runs`、`get_run_record` 等函数
- [ ] 从 `db/__init__.py` 中移除旧模型的导入引用
- [ ] 从 `api/` 各路由中移除旧模型 CRUD 的导入和调用
- [ ] 验证：创建任务 → 执行 → 查看结果 → 查看报告 全流程正常
- [ ] 更新 CONTEXT.md 中关于模型状态的描述（或留给 #07 统一处理）