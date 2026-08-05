# 规范：基于项目隔离的虚拟环境与容器部署架构

## 问题描述

EasyTest 管理系统目前运行在单一 Docker 容器中，所有测试执行共用容器内的 Python 环境。当不同项目有不同依赖（如不同版本的 `pytest-xdist`、`requests`、`httpx` 等）时，会产生依赖冲突，导致测试执行失败或结果不可靠。

此外，系统需要部署到部门环境，前后端通过容器交付。当前采用单一 `docker-compose` 栈部署，前端、后端 API、Celery Worker 耦合在一起，无法独立更新和扩缩容。

## 解决方案

### 1. 每个项目独立虚拟环境

为每个项目创建独立的 Python virtualenv，存储在共享数据卷中：

```
共享数据卷 /aifs01/.../project/
├── source/
│   ├── project_1/
│   │   ├── requirements.txt   ← 项目依赖
│   │   └── api/test_*.py
│   └── project_2/
│       └── ...
├── reports/
│   └── project_1/...
└── venvs/                      ← 新增
    ├── project_1/
    │   ├── bin/python
    │   └── lib/python3.12/...
    └── project_2/
        └── ...
```

- **懒创建**：首次执行某项目时，自动创建 virtualenv 并安装依赖
- **同步时重建**：每次同步项目代码时，自动重建 virtualenv
- **回退机制**：无 `requirements.txt` 的项目使用容器默认 Python 环境

### 2. 拆分独立部署栈

前后端拆分为独立的 docker-compose 栈，各自独立构建和部署，互不影响。所有服务通过共享的外部网络通信。

```
/project-root/
├── infra/
│   └── docker-compose.yml      ← Redis 独立管理
├── backend/
│   ├── Dockerfile
│   └── docker-compose.yml      ← backend + celery-worker
├── frontend/
│   ├── Dockerfile
│   └── docker-compose.yml      ← frontend
└── docker-compose.yml          ← 可选：整合所有服务（方便本地开发）
```

拆分后，更新某个服务只需操作对应目录：

```bash
# 更新前端
cd /path/to/frontend
docker-compose build && docker-compose up -d

# 更新后端
cd /path/to/backend
docker-compose build && docker-compose up -d
```

## 用户故事

1. 作为测试工程师，我希望项目 A 和项目 B 可以拥有不同的 Python 依赖版本（如 `pytest-xdist` 3.6 vs 2.5），这样我可以独立测试不同版本的被测软件。
2. 作为测试工程师，我首次执行某个项目的测试时，系统自动创建虚拟环境并安装依赖，这样我不需要手动配置环境。
3. 作为测试工程师，我同步项目代码后，虚拟环境自动更新，这样我的依赖始终与最新的 `requirements.txt` 保持一致。
4. 作为测试工程师，我的项目没有 `requirements.txt` 时，测试仍然可以使用系统默认 Python 环境正常执行，这样我无需为简单项目引入额外配置。
5. 作为运维工程师，我更新前端代码时只需要在 frontend 目录执行 `docker-compose build && docker-compose up -d`，这样后端服务不受影响，我可以快速交付前端变更。
6. 作为运维工程师，我更新后端代码时只需要在 backend 目录执行 `docker-compose build && docker-compose up -d`，这样前端服务不受影响，我可以快速交付后端变更。
7. 作为运维工程师，我可以独立部署 Redis 升级，而无需重启应用服务，这样我可以安全更新基础设施而不影响业务。
8. 作为测试工程师，我在 UI 中可以看到项目当前的虚拟环境状态（如是否已创建、依赖数量），这样我可以了解环境的准备情况。
9. 作为测试工程师，我可以在项目设置中手动触发虚拟环境重建，这样当依赖安装出现问题时我可以自行修复。

## 实现决策

### 1. 虚拟环境模块

在 `executor.py` 中新增 `_resolve_python()` 函数：

- 输入：`project_id: int`
- 输出：虚拟环境中 `python` 解释器的绝对路径
- 行为：
  - 如果 `project_id <= 0`，返回 `sys.executable`（系统默认 Python）
  - 如果虚拟环境目录不存在，执行 `python -m venv` 创建
  - 创建后检查 `source/project_{id}/requirements.txt` 是否存在
  - 如果存在，执行 `pip install -r requirements.txt --quiet`
  - 返回虚拟环境的 `bin/python` 路径

### 2. 同步时重建

在 `projects.py` 的 `sync_project()` 端点中，同步完成后异步触发虚拟环境重建：

- 删除旧的虚拟环境目录
- 创建新的虚拟环境
- 安装 `requirements.txt`

采用异步（`asyncio.ensure_future`）方式，不阻塞同步接口的返回。

### 3. 执行时的 Python 路径替换

在 `executor.py` 的 `_execute()` 方法中，构建 `pytest` 命令时：

- 之前：`cmd = [sys.executable, '-m', 'pytest', ...]`
- 之后：`python_path = await _resolve_python(project_id); cmd = [python_path, '-m', 'pytest', ...]`

### 4. 部署架构：拆分独立栈

拆分为三个独立的 docker-compose 栈，通过共享外部网络 `easy-test-net` 通信：

#### infra/docker-compose.yml

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: easy-test-redis
    ports:
      - "16379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

networks:
  default:
    name: easy-test-net
    external: true

volumes:
  redis_data:
```

#### backend/docker-compose.yml

```yaml
services:
  backend:
    image: easy-test-backend:${BACKEND_TAG:-latest}
    build:
      context: .
      dockerfile: Dockerfile
    container_name: easy-test-backend
    ports:
      - "8040:8000"
    environment:
      - DATABASE_URL=mysql+aiomysql://...
      - REDIS_URL=redis://easy-test-redis:6379/0
      - CELERY_BROKER_URL=redis://easy-test-redis:6379/0
      - CELERY_RESULT_BACKEND=redis://easy-test-redis:6379/0
      - PROJECTS_DATA_DIR=/data
      - CORS_ORIGINS=http://localhost:15731,http://frontend:15731
    volumes:
      - /aifs01/zouyang/easytest/project:/data
      - ~/.ssh/id_rsa:/home/appuser/.ssh/id_rsa:ro
      - ~/.ssh/id_rsa.pub:/home/appuser/.ssh/id_rsa.pub:ro
    depends_on:
      redis:
        condition: service_healthy

  celery-worker:
    image: easy-test-backend:${BACKEND_TAG:-latest}
    container_name: easy-test-worker
    command: celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=2
    environment:
      # 同 backend
    volumes:
      # 同 backend
    depends_on:
      redis:
        condition: service_healthy

networks:
  default:
    name: easy-test-net
    external: true
```

#### frontend/docker-compose.yml

```yaml
services:
  frontend:
    image: easy-test-frontend:${FRONTEND_TAG:-latest}
    build:
      context: .
      dockerfile: Dockerfile
    container_name: easy-test-frontend
    ports:
      - "15731:15731"
    restart: unless-stopped

networks:
  default:
    name: easy-test-net
    external: true
```

#### 启动顺序

```bash
# 1. 创建共享网络（仅首次）
docker network create easy-test

# 2. 启动基础设施
cd infra && docker-compose up -d

# 3. 启动后端（等待 Redis 就绪）
cd backend && docker-compose up -d

# 4. 启动前端
cd frontend && docker-compose up -d
```

#### 更新流程

| 变更 | 命令 |
|------|------|
| 更新前端代码 | `cd frontend && docker-compose build && docker-compose up -d` |
| 更新后端代码 | `cd backend && docker-compose build && docker-compose up -d` |
| 更新后端依赖 | `cd backend && docker-compose build --no-cache && docker-compose up -d` |
| 升级 Redis | `cd infra && docker-compose pull && docker-compose up -d` |

### 5. 基础设施

- 共享数据卷继续挂载到所有容器：`/aifs01/zouyang/easytest/project`
- 新增 `venvs/` 子目录，数据卷结构变更为 `source/`、`reports/`、`venvs/`
- MySQL 保持外部独立部署，不动

## 测试决策

### 好测试的标准

- 测试外部行为（API 响应、文件系统状态、执行结果），而非内部实现细节
- 使用 FastAPI `TestClient` 配合临时文件系统
- 每个测试独立运行，使用独立的临时目录和项目 ID
- 优先使用真实的子进程调用而非 mock

### 测试切入点

**最高切入点：API 集成测试**

通过 `POST /api/executions` 触发完整流程，验证虚拟环境被正确创建和使用。需要：
1. 创建测试项目，包含 `requirements.txt`
2. 调用执行 API
3. 验证 `venvs/project_{id}/` 目录被创建
4. 验证 `venvs/project_{id}/bin/python` 存在
5. 验证 `pip list` 中包含 `requirements.txt` 中的依赖

**次高切入点：单元测试**

直接测试 `_resolve_python()` 函数：

| 测试场景 | 输入 | 预期 |
|---------|------|------|
| project_id <= 0 | `project_id=0` | 返回 `sys.executable` |
| 首次创建虚拟环境 | `project_id=1`，无 venv 目录 | 创建目录，安装依赖，返回 venv python 路径 |
| 已有虚拟环境 | `project_id=1`，已有 venv 目录 | 跳过创建，直接返回 venv python 路径 |
| 无 requirements.txt | `project_id=2`，无 req 文件 | 创建 venv，跳过 pip install，返回 venv python 路径 |

### 现有参考

代码库中已有测试基础：`backend/tests/` 目录下的 `test_api.py` 使用 FastAPI `TestClient` 和内存 SQLite 数据库。新测试应遵循相同模式。

## 不在此范围

- **跨项目依赖共享**：不考虑虚拟环境之间的缓存共享或依赖去重
- **Python 版本管理**：所有虚拟环境使用容器内同一 Python 版本，不支持每个项目指定不同 Python 版本
- **容器级隔离**：不使用 Docker-in-Docker 或每个项目独立容器
- **前端依赖管理**：仅涉及后端 Python 依赖，不涉及前端 npm 依赖
- **虚拟环境监控**：不实现 UI 层面的虚拟环境状态监控面板

## 补充说明

- `config.py` 中的 `PROJECTS_DATA_DIR` 和 `PROJECTS_SOURCE_DIR` 已定义，无需修改
- 基础镜像（`python:3.12-slim`）已包含 `venv` 和 `pip`，无需额外安装
- 首次安装依赖可能耗时较久（30-60s），但只在首次执行和同步时发生，后续执行零额外开销
- 如果 `pip install` 失败，虚拟环境仍会被创建（只是不包含依赖），测试仍可使用系统级依赖执行