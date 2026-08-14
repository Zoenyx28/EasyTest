# EasyTest — AI 测试设计与测试管理平台

> 覆盖「需求 → AI 测试设计 → 自动化 → 执行 → 覆盖率 → 补测」全链路的测试管理与 AI 测试设计平台。
> AI 负责理解、拆解、评估、建议和生成；产品负责业务事实确认；测试工程师负责测试质量确认。

## 核心链路

```text
Requirement → 需求分析 → Story → Story评审 → 人工确认 → TestPoint
→ TestPoint评审 → 人工确认 → TestScenario → 生成用例 → 用例评审
→ 测试策略 → 自动化绑定 → 执行 → 覆盖率 / 风险 → TestGap → AI补测
```

每一层 AI 生成后都经过 **AI Review → QualityGate → 人工确认** 才进入下一层，AI 生成不是终点，形成持续质量闭环。

## 功能特性

### 📋 测试项目管理与版本隔离

- **Project + Branch（版本）**：数据按分支完全隔离（测试用例 / 任务 / 执行 / 报告均带 `branch_id`）
- **用例自动发现**：对项目源码运行 `pytest --collect-only` 自动导入测试用例定义（API / UI）
- **任务批量执行**：自由组合用例集，支持异步执行、并行（pytest-xdist）与报告生成（Allure / JSON）

### 🤖 需求驱动的 AI 测试设计（Phase 3）

- **需求来源多样**：手工输入、上传文件（txt/json/md/doc/docx/pdf/截图）、**飞书文档链接**、项目代码
- **QA Orchestrator + 12 专业 Agent**：需求分析 / Story 设计 / Story 评审 / 测试点设计 / 测试点评审 / 场景设计 / 用例生成 / 用例评审 / 策略建议 / 自动化建议 / 执行分析 / 覆盖率分析
- **分层逐步推进**：先理解（需求分析）→ 拆解（Story）→ 测什么（TestPoint）→ 在什么业务情况下测（TestScenario）→ 生成用例
- **AI 评审与质量门**：每个环节输出多维评分（100 分制）、评分原因、Issues、Suggestions 与 QualityGate（PASS / WARNING / BLOCKED），评分与 Gate 全程可审计
- **双角色人工确认**：产品经理确认业务事实，测试工程师确认测试可行性，可要求 AI 携带评论重新生成
- **AI 任务状态机**：`PENDING → RUNNING → REVIEW → WAITING_HUMAN → CONFIRMED → NEXT_STAGE`，异常可 `FAILED → RETRY`
- **覆盖率与补测闭环**：按层计算覆盖率、识别 TestGap（P0/P1 分级）并由 AI 驱动补测

### 🐞 缺陷管理

- 遵循**禅道缺陷生命周期**：未确认 → 已确认 → 处理中 → 已解决 → 已关闭（支持激活回退）
- 严重程度 / 优先级 P0–P3，解决方案枚举，多选附件，模块树分类
- 完整操作审计日志（创建 / 指派 / 确认 / 解决 / 关闭 / 激活 / 评论）

### 👥 用户与项目协作

- 注册 / 登录 / 修改密码，**JWT** 认证（7 天有效期），bcrypt 密码哈希
- 项目成员管理（添加 / 移除，创建者不可移除）、项目 Markdown 备注

### 🔗 飞书集成

- 通过 **lark-oapi** 官方 SDK 读取飞书文档正文作为需求来源，用户 token 加密存储
- OAuth 授权流程 + 文档链接一键加载

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · aiomysql · Celery · Redis |
| 前端 | Vue 3 · TypeScript · Vite · TailwindCSS 4 · Vue Router |
| 认证 | JWT · passlib/bcrypt |
| AI | 可配置 LLM Provider（文本 + 视觉模型），QA Orchestrator 多 Agent 编排 |
| 测试 | pytest · pytest-xdist · pytest-json-report · allure-pytest |
| 部署 | Docker · Docker Compose（MySQL / Redis / API+Celery / Nginx+Vue SPA） |

## 项目结构

```text
.
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/          # 路由层（auth / projects / defects / requirements / workbench / settings 等）
│   │   ├── domains/      # 领域逻辑（requirement_design 等）
│   │   ├── services/     # 服务层（feishu_client / requirement_agent 等）
│   │   ├── db/           # 数据模型与 CRUD
│   │   ├── main.py       # FastAPI 入口
│   │   └── config.py     # 集中配置（读取根目录 .env）
│   ├── tests/            # 后端测试
│   └── Dockerfile
├── frontend/             # Vue 3 前端
│   ├── src/components/   # 视图与组件（TestProjectsView / RequirementWorkbench / DefectView 等）
│   └── Dockerfile
├── infra/                # 基础设施（Redis / MySQL）
├── data/projects/        # 项目数据（测试用例 / 报告 / 附件，.gitignore 外挂载）
├── docs/                 # 设计文档
│   ├── adr/              # 架构决策记录（ADR）
│   └── specs/            # 规格与 PRD
├── CONTEXT.md            # 领域术语表
├── design.md             # 前端设计规范
└── docker-compose.yml    # 本地开发便捷编排
```

## 快速开始

### 环境要求

- Docker + Docker Compose
- Python 3.12（本地开发后端）
- Node.js 18+（本地开发前端）
- MySQL + Redis（或使用 `infra/` 编排）

### Docker 部署

```bash
# 1. 创建共享网络
docker network create easy-test-net

# 2. 基础设施（Redis / MySQL）
cd infra && docker-compose up -d && cd ..

# 3. 后端（API + Celery Worker，端口 8040）
cd backend && docker-compose up -d --build && cd ..

# 4. 前端（Nginx + Vue SPA，端口 15731）
cd frontend && docker-compose up -d --build && cd ..

# 访问 http://localhost:15731
```

> 镜像标签格式 `easy-test-<component>:<version>`（如 `easy-test-backend:v2`），可通过 `BACKEND_TAG` / `FRONTEND_TAG` 覆盖。

### 本地开发

**后端**

```bash
# 在项目根目录创建 .env（参考下方配置表）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8040 --reload
```

**前端**

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 自动代理到 :8040
```

## 配置（根目录 .env）

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `DATABASE_URL` | MySQL 连接串 | `mysql+aiomysql://user:pass@host:port/db?charset=utf8mb4` |
| `REDIS_URL` | Redis 连接串 | `redis://:pass@host:6379/0` |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery Broker / 结果后端 | 复用 `REDIS_URL` |
| `JWT_SECRET` | JWT 签名密钥（生产必须更换） | 开发默认值 |
| `PROJECTS_DATA_DIR` | 项目数据存储目录 | `./data/projects` |
| `FILE_SIGN_SECRET` | 文件访问签名密钥（生产必须更换） | 开发默认值 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书开放平台应用凭证 | 空 |
| `FEISHU_REDIRECT_URI` | 飞书 OAuth 回调地址（需配置白名单） | 空 |
| `FEISHU_TOKEN_ENC_KEY` | 飞书用户 token 加密密钥 | 从 `JWT_SECRET` 派生 |
| `CORS_ORIGINS` | 前端跨域白名单（逗号分隔） | 本地默认 |

## 测试

```bash
# 后端测试
cd backend && python -m pytest tests/ -v
```

## 文档索引

- [CONTEXT.md](CONTEXT.md) — 领域术语表与核心实体说明
- [docs/specs/AI QA Agent 测试设计与测试管理平台 PRD.md](docs/specs/AI%20QA%20Agent%20测试设计与测试管理平台%20PRD.md) — 产品需求文档（PRD V2.0）
- [docs/specs/requirement-workbench-closed-loop.md](docs/specs/requirement-workbench-closed-loop.md) — 需求工作台闭环设计
- [docs/adr/](docs/adr/) — 架构决策记录（ADR）
- [design.md](design.md) — 前端设计规范
