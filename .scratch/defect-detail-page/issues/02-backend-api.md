# 02 — 后端CRUD和API增强

**What to build:** 支持新增字段的CRUD操作，新增复制Bug接口，增强状态转换接口支持comment字段

**Blocked by:** 01 — 后端数据模型扩展

**Status:** ready-for-agent

- [ ] updateDefect CRUD支持新增字段
- [ ] 新增 POST /api/defects/{id}/copy 复制Bug接口（深拷贝除状态外的所有字段）
- [ ] 状态转换接口 POST /api/defects/{id}/transition 支持 comment 字段
- [ ] 字段变更日志记录增强，支持新增字段的变更记录
