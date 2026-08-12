# 04 — Story 生成 + 评审 + 资产 Tab

**What to build:** AI 将需求拆解为 Story，7 维评分评审，用户确认后进入下一层。

**Blocked by:** 03 — 需求导入 + AI 分析 + 概览 Tab

**Status:** pending

- [ ] 资产 Tab 内 Stories 视图：左侧 Story 列表 + 右侧 Story 详情
- [ ] AI 生成 Story 按钮 → AITask 状态机 → 生成完成后列表展示
- [ ] 每条 Story 显示 7 维评分（需求覆盖度/业务完整性/独立性/可测试性/粒度合理性/业务规则完整性/依赖完整性）+ QualityGate（PASS/WARNING/BLOCKED）
- [ ] Story 详情面板：标题、描述、验收标准、7 维评分明细、依赖 Story 列表
- [ ] 人工操作：[确认] [修改] [要求 AI 重新生成] [忽略问题]
- [ ] "确认进入测试点"按钮 → 更新需求状态为 story_confirmed → AITask 流转
