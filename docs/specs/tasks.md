# Tasks

- [x] Task 1: 后端添加 duplicate_defect_id 支持
  - [x] models.py: Defect 模型新增 `duplicate_defect_id` 字段
  - [x] schemas.py: DefectTransition / DefectInfo 新增 `duplicate_defect_id`、`duplicate_defect_title`
  - [x] crud.py: transition_defect 处理 duplicate_defect_id 写入
  - [x] defects.py: API 层传递 duplicate_defect_id；_enrich_defect 查询关联缺陷标题
  - [x] 数据库 ALTER TABLE 添加列

- [x] Task 2: 前端重复Bug关联缺陷选择器
  - [x] useDefect.ts: transitionDefect 新增 duplicate_defect_id 参数
  - [x] types.ts: DefectInfo 新增 duplicate_defect_id、duplicate_defect_title
  - [x] DefectResolveDialog.vue: 选择「重复Bug」时展示关联缺陷下拉框

- [x] Task 3: 详情侧边栏优化
  - [x] DefectDetailDialog.vue: 解决方案中文标签映射
  - [x] DefectDetailDialog.vue: 关联缺陷信息展示（resolution=duplicate时）
  - [x] DefectDetailDialog.vue: 关联版本去重（与解决版本相同时隐藏）

- [x] Task 4: 活动记录页重做
  - [x] DefectHistoryTimeline.vue: 极简预览模式（yyyy-MM-dd HH:mm:ss + 操作人 + 动作）
  - [x] DefectHistoryTimeline.vue: 同操作日志归并（同操作人 + ≤1s）
  - [x] DefectHistoryTimeline.vue: 详情展开模式（+/- 切换，字段变更明细）
  - [x] DefectHistoryTimeline.vue: 字段值中文映射（状态/严重程度/优先级/Bug类型/解决方案等）
  - [x] DefectHistoryTimeline.vue: 评论分组到对应操作下

# Task Dependencies
- Task 2 依赖 Task 1
- Task 3 无依赖，可与 Task 1/2 并行
- Task 4 无依赖，独立可并行
