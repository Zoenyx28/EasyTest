# 03 — 修复 spec 合规：Docker Compose 配置

**What to build:** 使 docker-compose 配置与 `docs/specs/per-project-virtualenv.md` 一致：添加 `depends_on: redis` 依赖、补全 CORS_ORIGINS、移除多余的 `python3-venv` 安装。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 在 `backend/docker-compose.yml` 的 `backend` 和 `celery-worker` 服务中添加 `depends_on: redis (condition: service_healthy)`
- [ ] 在 `backend/docker-compose.yml` 的 `CORS_ORIGINS` 环境变量中添加 `http://frontend:15731`
- [ ] 从 `backend/Dockerfile` 中移除 `python3-venv` 系统包安装（基础镜像已包含）
- [ ] 重建后端镜像并验证容器启动正常
- [ ] 验证前端通过 `http://frontend:15731` 与后端通信正常