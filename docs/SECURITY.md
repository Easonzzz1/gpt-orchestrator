# 会话边界与非官方自动化风险

本项目的网页适配层不是 OpenAI 官方 API，也没有保证其获得平台支持。网页自动化可能受到服务条款、工作区策略或账号使用规则限制；可能出现限流、临时访问限制、功能变化和账号风险。使用前应核对你当前账户适用的规则。项目不绕过限流、CAPTCHA、登录验证或访问控制；遇到这些情况立即停止，改用手动 Chat 交接。

## 实现方式

使用 Playwright 官方公开的 `launch_persistent_context` 浏览器接口（这里的“公开/官方”指 Playwright，不代表 OpenAI 认可该自动化用途）。创建专用 Chrome 配置，用户手动在真正的登录页面完成认证。会话状态由浏览器自行保存，浏览器会正常使用自己的认证信息打开页面。

适配层只定位可见编辑器、发送按钮、回答、停止按钮、复制按钮和提示弹窗。不读取或导出 Cookie、登录数据库、Keychain、Local Storage、`storage_state`、session token 或 OAuth token；不打开日常浏览器的配置、不探测已有登录账号、不暴露 CDP 端口、不调用 ChatGPT 私有后端 API，不用认证 fetch。浏览器网络本身仍然受浏览器/网站正常行为控制。

上游 chatgpt-use 的 `channel.rs` 在探测已有 profile、读取网页会话、私有接口访问方面与这个边界不一致，因此本项目**不执行原版 CLI/通道**。集成的是 MIT 协议移植、单次委派模式及原始协议源码，浏览器操作由自己的受限实现提供。

## 保管与外发

- `.state/browser-profile/` 是敏感浏览器配置，文件夹权限 0700；所有同用户进程仍可能读取它，权限不能防御已经控制本机的程序。不要提交、同步、压缩分发或上传。
- 提示词、计划、Codex 输出与检查日志保存在 `runs/` 中，可能含业务数据。不要上传整个运行目录。发布归档排除状态、日志、虚拟环境与本地配置。
- 只传显式选择的相对路径文本文件。拒绝逃出 workspace 的路径/符号链接、隐藏文件和明显凭据文件名；对部分常见密钥格式做启发式扫描。**这不是完整脱敏器**，发送前仍需检查。
- 不自动上传整个仓库、diff 或原始日志。审查上下文由用户显式整理和选择。
- `--sensitive` 禁止 CLI 发起任何模型派发；你选用的本地检查程序本身是否联网，不由路由器保证。
- Codex 使用正常登录与现有用户配置，项目不会读取其认证文件；它仍可能使用已配置的 API 身份。若需订阅登录，请在 Codex 正常登录流程中自己确认。CLI 不判断真实计费身份。

## 重试、执行和验收

每个 run 有独占锁；所有浏览器调用共用一个专用配置锁。提交边界前先原子写入 `unknown` 状态。调用可能提交后，绝不自动重发。每个 run 默认最多 2 次网页请求（规划、审查）和 2 次 Codex 尝试。

每次 Codex 执行有 `workspace-write` 沙箱、单次超时、显式 `--apply`，不会设置危险 bypass。现有 hooks/MCP、仓库代码以及目标程序依赖依然需要信任；这些配置不由本项目改写。`verify --apply -- ...` 执行你明确给出的本地 argv，没有 shell 拼接，也不提供额外沙箱。任何程序的副作用都需要结合命令和目录判断。

超时或中断后终止该执行进程组并保留不确定状态；更广的后台/系统副作用不能由 Python 完全撤销。重试需先检查实际工作区和证据，再显式 `--retry --apply`，不能用它绕过账号限流。

验收需要实际检查、当前计划对应的成功执行、有效审查与人工确认。重新执行、导入新计划或新增检查会使旧审查失效。项目无法证明你选择的检查涵盖所有需求，也无法检测任意外部编辑；工作区变化后必须重新检查并生成新审查。失败不会自动 reset/clean 工作区，不会覆盖用户已有修改。

## 上游与参考

- [chatgpt-use](https://github.com/leeguooooo/chatgpt-use)，固定提交见 `upstream.lock.json`。
- [Superpowers](https://github.com/obra/superpowers)，所选 Skill 与目录内参考资源保留 MIT 许可。
- [Playwright persistent context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)。
- [OpenAI 非交互执行](https://learn.chatgpt.com/docs/non-interactive-mode)与[使用限制](https://learn.chatgpt.com/docs/pricing)。
