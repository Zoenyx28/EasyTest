# ADR-0006: 缺陷（Bug）管理系统

## Status

Accepted

## Context

平台需要引入缺陷管理功能，参考禅道（Zentao）的设计，支持项目的缺陷全生命周期管理。

需求要点：

- 缺陷字段：标题、简单描述、详细信息（含具体描述、操作步骤、截图）、项目、版本（Branch）、模块、严重程度、优先级、Bug类型、截止日期、状态、指派给、创建者、创建时间、附件
- 缺陷状态完全照搬禅道：未确认 → 已确认 → 处理中 → 已解决 → 已关闭，包含激活回退流程；已确认状态可直接解决
- 缺陷关联项目 + 版本（Branch），解决时可指定解决版本，后续预留关联测试用例入口
- 严重程度分 P0/P1/P2/P3
- 优先级分 P0/P1/P2/P3
- Bug类型：代码错误、设计缺陷、性能问题、安全问题、体验问题、兼容性、其他
- 模块管理：用户在项目下自定义模块树，最多4级
- 附件上传先存临时目录，保存缺陷时才绑定
- 缺陷列表非成员用户不可见（只能看到自己参与的项目下的缺陷）

## Decision

### 数据模型

#### 缺陷表 `defects`

```sql
defects
├── id                  (PK, auto-increment)
├── project_id          (FK → projects.id, NOT NULL)
├── branch_id           (FK → branches.id, 可为 NULL)  — 关联版本
├── module_id           (FK → defect_modules.id, 可为 NULL)  — 关联模块
├── title               (VARCHAR 512, NOT NULL)         — 缺陷标题（简短）
├── description         (TEXT)                          — 缺陷简单描述/概要
├── steps               (TEXT)                          — 详细信息（含具体描述、操作步骤、截图，富文本 HTML）
├── severity            (VARCHAR 8, DEFAULT 'P3')       — 严重程度: P0/P1/P2/P3
├── priority            (VARCHAR 8, DEFAULT 'P3')       — 优先级: P0/P1/P2/P3
├── bug_type            (VARCHAR 32, DEFAULT 'code_error')  — Bug类型
├── deadline            (VARCHAR 32, DEFAULT '')        — 截止日期
├── status              (VARCHAR 16, DEFAULT 'unconfirmed')  — 缺陷状态
├── resolution          (VARCHAR 32, DEFAULT '')        — 解决方案（已解决时填写）
├── duplicate_defect_id (INTEGER, DEFAULT 0)            — 关联重复缺陷 ID（resolution=duplicate时）
├── assignee_id         (FK → users.id, 可为 NULL)      — 指派给
├── creator_id          (FK → users.id, NOT NULL)       — 创建者
├── resolved_version    (INTEGER, DEFAULT 0)            — 解决版本（Branch ID）
├── resolved_date       (VARCHAR 32, DEFAULT '')        — 解决日期
├── created_at          (DATETIME)
└── updated_at          (DATETIME)
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
├── field           (VARCHAR 64, NOT NULL)           — 变更字段: status/assignee_id/resolution/severity/priority/module_id/bug_type/deadline/resolved_version/duplicate_defect_id 等
├── old_value       (VARCHAR 512, DEFAULT '')
├── new_value       (VARCHAR 512, DEFAULT '')
├── operator_id     (FK → users.id, NOT NULL)        — 操作人
├── created_at      (DATETIME)
```

#### 缺陷评论表 `defect_comments`

```sql
defect_comments
├── id              (PK, auto-increment)
├── defect_id       (FK → defects.id, NOT NULL)
├── content         (TEXT, NOT NULL)                 — 评论内容
├── author_id       (FK → users.id, NOT NULL)        — 评论人
├── created_at      (DATETIME)
```

### 缺陷状态流转

完全照搬禅道的状态机：

```
                        ┌─────────────┐
                        │   未确认     │
                        └──┬───┬──────┘
                           │   │
                     确认   │   │ 关闭
                    ┌──────▼┐  │
                    │ 已确认 ├──┘
                    └──┬──┬─┘
                 指派   │  │ 解决
               ┌───────▼┐ │
               │ 处理中  │ │
               └───┬────┘┌▼───────┐
                   │ 解决│ 已解决  │
                   │    └──┬───┬─┘
                   │  关闭 │   │ 激活
                   │  ┌───▼┐ ┌▼───────┐
                   └──►已关闭│ │ 处理中  │ (激活回到处理中)
                      └────┘ └────────┘
```

可操作转换：

| 当前状态 | 操作 | 下一状态 | 条件 |
|---------|------|---------|------|
| 未确认 | 确认 | 已确认 | |
| 未确认 | 关闭 | 已关闭 | |
| 已确认 | 指派 | 处理中 | 需填写指派给 |
| 已确认 | 解决 | 已解决 | 需填写解决方案 |
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
| GET | `/api/defects?project_id=&branch_id=&status=&severity=&page=&page_size=` | 缺陷列表 |
| GET | `/api/defects/{id}` | 缺陷详情（含 enrich 后的用户名/模块名/版本名） |
| GET | `/api/defects/{id}/detail` | 缺陷完整详情（合并 defect + logs + attachments + comments，一次返回） |
| POST | `/api/defects` | 创建缺陷 |
| PUT | `/api/defects/{id}` | 更新缺陷 |
| POST | `/api/defects/{id}/copy` | 复制缺陷 |

#### 缺陷状态操作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/defects/{id}/transition` | 统一状态转换（body: {action, assignee_id, resolution, comment, resolved_version, duplicate_defect_id, bug_type, priority, deadline}） |

action 支持: confirm / assign / resolve / close / activate

#### 模块管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/defects/modules?project_id=` | 模块树列表 |
| POST | `/api/defects/modules` | 创建模块 |
| PUT | `/api/defects/modules/{id}` | 更新模块（重命名） |
| DELETE | `/api/defects/modules/{id}` | 删除模块（关联缺陷的 module_id 置空） |

#### 附件管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/defects/attachments/upload` | 上传附件到临时目录（返回 {filename, filepath, file_size, mime_type}） |
| DELETE | `/api/defects/attachments/{id}` | 删除附件 |
| GET | `/api/defects/attachments/{id}/download` | 下载附件 |

附件流程：上传时存到 `defects/temp/`，创建/更新缺陷时 passes `attachments: [{filename, filepath, ...}]`，后端将文件从 temp 移动到 `defects/{id}/` 并入库。

#### 最新缺陷（用于项目详情页）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/defects/recent?project_id=&branch_id=&limit=2` | 最近 N 条缺陷 |

#### 我的缺陷

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/defects/my?project_id=&branch_id=` | 当前用户的缺陷 |

### 前端实现

- 新增 `/defects` 路由，显示当前活跃项目下对应版本（Branch）的缺陷列表
- 缺陷列表页：左右布局（左侧模块目录树 + 右侧缺陷列表），支持按状态筛选
- 模块目录树：hover 显示操作按钮（添加子模块/重命名/删除），最多 4 级
- 缺陷详情弹窗：左右布局（左侧 Tab 切换详情/活动记录 + 右侧侧边栏元信息），编辑/预览两模式
- 侧边栏展示：创建者、指派给、模块路径（一级/二级/三级...）、严重程度、优先级、Bug类型、截止日期、解决方案、关联缺陷（重复Bug时）、解决版本、关联版本、时间等
- 活动记录 Tab：
  - 极简预览模式：`yyyy-MM-dd HH:mm:ss + 操作人 + 动作`，同操作日志归并
  - 详情展开模式：点击 + 展开显示字段变更明细 `修改了【字段名】，旧值为XX，新值为XX`
  - 评论在展开时显示于对应操作下方
- 缺陷操作：状态转换统一弹窗（确认、指派、解决、关闭、激活），解决时可选择关联重复缺陷
- 附件管理：预览模式可下载不可上传/删除，编辑模式先上传到临时目录、保存时才绑定

### 附件存储

- 临时附件存储在 `PROJECTS_DATA_DIR / 'defects' / 'temp' /` 目录下
- 保存缺陷后从 temp 移动到 `PROJECTS_DATA_DIR / 'defects' / '{defect_id}' /`
- 文件名使用原始文件名，上传时返回路径供保存时传入

## Consequences

- **Positive**: 完整的缺陷生命周期管理，团队协作流程清晰
- **Positive**: 状态机与禅道一致（含已确认→解决快捷路径），用户无需学习新流程
- **Positive**: 模块树支持层次化管理（最多 4 级），hover 操作交互高效
- **Positive**: 统一状态转换 API（transition）减少接口碎片化
- **Positive**: 合并详情接口（detail）一次返回缺陷+日志+附件+评论，减少 HTTP 请求
- **Positive**: 附件临时上传机制，取消编辑不留下孤立文件
- **Positive**: 活动记录支持极简/展开双模式，时序归并同操作日志
- **Negative**: 需要新建 6 个数据库表（defects / defect_attachments / defect_modules / defect_logs / defect_comments / 模块关联）
- **Negative**: 附件存储需要新增文件目录