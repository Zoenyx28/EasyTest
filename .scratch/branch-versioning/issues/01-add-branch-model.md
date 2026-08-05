# 01 — 添加 Branch 数据模型和 branch\_id 字段

**What to build:** 在数据层新增 Branch 模型，并向所有需要版本隔离的现有表添加 branch\_id 字段。这是后续所有工单的基础设施，不改变现有行为。

**Blocked by:** 无 — 可立即开始

**Status:** ready-for-agent

- [ ] 在 `models.py` 中新增 `Branch` ORM 类，包含字段：`id`(PK)、`project_id`(FK)、`name`、`source_branch_id`(nullable FK)、`is_default`、`is_empty`、`source_path`、`test_path`、`created_at`、`updated_at`
- [ ] 为 Branch 模型添加 `projects` 关联关系（`Project.branches`）
- [ ] 在 `schemas.py` 中新增 Branch Pydantic schema（`BranchInfo`、`BranchCreate`）
- [ ] 向 6 张表添加 `branch_id` 列（可空，默认 0）：`test_case_definitions`、`tasks`、`task_cases`、`executions`、`execution_cases`、`reports`
- [ ] 在 `database.py` 的 `init_db()` 中添加 `ALTER TABLE ADD COLUMN` 迁移语句
- [ ] 确认添加列后现有 API 查询不受影响（branch\_id 为可空/默认值）

