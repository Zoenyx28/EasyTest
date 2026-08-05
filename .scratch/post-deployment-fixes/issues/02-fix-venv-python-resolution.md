# 02 — 修复 spec 合规：虚拟环境 Python 解析

**What to build:** 使虚拟环境 Python 解析逻辑与 `docs/specs/per-project-virtualenv.md` 完全一致：函数名改为 `_resolve_python`，且无 `requirements.txt` 的项目不创建 venv，直接使用系统 Python。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 将 `_ensure_venv_python` 重命名为 `_resolve_python`，更新所有调用方
- [ ] 修复回退机制：当 `project_id > 0` 但项目目录下无 `requirements.txt` 时，不创建 venv，直接返回 `sys.executable`
- [ ] 更新 `projects.py` 中同步时重建虚拟环境的逻辑，使其与 `_resolve_python` 的行为一致
- [ ] 验证：有 `requirements.txt` 的项目仍能正常创建 venv 并安装依赖
- [ ] 验证：无 `requirements.txt` 的项目使用系统 Python 执行测试