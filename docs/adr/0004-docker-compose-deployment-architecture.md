# ADR-0004: Docker Compose 部署架构

## Status

Accepted

## Context

项目需要部署到团队服务器（10.19.195.109）。服务器存在以下约束：

- **访问方式受限**：只能通过 SSH 工具连接，无 CI/CD 流水线（Jenkins 存在于 10.19.28.137，但暂未接入）。
- **外网访问不稳定**：无法直接访问 Docker Hub、registry.npmjs.org、files.pythonhosted.org 等外网源；部分国内镜像（registry.nrbewqda.mirror.aliyuncs.com 等）也已失效。
- **已有基础设施**：服务器已安装 Docker（v26+）与 docker compose v2，本地有 10.19.195.109:5000 的私有 Registry，部分基础镜像（`python:3.12-slim`、`node:20-alpine`、`nginx:alpine`、`redis:7-alpine`）已缓存在服务器上。

系统由三个部署单元组成：

| 组件 | 组成 | 构建来源 |
|---|---|---|
| **Frontend** | nginx 托管 Vue SPA | `frontend/Dockerfile`（node 构建 + nginx 托管） |
| **Backend** | FastAPI API + Celery Worker | `backend/Dockerfile`（同一镜像，不同启动命令） |
| **Infra** | Redis（Celery broker/result）、MySQL | 官方镜像 |

## Decision

1. **部署方式**：使用 docker-compose 定义全部服务（frontend、backend-api、celery-worker、redis、mysql），单项目 `easytest`，统一网络 `easytest_app-network`。

2. **镜像策略（过渡期，当前生效）**：在 Jenkins 接入之前，镜像采用手动构建 + 本地标签方式：
   - 标签格式：`easy-test-<component>:v<N>`（如 `easy-test-backend:v2`、`easy-test-frontend:v2`）。
   - 构建方式二选一：
     - 在服务器上直接 `docker compose build`（需网络可用的国内源：pip 用阿里云 PyPI + 600s 超时，npm 用 npmmirror）。
     - 本地（有外网的开发机）构建后 `docker save` → scp → 服务器 `docker load`。
   - 升级流程：构建新标签镜像 → 修改 docker-compose.yml 的 `image:` 标签 → `docker compose up -d`。

3. **镜像策略（目标态，Jenkins 接入后）**：镜像推送到私有 Registry `10.19.195.109:5000`，compose 引用 `10.19.195.109:5000/easytest-<component>:<tag>`，由 Jenkins 触发构建与发布。

4. **Base 镜像来源**：优先使用服务器已缓存的镜像；`nginx:stable-alpine` 不可得时使用 `nginx:alpine` 替代。

5. **配置管理**：环境变量（数据库连接、Redis 地址、项目数据目录等）直接写在 docker-compose.yml 的 `environment:` 中；敏感配置通过 `./config/.env` 挂载。

6. **数据库迁移**：手动 SSH 到服务器执行，不随容器启动自动运行。

## Consequences

- **Positive**: 单机 docker-compose 部署简单直接，无需额外基础设施，符合团队现状。
- **Positive**: 手动标签方式不依赖私有 Registry 可用性，镜像可离线传输（save/load）。
- **Positive**: 过渡期方案与目标态（registry + Jenkins）兼容，切换时只需改镜像标签前缀和推送环节。
- **Negative**: 手动更新存在人为操作风险（标签写错、漏更新 compose），且无回滚自动化。
- **Negative**: 服务器外网受限，首次构建需要国内镜像源或离线传镜像，流程偏重。
- **Negative**: Backend 镜像同时承载 API 与 Worker，二者无法独立升级。
