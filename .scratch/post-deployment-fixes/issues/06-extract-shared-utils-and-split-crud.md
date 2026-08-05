# 06 — 提取共享工具 + 拆分 crud.py

**What to build:** 消除 `format_duration` 等重复代码，将 1543 行的 `crud.py` 按领域拆分为独立模块，提高可维护性。

**Blocked by:** 04 — 宽重构：状态值统一为枚举（状态枚举化后 crud 中的状态引用更清晰）、05 — 移除遗留 RunRecord/TestResultRecord 模型（旧模型 CRUD 删除后 crud.py 体积大幅减小，拆分边界更干净）

**Status:** ready-for-agent

- [ ] 将 `format_duration()` 提取到共享工具模块（如 `app/utils.py`），更新所有调用方
- [ ] 将报告构建逻辑从 `executor.py` 和 `reporter.py` 中提取到共享模块
- [ ] 将 `crud.py` 拆分为领域模块：`crud_projects.py`（项目 + 分支）、`crud_tasks.py`（任务 + TaskCase）、`crud_executions.py`（执行 + ExecutionCase）、`crud_reports.py`（报告）
- [ ] 更新 `api/` 各路由文件中的导入引用
- [ ] 更新 `executor.py`、`reporter.py` 中的导入引用
- [ ] 验证全流程：项目同步 → 创建任务 → 执行 → 查看结果 → 查看报告