# 01 — 移除调试埋点代码

**What to build:** 移除 `discovery.py` 和 `projects.py` 中向 `127.0.0.1:7777/event` 发送调试请求的残留代码，消除无意义的网络开销和潜在的安全风险。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 定位并删除 `discovery.py` 中所有向 `127.0.0.1:7777` 发送 HTTP 请求的 `#region debug-point` 代码块
- [ ] 定位并删除 `projects.py` 中所有向 `127.0.0.1:7777` 发送 HTTP 请求的 `#region debug-point` 代码块
- [ ] 确认相关路由没有被外部依赖引用
- [ ] 验证 `POST /api/projects/{id}/sync` 仍正常返回