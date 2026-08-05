
# 缺陷详情页功能修改规范

## Problem Statement

当前缺陷详情页仅支持有限的编辑功能（状态、指派人），用户需要一个更完整的缺陷管理界面，支持：
- 修改更多核心字段（严重程度、优先级、模块、描述、复现步骤）
- 状态变更时可添加备注评论
- 历史记录以更直观的方式展示操作轨迹
- 列表页提供快捷操作按钮（确认、解决、关闭、编辑、复制）

## Solution

对缺陷管理模块进行全面升级，包括：
1. 后端新增字段（bug_type、deadline、resolved_version、resolved_date）
2. 详情页实现内联编辑功能，支持即时保存
3. 历史记录组件重做，展示"创建、编辑、确认、指派给、解决、关闭"等操作
4. 列表页添加5个快捷操作按钮，对应3个状态转换弹窗
5. 复制Bug功能，深拷贝除状态外的所有字段

## User Stories

1. As a 测试人员, I want to 修改缺陷的严重程度，so that 准确反映问题影响范围
2. As a 测试人员, I want to 修改缺陷的优先级，so that 开发能按重要性排序处理
3. As a 测试人员, I want to 修改缺陷所属模块，so that 问题能正确归类
4. As a 测试人员, I want to 编辑缺陷描述和复现步骤，so that 信息更准确完整
5. As a 开发人员, I want to 状态变更时添加备注评论，so that 记录处理过程和原因
6. As a 项目负责人, I want to 查看完整的历史操作记录，so that 追踪缺陷处理轨迹
7. As a 项目成员, I want to 在列表页快速确认缺陷，so that 提高处理效率
8. As a 开发人员, I want to 在列表页快速解决缺陷，so that 减少操作步骤
9. As a 测试人员, I want to 在列表页快速关闭已解决的缺陷，so that 完成缺陷生命周期
10. As a 项目成员, I want to 在列表页快速编辑Bug，so that 快速修改信息
11. As a 测试人员, I want to 复制Bug，so that 创建类似问题时减少重复输入
12. As a 开发人员, I want to 确认Bug时可设置指派人、Bug类型、优先级、截止日期，so that 完整记录确认信息
13. As a 开发人员, I want to 解决Bug时可选择解决方案、解决版本，so that 记录解决信息
14. As a 测试人员, I want to 关闭Bug时可添加备注，so that 记录关闭原因
15. As a 项目成员, I want to 上传和删除附件，so that 提供截图等辅助信息

## Implementation Decisions

### 1. 后端数据模型变更

**新增字段：**
- `bug_type`: Bug类型，枚举值：code_error(代码错误)、config_error(配置错误)、ui_error(界面错误)、performance(性能问题)、security(安全问题)、compatibility(兼容性问题)、document_error(文档错误)
- `deadline`: 截止日期，DateTime类型
- `resolved_version`: 解决版本，映射到branch_id
- `resolved_date`: 解决时间，DateTime类型

**Schema更新：**
- `DefectCreate` 添加 `bug_type`（可选，默认code_error）、`deadline`（可选）
- `DefectUpdate` 添加 `bug_type`、`deadline`、`resolved_version`、`resolved_date`
- `DefectInfo` 添加上述4个字段及对应的名称字段

### 2. API接口变更

**现有接口增强：**
- `PUT /api/defects/{defect_id}`: 支持更新新增字段，自动记录变更日志
- `POST /api/defects/{defect_id}/transition`: 支持 `comment` 字段，状态变更时可同时创建评论

**新增接口：**
- `POST /api/defects/{defect_id}/copy`: 复制Bug，返回新Bug的ID

### 3. 前端组件结构

**详情页 (DefectDetailDialog.vue):**
- 编辑模式：单独提供"编辑"按钮，点击后进入编辑状态
- 只读字段：状态、是否确认（不可修改）
- 可编辑字段：严重程度、优先级、模块、描述、复现步骤、Bug类型、截止日期
- 特殊限制：指派人在已关闭状态时不可修改
- 保存方式：点击"保存"按钮批量提交所有修改

**历史记录组件 (DefectHistoryTimeline.vue - 新建):**
- 展示格式：`[时间], 由 [人] [操作]`
- 简单展示，不设计展开/收起
- 评论直接显示在对应操作记录下方

**列表操作按钮 (DefectList.vue 增强):**
- 5个图标按钮：确认、解决、关闭、编辑、复制
- 始终显示（非悬停显示）
- 按钮根据状态动态禁用/启用

**状态转换弹窗 (3个):**
- `DefectConfirmDialog.vue`: 确认弹窗，含指派人、Bug类型、优先级、截止日期、备注（支持剪贴板贴图）
- `DefectResolveDialog.vue`: 解决弹窗，含解决方案、解决版本、指派人、附件、备注（支持剪贴板贴图）
- `DefectCloseDialog.vue`: 关闭弹窗，含备注（支持剪贴板贴图）

### 4. 状态转换规则

```
unconfirmed ─confirm─→ confirmed
confirmed ─assign─→ in_progress
in_progress ─resolve─→ resolved
resolved ─close─→ closed
* ─activate─→ unconfirmed (重新激活)
```

### 5. 解决方案枚举

```
fixed: 已解决
duplicate: 重复Bug
not_issue: 不是问题
cannot_reproduce: 无法重现
design: 设计如此
external: 外部原因
deferred: 延期处理
```

## Testing Decisions

### 测试范围

1. **后端API测试：**
   - 新增字段的CRUD操作
   - 状态转换接口的参数校验
   - 复制Bug接口的数据完整性

2. **前端组件测试：**
   - 详情页各字段的编辑和保存功能
   - 历史记录的展开/收起交互
   - 列表操作按钮的状态控制
   - 3个状态转换弹窗的表单验证

### 测试方法

- 使用现有测试框架（如pytest+Vue Test Utils）
- 优先测试外部行为，不测试实现细节
- 参考项目中现有的缺陷管理测试用例结构

## Out of Scope

- 抄送给(cc)功能：当前不实现，后续版本考虑
- 邮件通知：状态变更后的通知功能
- 批量操作：多个Bug的批量处理

## Further Notes

### 字段映射说明

| 字段名 | 说明 | 默认值 |
|--------|------|--------|
| bug_type | Bug类型枚举 | code_error |
| deadline | 截止日期 | 空 |
| resolved_version | 解决版本(branch_id) | 0 |
| resolved_date | 解决时间 | 空 |

### 复制Bug规则

- 复制：标题、描述、复现步骤、严重程度、优先级、模块、Bug类型、截止日期
- 重置：status → unconfirmed
- 不复制：创建时间、更新时间、创建者（新Bug创建者为当前用户）

### 按钮权限控制

| 按钮 | 可用状态 |
|------|----------|
| 确认 | unconfirmed |
| 解决 | confirmed, in_progress |
| 关闭 | resolved |
| 编辑 | 所有状态 |
| 复制 | 所有状态 |
