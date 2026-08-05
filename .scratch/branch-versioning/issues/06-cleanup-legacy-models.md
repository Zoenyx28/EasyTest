# 06 — 清理旧模型

**What to build:** 删除旧版 `RunRecord`、`TestResultRecord` 模型及相关代码。清理 `runs`/`test_results` 表和相关迁移语句。确认所有流程已切换到新模型。

**Blocked by:** 05 — 发现流程关联分支（或可并行）

**Status:** ready-for-agent

- [ ] 从 `models.py` 中删除 `RunRecord` 和 `TestResultRecord` ORM 类
- [ ] 从 `database.py` 的 `init_db()` 迁移列表中移除 `test_results` 相关的 `ALTER TABLE` 语句
- [ ] 在 `init_db()` 中添加 `DROP TABLE IF EXISTS runs, test_results` 语句
- [ ] 从 `schemas.py` 中删除旧版 Pydantic schema：`RunRecordInfo`、`RunStatus`、`TestHistoryItem`、`RunLogDetail`
- [ ] 从 `crud.py` 中删除旧版 CRUD 函数：
  - `save_run`、`update_run`、`get_runs`、`get_run_by_id`、`delete_runs_by_project_id`
  - `save_test_result`、`get_results_by_run`、`get_result_count_by_type`、`get_all_test_results_by_run`、`delete_results_by_run`
- [ ] 检查 API 路由和 service 中是否引用了上述 CRUD 函数，有则清理
- [ ] 验证：所有 API 端点正常工作，不依赖旧模型
- [ ] 验证：`pytest` 收集后无导入警告
