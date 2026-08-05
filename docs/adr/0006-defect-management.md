# ADR-0006: 缺陷（Bug）管理系统

## Status

Accepted

## Context

平台需要引入缺陷管理功能，参考禅道（Zentao）的设计，支持项目的缺陷全生命周期管理。

需求要点：

- 缺陷字段：标题、简单描述、详细信息（含具体描述、操作步骤、截图）、项目、版本（Branch）、模块、严重程度、优先级、状态、指派给、创建者、创建时间、附件
- 缺陷状态完全照搬禅道：未确认 → 已确认 → 处理中 → 已解决 → 已关闭，包含激活回退流程
- 缺陷关联项目 + 版本（Branch），后续预留关联测试用例入口
- 严重程度分 P0/P1/P2/P3
- 优先级分 P0/P1/P2/P3
- 模块管理：用户在项目下自定义模块树
- 提交缺陷应提供富文本输入，支持图片和文字超链接
- 附件上传到服务器文件系统
- 缺陷列表非成员用户不可见（只能看到自己参与的项目下的缺陷）

## Decision

### 数据模型

#### 缺陷表 `defects`

```sql
defects
├── id              (PK, auto-increment)
├── project_id      (FK → projects.id, NOT NULL)
├── branch_id       (FK → branches.id, 可为 NULL)  — 关联版本
├── module_id       (FK → defect_modules.id, 可为 NULL)  — 关联模块
├── title           (VARCHAR 512, NOT NULL)         — 缺陷标题（简短）
├── description     (TEXT)                          — 缺陷简单描述/概要
├── steps           (TEXT)                          — 详细信息（含具体描述、操作步骤、截图，富文本 HTML，支持图片和超链接）
├── severity        (VARCHAR 8, DEFAULT 'P3')       — 严重程度: P0/P1/P2/P3
├── priority        (VARCHAR 8, DEFAULT 'P3')       — 优先级: P0/P1/P2/P3
├── status          (VARCHAR 16, DEFAULT '未确认')  — 缺陷状态
├── resolution      (VARCHAR 32, DEFAULT '')        — 解决方案（已解决时填写）
├── assignee_id     (FK → users.id, 可为 NULL)      — 指派给
├── creator_id      (FK → users.id, NOT NULL)       — 创建者
├── created_at      (DATETIME)
├── updated_at      (DATETIME)
├── resolved_at     (DATETIME, 可为 NULL)           — 解决时间
└── closed_at       (DATETIME, 可为 NULL)           — 关闭时间
```

#### 缺陷附件表 `defect_attachments`

```sql
defect_attachments
├── id              (PK, auto-increment)
├── defect_id       (FK → defects.id, NOT NULL)
├── file_name       (VARCHAR 256, NOT NULL)         — 原始文件名
├── file_path       (VARCHAR 1024, NOT NULL)        — 服务器存储路径
├── file_size       (INTEGER, DEFAULT 0)            — 文件大小（字节）
├── mime_type       (VARCHAR 64, DEFAULT '')        — MIME 类型
├── uploaded_by     (FK → users.id, NOT NULL)       — 上传者
├── created_at      (DATETIME)
└── is_deleted      (BOOLEAN, DEFAULT FALSE)        — 软删除
```

#### 缺陷模块表 `defect_modules`

```sql
defect_modules
├── id              (PK, auto-increment)
├── project_id      (FK → projects.id, NOT NULL)
├── parent_id       (FK → defect_modules.id, 可为 NULL)  — 父模块（支持树形）
├── name            (VARCHAR 128, NOT NULL)         — 模块名称
├── sort            (INTEGER, DEFAULT 0)            — 排序
├── created_at      (DATETIME)
└── UNIQUE(project_id, parent_id, name)
```

#### 缺陷操作日志表 `defect_logs`

```sql
defect_logs
├── id              (PK, auto-increment)
├── defect_id       (FK → defects.id, NOT NULL)
├── action          (VARCHAR 32, NOT NULL)          — 操作类型: created/assigned/confirmed/resolved/closed/activated/commented
├── operator_id     (FK → users.id, NOT NULL)       — 操作人
├── old_value       (VARCHAR 128, DEFAULT '')
├── new_value       (VARCHAR 128, DEFAULT '')
├── comment         (TEXT, DEFAULT '')              — 备注/评论
├── created_at      (DATETIME)
```

### 缺陷状态流转

完全照搬禅道的状态机：

```
                        ┌─────────────┐
                        │   未确认     │
                        └──────┬──────┘
                               │ 确认
                        ┌──────▼──────┐
                        │   已确认     │
                        └──────┬──────┘
                          ┌────┴────┐
                          │ 指派    │ 关闭
                    ┌─────▼─────┐   │
                    │  处理中    │   │
                    └─────┬─────┘   │
                          │ 解决     │
                    ┌─────▼─────┐   │
                    │  已解决    │   │
                    └─────┬─────┘   │
                     ┌────┴────┐    │
                     │ 关闭    │ 激活
                     │        │    │
                ┌────▼────┐  ┌┴────┴───┐
                │ 已关闭   │  │ 处理中   │  (激活回到处理中)
                └─────────┘  └─────────┘
```

可操作转换：

| 当前状态 | 操作 | 下一状态 | 条件 |
|---------|------|---------|------|
| 未确认 | 确认 | 已确认 | |
| 已确认 | 指派 | 处理中 | 需填写指派给 |
| 已确认 | 关闭 | 已关闭 | |
| 处理中 | 解决 | 已解决 | 需填写解决方案 |
| 已解决 | 关闭 | 已关闭 | |
| 已解决 | 激活 | 处理中 | |
| 已关闭 | 激活 | 处理中 | |

**解决方案**（resolution）：已修复、重复、不是问题、无法重现、设计如此、外部原因、暂不处理

### 严重程度 & 优先级

| 级别 | 严重程度 | 优先级 |
|------|---------|--------|
| P0 | 致命（系统崩溃、数据丢失） | 紧急（需立即处理） |
| P1 | 严重（主要功能不可用） | 高（应尽快处理） |
| P2 | 一般（次要功能异常） | 中（正常排期） |
| P3 | 建议（界面优化、建议） | 低（可延后处理） |

### 后端 API 设计

#### 缺陷 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/defects?branch_id=&status=&severity=&page=&size=` | 缺陷列表 |
| GET | `/api/defects/{id}` | 缺陷详情（含操作日志） |
| POST | `/api/projects/{project_id}/defects` | 创建缺陷 |
| PUT | `/api/defects/{id}` | 更新缺陷 |
| DELETE | `/api/defects/{id}` | 删除缺陷 |

#### 缺陷状态操作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/defects/{id}/confirm` | 确认缺陷 |
| POST | `/api/defects/{id}/assign` | 指派（body: {assignee_id}） |
| POST | `/api/defects/{id}/resolve` | 解决（body: {resolution, comment}） |
| POST | `/api/defects/{id}/close` | 关闭（body: {comment}） |
| POST | `/api/defects/{id}/activate` | 激活（重新打开） |

#### 模块管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/defect-modules` | 模块树列表 |
| POST | `/api/projects/{project_id}/defect-modules` | 创建模块 |
| PUT | `/api/defect-modules/{id}` | 更新模块 |
| DELETE | `/api/defect-modules/{id}` | 删除模块 |

#### 附件管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/defects/{id}/attachments` | 上传附件 |
| DELETE | `/api/defect-attachments/{id}` | 删除附件 |
| GET | `/api/defect-attachments/{id}/download` | 下载附件 |

#### 最新缺陷（用于项目详情页）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{project_id}/defects/recent?limit=2` | 最近 N 条缺陷 |

### 前端实现

- 新增 `/defects` 路由，显示当前活跃项目下对应版本（Branch）的缺陷列表
- 缺陷列表页：表格展示，支持按状态/严重程度/优先级筛选
- 缺陷详情页：富文本展示描述，操作日志时间线，附件列表
- 创建/编辑缺陷：富文本编辑器（支持图片粘贴上传、超链接）
- 模块管理：在项目设置中管理模块树
- 缺陷操作：状态转换按钮（确认、指派、解决、关闭、激活）

### 附件存储

- 附件存储在 `PROJECTS_DATA_DIR / defects / attachments / {defect_id} /` 目录下
- 文件名使用 `{timestamp}_{original_filename}` 避免冲突

## Consequences

- **Positive**: 完整的缺陷生命周期管理，团队协作流程清晰
- **Positive**: 状态机与禅道一致，用户无需学习新流程
- **Positive**: 模块树支持层次化管理，与禅道体验一致
- **Positive**: 预留了关联测试用例的入口（`branch_id` 字段）
- **Negative**: 需要新建 4 个数据库表
- **Negative**: 富文本编辑器需要引入额外的前端依赖
- **Negative**: 附件存储需要新增文件目录