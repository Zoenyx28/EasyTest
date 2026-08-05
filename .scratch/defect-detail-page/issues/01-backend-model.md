# 01 — 后端数据模型扩展

**What to build:** 新增 bug_type、deadline、resolved_version、resolved_date 四个字段到数据库模型和Pydantic Schemas

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Defect表新增4个字段 (bug_type, deadline, resolved_version, resolved_date)
- [ ] DefectCreate Schema添加 bug_type（可选，默认code_error）、deadline（可选）
- [ ] DefectUpdate Schema添加 bug_type、deadline、resolved_version、resolved_date
- [ ] DefectInfo Schema添加上述4个字段及对应名称字段
- [ ] 数据库初始化脚本更新（MySQL和SQLite CREATE TABLE语句）
