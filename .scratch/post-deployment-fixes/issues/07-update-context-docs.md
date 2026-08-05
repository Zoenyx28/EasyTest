# 07 — 更新 CONTEXT.md 与代码同步

**What to build:** 修正 CONTEXT.md 中与实际代码不符的描述，确保领域文档准确反映当前代码状态。

**Blocked by:** 06 — 提取共享工具 + 拆分 crud.py（需确认最终模块结构和命名）

**Status:** ready-for-agent

- [ ] 更新 CONTEXT.md「Data Model Convention」章节：确认遗留模型已移除的声明与代码一致
- [ ] 更新 CONTEXT.md「URL Convention」章节：准确描述当前版本上下文的传递方式（`/api/projects/{id}/branches` 路径参方式）
- [ ] 如有新增的关键领域概念（如 `_resolve_python` 函数），在 CONTEXT.md 中补充
- [ ] 确认 `docs/adr/` 中的决策记录与当前实现一致