# 缺陷详情改进 Spec

## Why
缺陷详情页和活动记录页的交互体验需要优化：重复 Bug 需要关联具体缺陷、侧边栏字段存在冗余显示、活动记录需要支持折叠/展开两种查看模式。

## What Changes
- 解决方案为「重复Bug」时可选择关联缺陷（下拉单选当前项目缺陷列表）
- 详情侧边栏：解决方案显示中文标签，关联缺陷信息展示，关联版本字段去重
- 活动记录页重做：极简预览 + 详情展开（+/-）两种展示形态
- 日志按同次操作用时间戳归并分组

## Impact
- Affected specs: 缺陷管理
- Affected code:
  - `backend/app/api/defects.py` — `_enrich_defect`、`transition_defect`
  - `backend/app/db/models.py` — Defect 模型
  - `backend/app/db/crud.py` — `transition_defect`
  - `backend/app/models/schemas.py` — `DefectTransition`、`DefectInfo`
  - `frontend/src/components/DefectDetailDialog.vue`
  - `frontend/src/components/DefectResolveDialog.vue`
  - `frontend/src/components/DefectHistoryTimeline.vue`
  - `frontend/src/composables/useDefect.ts`
  - `frontend/src/types.ts`

## ADDED Requirements

### Requirement: 重复 Bug 关联缺陷选择
系统 SHALL 在解决缺陷时，当解决方案选择「重复Bug」，提供当前项目缺陷列表的下拉单选，将选中的缺陷 ID 持久化。

#### Scenario: 选择重复Bug并关联缺陷
- **GIVEN** 用户在解决缺陷弹窗中
- **WHEN** 用户选择解决方案为「重复Bug」
- **THEN** 系统展示「关联缺陷」下拉框，加载当前项目所有缺陷（排除自身）
- **AND** 用户可选单选一个缺陷
- **AND** 保存后将 `duplicate_defect_id` 写入数据库

#### Scenario: 切换解决方案后隐藏关联缺陷字段
- **GIVEN** 用户之前选择了「重复Bug」并选了关联缺陷
- **WHEN** 用户切换解决方案为其他值
- **THEN** 关联缺陷下拉框隐藏，值重置为 0

### Requirement: 解决方案 label 映射
系统 SHALL 将解决方案的英文值映射为中文标签显示在详情页侧边栏。

#### Scenario: 展示中文解决方案
- **WHEN** 缺陷详情侧边栏渲染解决方案字段
- **THEN** 显示中文标签：`已解决`、`重复Bug`、`不是问题`、`无法重现`、`设计如此`、`外部原因`、`延期处理`

### Requirement: 关联缺陷信息展示
系统 SHALL 在缺陷详情侧边栏，当解决方案为「重复Bug」且有 `duplicate_defect_id` 时，展示关联缺陷的 ID 和标题。

#### Scenario: 展示关联缺陷
- **GIVEN** 缺陷的 resolution 为 `duplicate` 且 `duplicate_defect_id > 0`
- **WHEN** 查看缺陷详情
- **THEN** 侧边栏展示「关联缺陷」字段，显示 `#缺陷ID 标题`

### Requirement: 关联版本字段去重
系统 SHALL 在缺陷详情侧边栏中，仅当 `关联版本` 与 `解决版本` 值不同时才显示「关联版本」字段。

#### Scenario: 版本相同时隐藏关联版本
- **GIVEN** 缺陷的 `branch_name` 等于 `resolved_version_name`
- **WHEN** 查看缺陷详情侧边栏
- **THEN** 不显示「关联版本」字段

#### Scenario: 版本不同时显示关联版本
- **GIVEN** 缺陷的 `branch_name` 不等于 `resolved_version_name`
- **WHEN** 查看缺陷详情侧边栏
- **THEN** 显示「关联版本」字段，值为 `branch_name`

### Requirement: 活动记录极简预览模式
系统 SHALL 在活动记录 Tab 中以极简模式展示每条操作日志：`yyyy-MM-dd HH:mm:ss + 操作人 + 动作`。同一操作的多条日志（同操作人、间隔 ≤ 1s）合并为一个条目。

#### Scenario: 单字段变更的日志
- **GIVEN** 某次操作只产生一条日志
- **WHEN** 查看活动记录
- **THEN** 显示格式：`2026-01-14 10:30:00 陈浩然 创建`
- **AND** 同次操作仅一条日志时不显示「N 项变更」提示

#### Scenario: 多字段变更的日志归并
- **GIVEN** 某次操作产生多条日志（如解决时同时变更状态、解决方案、指派给）
- **WHEN** 查看活动记录（折叠状态）
- **THEN** 多条日志合并为一个条目，显示主动作标签（取状态变更的动作）
- **AND** 显示「N 项变更」提示

### Requirement: 活动记录详情展开模式
系统 SHALL 支持点击条目右侧 + 按钮展开详情，展示本次操作全部字段变更。

#### Scenario: 展开查看字段变更
- **WHEN** 用户点击某条活动记录的 + 按钮
- **THEN** 展开详情区域，列出本次操作所有字段变更
- **AND** 每条变更格式：`修改了【字段名】，旧值为 XX，新值为 XX`
- **AND** 字段值进行中文映射（状态、严重程度、优先级、Bug类型、解决方案等）
- **AND** 按钮切换为 -（收起按钮）

#### Scenario: 查看展开区域的评论
- **GIVEN** 某次操作后有评论产生
- **WHEN** 展开该操作的详情
- **THEN** 在字段变更列表下方展示评论列表（作者 + 时间 + 内容）

#### Scenario: 收起展开区域
- **WHEN** 用户点击已展开条目的 - 按钮
- **THEN** 详情区域收起，恢复为极简预览模式

## MODIFIED Requirements

### Requirement: 关联版本显示逻辑
**Before**: 无论「关联版本」与「解决版本」是否相同，始终显示「关联版本」字段。
**After**: 当 `branch_name === resolved_version_name` 时隐藏「关联版本」字段。
**Migration**: 无需迁移，前端条件判断自动生效。
