# chatgpt-use 安全适配边界

固定上游提交：`ecb204d4f4a4aef127851240af17dcf1a321afbc`（Cargo 版本 0.0.11）。

本项目选择移植它的 **Mode 1 / 单次 ask + 结构化委派**，不是安装原版二进制后调用其全部功能。

| 上游能力 | 本项目集成 |
| --- | --- |
| DelegationPacket | 保持 goal/summary/plan/risks/tests/acceptance/do_not_do/verdict 及 PlanStep 字段 |
| plan/review prompt | 在 Python 中适配，加入 Superpowers 方法、显式上下文和预算 |
| 返回 envelope | 浏览器内部返回 status/result.text；先落盘，再校验 packet |
| 原始协议参考 | `delegation.upstream.rs` 原样保留，`manifest.json` 固定 SHA-256 |
| parser | 比原版更严格：拒绝周围散文、多对象、未知字段、缺少验收项的执行计划 |
| 浏览器通道 | 完全替换为专用配置 + 用户手动登录 + Playwright 可见 DOM 操作 |
| handoff | 本地 CLI 生成任务书，通过 stdin 交给 Codex；默认预览 |
| run/serve/mcp/work | 不提供，不导出本机工具或终端到网页 |

移植实现位于 `gpt_orchestrator/core.py`；受限浏览器实现位于 `browser.py`。协议引用和改写遵循本目录 MIT LICENSE。`upstream.lock.json` 与本目录 manifest 说明来源和文件校验值。

原版还包含 chrome-use 自动配置探测、网页会话信息和私有接口访问逻辑；本项目不执行这些代码。不会自动安装原版 chatgpt-use、chrome-use、cookie-use，也不会创建隧道、共享 token、本地 MCP 工具服务器或“永远允许终端”的授权。

取舍：放弃原版更宽泛的兼容与全自动本机工具循环，保留规划/审查与可核对交接。页面选择器变化可能需要维护；手动复制/粘贴始终是无需此浏览器自动化的替代路径。
