# 05 — 项目备注

**What to build:** 项目备注的 Markdown 编辑与渲染功能。

- project_notes 表（每个项目一条记录）
- 备注 API（GET/PUT，需认证 + 项目成员权限）
- 前端 Markdown 编辑模式（textarea）与渲染模式切换
- 保存后刷新渲染内容

**Blocked by:** 01 — 用户注册与登录认证

**Status:** ready-for-agent

- [ ] 每个项目可关联一条 Markdown 备注
- [ ] 项目成员可查看和编辑备注
- [ ] 前端支持 Markdown 编辑与渲染切换
- [ ] 保存后立即生效