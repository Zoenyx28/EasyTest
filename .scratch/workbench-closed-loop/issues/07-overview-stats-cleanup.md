# 07 — 概览统计 + 收尾清理

**What to build:** 需求概览 Tab 展示完整统计卡片（测试进度/执行摘要/缺陷数/覆盖率）。MySQL JSON 列迁移 + 删除旧表。

**Blocked by:** 06 — 执行 Tab + 缺陷 Tab + 一键提缺陷

**Status:** pending

- [ ] 概览 Tab 四张统计卡片：
  - 测试设计进度：各层完成状态（需求分析✅/Story×4 PASS/测试点×12 PASS/用例×8 PASS）
  - 最近执行：时间 + pass/fail 数量 + [查看详情] [重新跑]
  - 关联缺陷：总数 + 未关闭数 + [查看全部]
  - 覆盖率：Story/测试点/用例/自动化/风险 各层百分比（从 RequirementAsset 实时计算）
- [ ] `requirement_assets.content` 字段从 TEXT 迁移为 MySQL JSON 列类型
- [ ] `requirements.source_meta` 字段从 TEXT 迁移为 MySQL JSON 列类型
- [ ] 删除已合并的 12 张旧分层表（保留数据迁移脚本记录）
- [ ] 完整端到端自测：导入需求 → AI 分析 → Story → 测试点 → 场景 → 用例 → 绑定 → 执行 → 提缺陷 → 概览统计
