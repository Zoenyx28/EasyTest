# ADR-0007: 项目详情板块

## Status

Accepted

## Context

项目列表页面需要增加右侧详情面板，显示当前活跃项目的详细信息，包括：

1. **项目备注板**：支持 Markdown 渲染，用于记录项目说明、注意事项等
2. **项目基本信息**：项目名称、创建人、项目成员清单
3. **最近缺陷信息**：最近 2 次提交的缺陷记录（"xxx 提交了 xxx 用例名称（xx 时间之前）"）
4. **最近测试任务**：最近 2 次测试任务情况（任务名称、执行时间、执行状态），点击可跳转到测试执行页面

需求要点：

- 项目列表页采用**左右分栏布局**，左侧为项目列表（卡片显示），右侧为当前活跃项目的详情
- 切换活跃项目时右侧详情同步更新
- 项目成员都有权限添加/移除成员，但不能移除创建人
- "最近缺陷"指最近 2 条提交记录，不限时间
- 项目备注支持 Markdown 渲染，支持编辑
- "最近测试任务"指该项目下最近 2 条执行记录（不区分版本）
- 右侧详情面板**不使用子导航 tab**，所有信息按区块垂直排列

## Decision

### 页面布局

```
┌──────────────────────────────────────────────────────────┐
│  [左侧 - 项目列表（约 40%）]  │  [右侧 - 项目详情（约 60%）]  │
│                              │                             │
│  ┌───┐  ┌───┐               │  ┌──────────────────────┐  │
│  │ P1│  │ P2│               │  │ 项目备注（Markdown）   │  │
│  └───┘  └───┘               │  │ [编辑]               │  │
│  ┌───┐                      │  │ ---                  │  │
│  │ P3│                      │  │ 渲染后的 Markdown 内容│  │
│  └───┘                      │  ├──────────────────────┤  │
│                              │  │ 项目名称: xxx         │  │
│                              │  │ 创建人: xxx           │  │
│                              │  │ 成员: a, b, c  [管理] │  │
│                              │  ├──────────────────────┤  │
│                              │  │ 最近缺陷              │  │
│                              │  │ · xxx 提交了 xxx     │  │
│                              │  │   （2小时前）         │  │
│                              │  │ · xxx 提交了 xxx     │  │
│                              │  │   （昨天 15:30）     │  │
│                              │  ├──────────────────────┤  │
│                              │  │ 最近测试任务           │  │
│                              │  │ · 任务A   成功  昨天  │  │
│                              │  │ · 任务B   失败  前天  │  │
│                              │  └──────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 数据模型

#### 项目备注表 `project_notes`

```sql
project_notes
├── id              (PK, auto-increment)
├── project_id      (FK → projects.id, UNIQUE, NOT NULL)
├── content         (TEXT, DEFAULT '')                 — Markdown 内容
├── updated_by      (FK → users.id, 可为 NULL)        — 最后修改人
├── created_at      (DATETIME)
└── updated_at      (DATETIME)
```

### 后端 API 设计

#### 项目详情

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/detail` | 获取项目完整详情（含创建人、成员数、备注预览） |

#### 项目成员

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/members` | 获取项目成员列表 |
| POST | `/api/projects/{project_id}/members` | 添加成员（body: {user_id}） |
| DELETE | `/api/projects/{project_id}/members/{user_id}` | 移除成员（不能移除创建人） |

#### 项目备注

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/notes` | 获取项目备注 |
| PUT | `/api/projects/{project_id}/notes` | 更新项目备注（body: {content}） |

#### 项目概览信息

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/overview` | 返回概览数据（打包：创建人信息、成员列表、最近缺陷、最近测试任务） |

### 前端实现

#### 路由 & 页面结构

- `TestProjectsView.vue` 重构为**左右分栏布局**
- 左侧：现有项目卡片列表（调整宽度）
- 右侧：新增 `ProjectDetailPanel.vue` 组件

#### 右侧面板内容区块（从上到下排列，无子导航）

1. **项目备注区块**（最上方）：
   - 默认显示 Markdown 渲染内容
   - 点击"编辑"按钮切换为 Markdown 编辑模式（textarea + 保存/取消）
   - 保存后刷新渲染内容
   - 空状态显示"暂无备注"

2. **项目信息区块**：
   - 项目名称、创建人名称
   - 项目成员清单（头像/名称列表），附带"管理成员"按钮 → 弹出成员管理对话框

3. **最近缺陷区块**（最近 2 条）：
   - 显示格式："xxx 提交了 xxx 用例名称（xx 时间之前）"
   - 点击跳转到缺陷详情页
   - 空状态显示"暂无缺陷"

4. **最近测试任务区块**（最近 2 条）：
   - 显示：任务名称、执行状态（成功/失败/运行中）、执行时间
   - 点击跳转到测试执行页面（`/execution`，可传入 execution_id 定位）
   - 空状态显示"暂无执行记录"

#### 组件拆分

- `ProjectDetailPanel.vue` — 右侧面板容器，包含所有区块
- `ProjectInfoSection.vue` — 项目信息区块（名称、创建人、成员管理入口）
- `ProjectRecentDefects.vue` — 最近缺陷区块
- `ProjectRecentTasks.vue` — 最近测试任务区块
- `ProjectNotesSection.vue` — 备注区块（Markdown 渲染 + 编辑切换）
- `ProjectMemberManageModal.vue` — 成员管理弹窗（搜索用户、添加、移除）

## Consequences

- **Positive**: 无子导航，所有信息一目了然，操作更直接
- **Positive**: 左右分栏布局，充分利用屏幕空间
- **Positive**: 项目备注支持 Markdown，灵活满足文档需求
- **Positive**: 复用现有 API（执行历史），减少重复开发
- **Negative**: 需要重构 TestProjectsView.vue，改动较大
- **Negative**: 需要新增 `project_notes` 表
- **Negative**: 现有 projects API 需要增加 `creator_id` 和成员信息