# ADR-0016: 领域模型精简 —— 分层资产表合并与模块边界划分

## 状态

提议中（Proposed）

## 关联规范

此 ADR 的具体实施方案见 [需求工作台全流程闭环与架构精简 SPEC](../specs/requirement-workbench-closed-loop.md)。

## 背景

系统用户规模为 **3 名测试 + 3 名开发**。功能场景明确：需求评审、缺陷提交、自动化用例执行、缺陷跟踪。用户目标：**扩展性好、性能好、代码精简可维护**。

当前系统有 25+ 张数据库表，其中需求域独占 15+ 张（PRD V2.0 分层测试设计一次性引入 13 张新表）。同时所有业务逻辑的 CRUD 集中在一个 `crud.py` 文件，所有 API 路由平铺在 `api/` 目录下，没有模块边界。

对 3 人团队而言，这个架构**过度设计**了。

### 当前需求域表清单

| 表 | 用途 | 查询频率 |
|---|---|---|
| `requirements` | 需求主表 | 高频 |
| `requirement_sources` | 需求来源（飞书链接/文件） | 中频 |
| `requirement_analyses` | AI 需求分析结果 | 每次打开工作台 |
| `information_gaps` | 信息缺口 | 低频 |
| `stories` | Story 拆解 | 中频 |
| `requirement_reviews` | 需求评审结果 | 中频 |
| `test_points` | 测试点（树形） | 中频 |
| `test_point_reviews` | 测试点评审 | 中频 |
| `test_scenarios` | 测试场景 | 中频 |
| `scenario_reviews` | 场景评审 | 中频 |
| `generated_cases` | AI 生成的测试用例 | 中频 |
| `case_reviews` | 用例评审 | 中频 |
| `case_bindings` | 生成用例 ↔ 自动化用例绑定 | 中频 |
| `test_strategies` | 自动化策略推荐 | 低频 |
| `review_audits` | AI 评审审计日志 | 低频 |
| `coverage_snapshots` | 覆盖率快照 | 中频 |
| `test_gaps` | 测试缺口 | 低频 |
| `ai_tasks` | AI 任务状态机 | 高频（前端轮询） |

### 问题

1. **表膨胀** — 15+ 张表对 3 人团队来说维护成本远超收益
2. **查询复杂** — 一次工作台加载需要跨 6+ 张表 JOIN
3. **运维脆弱** — 复制一个需求的全部测试资产需要跨 10+ 张表操作
4. **JSON-in-TEXT 反模式** — AI 产出的结构化数据（评分维度、步骤、覆盖率明细）以 JSON 字符串存在 TEXT 列里，数据库无法查询、无法索引
5. **无模块边界** — 全部 CRUD 函数在一个文件，全部路由在一个目录
6. **无迁移工具** — `init_db()` 里手动执行 `ALTER TABLE ... ADD COLUMN`
7. **执行状态在进程内存** — `ExecutionManager` 用 Python dict 存运行状态，进程重启全部丢失

---

## 决策

### 1. 分层资产表合并为统一资产表

将 9 张"同模式"的分层资产表合并为一张 `requirement_assets`：

```text
requirement_assets
├── id                (PK)
├── requirement_id    (FK → requirements.id)
├── asset_type        ENUM('analysis','story','test_point','test_point_review',
│                          'scenario','scenario_review','case','case_review','strategy')
├── parent_id         (自引用 FK, 支持树形: Story→TestPoint 树, TestPoint→Scenario)
├── story_id          (可选, 用例关联的 Story)
├── title             VARCHAR(512)
├── content           JSON    (MySQL JSON / PostgreSQL JSONB, 存所有可变结构化数据)
├── score             INT     (100分制, 0表示不适用)
├── gate_status       VARCHAR(16)  (PASS/WARNING/BLOCKED/'')
├── review_comment    TEXT
├── sort_order        INT
├── status            VARCHAR(16)  (generated/reviewed/confirmed, 仅部分类型使用)
├── created_by        INT
├── created_at        DATETIME
└── updated_at        DATETIME

索引:
  - (requirement_id, asset_type)
  - (parent_id)
  - (story_id)
```

**保留独立不合并的表：**

| 表 | 原因 |
|---|---|
| `requirements` | 需求主表，状态机核心。**来源信息（飞书链接/文件名/提取状态）直接作为字段并入此表**，不再需要独立的 `requirement_sources` 表 |
| `case_bindings` | 多对多关联表，独立合理 |
| `review_audits` | 审计日志，不可变，只追加，与可变资产生命周期不同 |
| `ai_tasks` | AI 任务状态机，高频轮询，独立合理 |

**`requirement_sources` 不再保留。** 理由：

- 需求来源（飞书链接、上传文件、粘贴文本）只是**输入通道**，不是核心领域概念
- 提取完的正文已经是 `requirements.content`（MEDIUMTEXT），用户打开需求直接预览统一格式
- 溯源只需要两个字段：`source_type`（lark/file/text）+ `source_meta`（JSON：链接/文件名/提取状态/错误信息）
- 当前系统把来源当作独立聚合根，实际上它是需求的属性——删掉需求，来源也删掉；没有需求，来源没有独立存在的意义

```text
requirements（精简后）
├── id, project_id, branch_id
├── title, content (MEDIUMTEXT)
├── priority, status (状态机)
├── source_type    ENUM('lark','file','text')  ← 多模态输入标记
├── source_meta    JSON                        ← 溯源+提取状态
│     {link, filename, file_size, mime_type,
│      extracted, extract_error}
├── created_by, created_at, updated_at
```

**效果：** 需求域从 17 张表缩减到 **5 张**（减少约 70%）。需求详情页一次查询不再需要 JOIN `requirement_sources`。

### 2. MySQL JSON 列替代 TEXT 存 JSON

所有 AI 产出的结构化内容（评分维度、步骤、覆盖率明细、问题清单、建议列表）使用 MySQL 原生 **JSON 列类型**：

- 支持 `JSON_EXTRACT` 路径查询
- 可建虚拟列 + 索引（如对 `content->>'$.score'` 建索引）
- 数据库层直接做过滤："查出所有 score < 60 的 Story"
- 同时保留 schema 灵活性（AI 输出字段可能随 prompt 版本变化）

### 3. 按限界上下文拆分模块

```
backend/app/
├── domains/
│   ├── test_execution/      # Task, Execution, ExecutionCase, Report, ExecutionManager
│   │   ├── models.py
│   │   ├── crud.py
│   │   └── api.py
│   ├── defect_tracking/     # Defect, DefectModule, DefectLog, DefectComment, DefectAttachment
│   │   ├── models.py
│   │   ├── crud.py
│   │   └── api.py
│   ├── requirement_design/  # Requirement, RequirementAsset,
│   │   ├── models.py        #   CaseBinding, AITask, ReviewAudit, CoverageSnapshot
│   │   ├── crud.py
│   │   └── api.py
│   └── project_mgmt/        # Project, Branch, ProjectMember, ProjectNote
│       ├── models.py
│       ├── crud.py
│       └── api.py
└── shared/                  # 共享基础设施
    ├── database.py          # 数据库引擎、session
    ├── auth.py              # JWT 认证、中间件
    ├── models.py            # User, LLMSettings, UserLarkBinding
    ├── common.py            # ok/fail 响应信封
    └── file_signer.py       # 文件签名
```

每个 domain 内部自治，通过 `shared` 引用公共模块。添加新功能时只需在对应 domain 内部修改，不会影响其他 domain。

### 4. 迁移工具从手动 ALTER TABLE 升级为 Alembic

`init_db()` 中的手动 SQL 语句（当前 50+ 行 ALTER TABLE）由 Alembic 迁移脚本替代，每次变更生成可追溯、可回滚的迁移文件。

### 5. 关于 PostgreSQL 和 RAG 的裁决

用户提出两个进一步的改进方向。经评估：

**PostgreSQL → 不采纳（当前阶段）**

- PostgreSQL JSONB 比 MySQL JSON 更成熟，但在 3 用户规模下性能差距为零
- 迁移成本（SQL 方言差异、数据迁移）超过收益
- **建议：** 先完成表合并和模块拆分。如果未来需要 JSONB 高级查询或全文搜索，届时迁移。表少了，迁移也简单。

**RAG → 不采纳（当前阶段）**

- RAG 将文档分块存入向量数据库，AI 只检索相关块。适用于需求文档很大（50 页+）且有大量历史需求需要参考的场景
- 本系统需求文档通常在 1-5 页，完整放入 LLM 上下文窗口绰绰有余
- RAG 引入额外基础设施（向量数据库 + embedding 模型）和分块策略，增加了运维复杂性
- RAG 还有精度损失：AI 只看片段可能漏掉跨章节的上下文
- 当前瓶颈是 LLM 调用本身（秒级），加 RAG 只会增加总延迟（embedding 调用 + LLM 调用）

**版本内需求多次更新的变更影响分析 → 走追溯链，不走 RAG**

当项目内一个需求多次修改时，核心问题是"哪些测试资产受变更影响需要重新生成"，不是"从大量历史文档中检索相关知识"：

```text
需求变更 → diff 变更段落 → 追溯链找到依赖的 Story/TestPoint/Scenario/Case
→ AI 判断是否受影响 → 标记 stale → 重新生成 stale 链
```

`requirement_assets` 的 `parent_id` 树形结构天然支持这个追溯——从需求出发，沿 parent 链向下找到所有受影响资产。零新基础设施，一次 DB 查询 + 一次 LLM 调用即可完成影响分析。RAG 对此场景没有帮助，反而增加了不必要的复杂度。

- **建议：** 不引入 RAG。需求多次更新走追溯链 + stale 标记方案。等需求文档规模或跨项目历史积累显著增长时重新评估 RAG。

---

## 备选方案

| 方案 | 评估 |
|------|------|
| **保持 15+ 表不动** | 与 PRD V2.0 概念一一对应，数据模型"书面上"清晰。但 3 人团队不需要这种颗粒度。查询/复制/变更成本高于收益。**不采纳。** |
| **完全 NoSQL（MongoDB）** | 分层资产天然适合文档模型。但与现有 MySQL 基础设施冲突，引入新运维依赖。**不采纳。** |
| **PostgreSQL 替代 MySQL** | JSONB 更优，全文搜索内置。但当前瓶颈不在数据库，迁移成本 > 收益。**暂不采纳，保留为未来选项。** |
| **RAG 增强 AI** | 文档分块检索。但当前文档规模小，引入基础设施成本和精度损失。**暂不采纳，保留为未来选项。** |

---

## 后果

### 正面

- **精简**：需求域从 17 表 → 5 表，开发者心智负担显著降低
- **查询简化**：工作台一屏数据从多表 JOIN 变为单表 WHERE 查询
- **可维护**：模块边界清晰，改缺陷不影响执行，改需求不影响项目
- **可扩展**：新 domain 可以直接加目录，不碰已有代码
- **可迁移**：Alembic 提供可追溯、可回滚的数据库变更历史

### 负面

- **一次性迁移工程**：现有 15+ 表数据需要迁移到新表结构，需写数据迁移脚本
- **导入路径变更**：模块拆分后所有 import 需要更新，需一次全局重构
- **放弃概念一一对应**：PRD V2.0 中每层独立表的"概念清晰性"被换取运维简单性（已显式裁决）
- **JSON 列不可完全替代关系型查询**：复杂的跨资产关联仍需应用层处理。但当前场景下这种查询极少，可接受

---

## 实施优先级

| 优先级 | 事项 | 理由 |
|--------|------|------|
| **P0** | 分层资产表合并（17→5） | 直接降低维护成本，是后续所有工作的基础 |
| **P0** | 模块边界拆分 | 使代码可独立理解、修改、测试 |
| **P1** | Alembic 迁移工具 | 替代脆弱的 init_db() 手动 SQL |
| **P1** | MySQL JSON 列 | 让数据库能查询结构化内容 |
| **P2** | 执行管理器状态迁移到 Redis | 进程重启不丢状态，支持 WebSocket 重连 |
| **P3** | PostgreSQL 迁移 | JSONB/全文搜索成为刚需时再动 |
| **P3** | RAG 引入 | 文档规模或历史积累显著增长时再评 |
