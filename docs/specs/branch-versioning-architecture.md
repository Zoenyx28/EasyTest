# 规范：基于分支的版本管理与架构统一

## 问题描述

EasyTest 目前没有测试项目的版本管理概念。用户只能针对单一的测试用例定义快照运行测试，无法在不同版本的被测软件之间隔离工作。当需要测试新版本发布、同时保留上一个版本的测试配置时，只能创建一个独立项目——这会导致配置重复，而且切断了相关测试套件之间的可见关联。

与此同时，代码库中存在两套并行的执行跟踪模型（旧版 `runs`/`test_results` 表与新版 `executions`/`execution_cases` 表并存），增加了维护成本，也容易让新贡献者困惑。

## 解决方案

引入 **Branch（分支，也称版本）** 作为项目中的一等实体。分支就像一个轻量级、隔离的工作空间：

- 它拥有自己独立的 **TestCaseDefinition（测试用例定义）**（从源分支复制时，每个用例获得新的 ID）。
- 它拥有自己独立的 **Task（任务）**、**Execution（执行）** 和 **Report（报告）**。
- 在 UI 中切换分支会改变所有数据视图的作用域。

同时，移除旧版 `RunRecord` 和 `TestResultRecord` 模型，使 `executions`/`execution_cases` 表成为唯一的持久化路径。

## 用户故事

1. 作为测试工程师，我希望能够从已有分支**创建新分支**，这样我就可以开始测试新软件版本而无需重新导入测试用例。
2. 作为测试工程师，我希望复制的测试用例拥有**全新的 ID**，这样在一个分支上的改动不会影响另一个分支的历史记录。
3. 作为测试工程师，我希望能够创建**空白分支**（不含任何测试用例），这样我可以为同一项目从头开始配置完全不同的测试套件。
4. 作为测试工程师，我希望在 UI 中通过下拉菜单**切换当前分支**，这样我可以查看该分支下的测试用例、任务、执行和报告。
5. 作为测试工程师，我希望 URL 中携带**分支 ID**（`?version=<id>`），这样我可以收藏或分享指向特定分支视图的链接。
6. 作为测试工程师，我希望创建项目时自动创建**默认分支**（`main`），这样现有项目无需额外迁移步骤即可正常工作。
7. 作为测试工程师，我希望能够**删除分支**，这样我可以清理过期的版本上下文。
8. 作为开发者，我希望移除旧版 `RunRecord` 和 `TestResultRecord` 模型，这样代码库只有一条执行跟踪路径。
9. 作为测试工程师，我希望**测试发现（导入）** 的结果归属于当前激活的分支，这样发现的测试用例属于正确的版本上下文。
10. 作为测试工程师，我希望在 UI 头部看到**分支名称**，这样我始终清楚自己正在操作哪个版本。

## 实现决策

### 1. 新增 `branches` 表

```
branches
├── id              PK，自增
├── project_id      外键 → projects.id，NOT NULL
├── name            varchar(255)，人类可读，例如 "main"、"v2.0"
├── source_branch_id  可空外键 → branches.id，从已有分支创建时设置
├── is_default      boolean，默认 false——每个项目只有一个默认分支
├── is_empty        boolean，默认 false——true 表示空白分支，需要导入
├── source_path     varchar(1024)，该分支的项目源码目录
├── test_path       varchar(512)，源码中的相对测试路径
├── created_at      datetime
└── updated_at      datetime
```

### 2. 在现有表中添加 `branch_id` 字段

| 表名 | 新增列 | 约束 |
|---|---|---|
| `test_case_definitions` | `branch_id` | 外键 → branches.id，NOT NULL，默认 0 |
| `tasks` | `branch_id` | 外键 → branches.id，NOT NULL，默认 0 |
| `task_cases` | `branch_id` | 外键 → branches.id，NOT NULL，默认 0 |
| `executions` | `branch_id` | 外键 → branches.id，NOT NULL，默认 0 |
| `execution_cases` | `branch_id` | 外键 → branches.id，NOT NULL，默认 0 |
| `reports` | `branch_id` | 外键 → branches.id，NOT NULL，默认 0 |
| `project_cases` | 不变 | （已弃用，推荐使用分支作用域的 TCD）|

### 3. API 接口

**新增接口：**

| 方法 | 路径 | 描述 |
|---|---|---|
| `POST` | `/api/projects/{project_id}/branches` | 创建分支。请求体：`{name, source_branch_id?}`。如果传了 `source_branch_id`，则从该分支深拷贝 TCD；否则创建空白分支。 |
| `GET` | `/api/projects/{project_id}/branches` | 列出项目的所有分支 |
| `DELETE` | `/api/branches/{id}` | 删除分支及其作用域内的所有数据 |
| `POST` | `/api/branches/{id}/set-default` | 将某分支设为其项目的默认分支 |

**修改的接口——全部接受 `?version=<branch_id>` 查询参数：**

| 方法 | 路径 | 变更 |
|---|---|---|
| `GET` | `/api/tests` | 按 `branch_id` 过滤 TCD |
| `GET` | `/api/tasks` | 按 `branch_id` 过滤任务 |
| `POST` | `/api/tasks` | 从 `?version=` 自动填充 `branch_id` |
| `GET` | `/api/executions` | 按 `branch_id` 过滤执行 |
| `POST` | `/api/executions` | 从 `?version=` 自动填充 `branch_id` |
| `GET` | `/api/reports` | 按 `branch_id` 过滤报告 |
| `POST` | `/api/discovery` | 将发现的 TCD 关联到 `branch_id` |

省略 `?version=` 时，使用项目的默认分支。

### 4. 前端改动

- 新增 **`useBranch.ts`** composable：管理当前分支状态、获取分支列表、提供 `switchBranch()` 方法。
- **App.vue / Header.vue**：增加分支选择器下拉菜单，显示 `branch.name`。切换时更新 URL 中的 `?version=` 参数并重新加载数据。
- **路由**：导航时读取 `?version=` 查询参数，将所有 API 调用传入 `version`。
- **所有 API 调用**：在版本相关请求中追加 `?version=<activeBranchId>`。
- **URL 示例**：`/cases?version=1`、`/execution?version=1`、`/reports?version=2`

### 5. 删除旧模型

- 通过 DDL 删除 `runs` 和 `test_results` 表。
- 移除 `RunRecord` 和 `TestResultRecord` ORM 类。
- 移除 `RunRecordInfo`、`RunStatus`、`TestHistoryItem`、`RunLogDetail` Pydantic schema。
- 移除所有引用这些模型的 service 或 API 代码。
- `executions` 表中的 `execution_id` 生成已替代旧的 `run_id`——确认所有调用方都使用 `execution_id`。

### 6. 项目创建变化

创建 Project 时，自动创建一个名为 `main` 的默认分支。`server_path` 和 `test_path` 字段从 Project 级别迁移到 Branch 级别——每个分支可以指向不同的源码目录。

迁移时，为每个已有项目创建一个 `main` 分支，将项目级别的 `server_path` 和 `test_path` 复制到分支中。

## 测试决策

### 好测试的标准

- 测试外部行为（API 响应、操作后的数据库状态），而非内部实现细节。
- 使用 FastAPI `TestClient` 配合内存 SQLite 数据库。
- 每个测试独立运行——每个测试都有独立的 setup 和 teardown。
- 优先使用真实数据库操作而非 mock。

### 测试范围：API 层（FastAPI TestClient）

这是最高的可行测试切入点。测试覆盖完整的 请求→路由→服务→数据库 链路。

### 测试模块

| 测试文件 | 范围 |
|---|---|
| `tests/test_branches.py` | 分支 CRUD API：创建（复制/空白）、列出、删除、设为默认 |
| `tests/test_version_filtering.py` | 按版本过滤的查询能否正确返回每个分支的数据 |
| `tests/test_legacy_removal.py` | 旧模型已移除；现有流程仍然正常 |
| `tests/test_discovery.py` | 测试发现填充到当前分支（添加 `branch_id` 断言） |

### 测试场景（分支相关）

1. **创建空白分支** — `POST /projects/1/branches {name:"v2.0"}` → 201，分支无 TCD。
2. **通过复制创建分支** — `POST /projects/1/branches {name:"v2.0", source_branch_id:1}` → 201，TCD 数量与源分支一致，所有 TCD 拥有新 ID。
3. **列出分支** — `GET /projects/1/branches` → 200，返回项目的所有分支。
4. **设置默认分支** — `POST /branches/2/set-default` → 200，分支 2 现在是默认分支。
5. **删除分支** — `DELETE /branches/2` → 204，级联删除相关数据。
6. **按版本过滤查询** — 创建两个具有不同 TCD 集的分支；使用 `?version=1` 查询仅返回分支 1 的 TCD。
7. **省略版本参数** — API 默认使用项目的默认分支。
8. **自动创建默认分支** — 创建项目时自动创建 `main` 分支。

### 现有参考

代码库中尚无测试。这些将是第一批测试。使用标准的 `pytest` + `httpx`（FastAPI TestClient）模式，遵循 FastAPI 官方测试指南。

## 不在此范围

- **Git 集成**：不会自动关联 Git 分支或提交。分支名称是用户自定义文本。
- **分支合并**：不支持分支间合并或 TCD 差异对比。
- **访问控制**：所有用户都能看到项目内的所有分支。
- **分支对比 UI**：不提供并排 TCD 对比视图。
- **大数据量 TCD 复制优化**：初始实现使用逐条复制；批量 INSERT 优化属于未来工作。
- **Celery 任务版本管理**：提交给 Celery 的任务不按版本划分——只有跟踪它们的 Execution 是按版本划分的。

## 补充说明

- `Project` → `ProjectCase` 关联在概念上已被弃用（因为 `TestCaseDefinition` 现在携带 `branch_id`）。考虑在未来的规范中移除 `project_cases` 表，但**本次变更不涉及**。
- `Project.is_active` 字段可能在 UI 始终在分支上下文内操作后变得冗余。暂时保留不动。
- 数据库迁移应使用 Alembic 来新增 `branches` 表和列。旧表删除可在迁移中使用原始 SQL DDL。
- 当用户运行测试发现（导入）时，发现的 TCD 与当前激活的 `branch_id` 关联。如果分支是通过复制创建的，发现过程应替换复制的 TCD（从源码重新刷新）。
