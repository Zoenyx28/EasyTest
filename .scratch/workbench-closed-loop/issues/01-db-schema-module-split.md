# 01 — DB 新 Schema + 后端模块拆分

**What to build:** 需求域从 17 张表合并为 5 张核心表，后端代码按限界上下文拆分为 4 个独立模块。所有现有功能保持正常运行。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 新建 `requirement_assets` 统一资产表（asset_type 枚举 + parent_id 树形 + content JSON）
- [ ] `requirements` 表增加 `content`（MEDIUMTEXT）、`source_type`（ENUM）、`source_meta`（JSON）字段
- [ ] `defects` 表增加 `requirement_id` 可选字段
- [ ] Alembic 初始化 + 首次迁移脚本，替代 init_db() 中的手动 ALTER TABLE
- [ ] 后端代码拆分为 `domains/test_execution/`、`domains/defect_tracking/`、`domains/requirement_design/`、`domains/project_mgmt/`、`shared/`
- [ ] 所有现有 import 路径更新，API 行为不变
- [ ] 旧表数据迁移脚本（旧 12 张分层表 → requirement_assets）
- [ ] 现有测试全部通过
