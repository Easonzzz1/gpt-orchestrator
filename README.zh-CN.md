[English](README.md)

# GPT Orchestrator：Chat 规划与审查，Codex 执行

离线用量报告：`python3 scripts/usage_report.py examples/usage.synthetic.jsonl`。缓存输入仍属于总输入，缺失数据保留为未知，不推算订阅额度或账单。详见 [复盘方法](docs/MEASUREMENT.md)。

一个可在 macOS / Linux 本地运行的 Python 项目。默认离线生成路由建议和任务书；需要模型时，优先用 Chat 做规划与审查，让 Codex 专注于修改代码、执行检查。文档/表格/幻灯片等任务输出 Work 交接材料。

路由表达的是减少重复交接与限制调用次数的偏好，不能保证最低价格或某个额度池。使用限制以[官方说明](https://learn.chatgpt.com/docs/pricing)和实际账户页面为准。项目不读取账户配额，不使用 API Key，也不会把 Chat 订阅包装成官方 API。

## 已集成的内容

- **Superpowers**：固定提交的 6 个 MIT Skill 及其目录内参考资源随项目提供；安装脚本只发现顺序执行所需的 6 个 Skill 和自定义 Skill，不启用上游 hooks 或并行工作流。
- **chatgpt-use**：移植 `DelegationPacket` 协议与单次 `ask → packet → handoff` 模式；保留带校验值的原始协议源码和许可证。原版浏览器通道由本项目的安全适配层替换。**这不是安装/透传原版 chatgpt-use CLI**；不支持它的 `run/serve/mcp/work`。详见 [集成边界](integrations/chatgpt-use/README.md)。
- **gpt-orchestrator Skill**：分类、Chat/Work/Codex 路由、模型层级、Execution Brief、验收和回退规则。
- **CLI**：离线路由、手动/浏览器规划、严格计划导入、Codex 执行、本地检查、Chat 审查、人工验收确认。

## 快速开始：无需登录、无需模型调用

需要 Python 3.9+；代码执行另需已安装并登录的 Codex CLI。浏览器自动化为可选项，需要已安装的 Google Chrome 和 Playwright。Windows 请使用 WSL，本项目的文件锁与进程终止逻辑面向 macOS/Linux。

在本项目目录执行：

```sh
sh scripts/install.sh
./gpt-orchestrator-cli doctor
./gpt-orchestrator-cli route --task '修复 Python 程序中的输入校验' --kind code
./gpt-orchestrator-cli brief --task-file examples/tasks/code.md \
  --kind code --workspace "$PWD/examples/demo-workspace" --out runs/demo
```

上面不会调用任何模型。`runs/demo/` 中会出现 `run.json`、`execution-brief.md` 和 `plan-request.md`。最后一个目录必须不存在，避免误覆盖。

安装脚本支持重复运行，不覆盖已有配置和其他技能。若要让另一个代码项目发现这些技能：

```sh
sh scripts/install.sh --skills-dir /absolute/path/to/your-project/.agents/skills
```

它仅向指定位置添加链接；冲突即停止。保持本项目位置不变，或移动后重新安装链接。重新打开目标项目/新建 Codex 会话以发现技能；可显式使用 `$gpt-orchestrator`。不会修改你的全局 Codex 配置。

## 配置与模型成本

`config.example.json` 是无凭据示例；安装生成本地 `config.json`。`models.cheap/standard/strong` 是本项目的逻辑别名，默认均为 `null`。请填入**你的账户实际支持的模型 ID**，不能把网页的展示名称直接当 CLI ID。项目不替你猜模型可用性，也不自动切换网页模型。

```json
{
  "models": {"cheap": null, "standard": null, "strong": null},
  "max_codex_calls": 2,
  "max_web_calls": 2,
  "timeout_seconds": 900,
  "context_limit_bytes": 40000
}
```

可以只保留需要覆盖的键；其余从示例合并。`--config /absolute/config.json` 必须放在子命令之前。

模型策略：本地确定性工具 → 简单任务用 cheap → 中等任务 standard → 确有复杂依赖的任务 strong。同一诊断失败两次即停下，提供证据后显式升级。没有后台重试、隐式付费 API 或并行 workers。

没有填写模型时，`execute` 会拒绝。若你明确愿意用 Codex 已配置的默认模型，可以用 `--use-codex-default`；其价格/额度消耗仍然未知。两次调用上限仅限制尝试次数，不限制每次 token、金额或额度百分比。

## 完整流程：手动 Chat 模式

这是最稳定的路径，也适合作为网页自动化故障时的回退。

1. 读取 `runs/demo/plan-request.md`，确认任务与上下文可以发送。复制到 ChatGPT **Chat** 中；选择你账户里合适的模型。无需给 Chat 本地终端或文件权限。
2. 将 Chat 返回的一个 JSON 对象（或单个 json 代码块）保存到 `runs/demo/chat-plan.txt`，然后导入：

```sh
./gpt-orchestrator-cli import-packet --run runs/demo --file runs/demo/chat-plan.txt
```

3. 查看 `execution-brief.md`，确认范围、步骤、测试和验收。先预览再执行：

```sh
./gpt-orchestrator-cli execute --run runs/demo --use-codex-default
./gpt-orchestrator-cli execute --run runs/demo --use-codex-default --apply
```

配置了模型时省略 `--use-codex-default`。CLI 通过 stdin 把任务书交给 `codex exec --sandbox workspace-write`，不设置 bypass/full-access。Codex 使用你现有的正常登录方式与规则；继承配置中的 hooks/MCP 等仍可能生效，请自行确认环境。[官方非交互执行说明](https://learn.chatgpt.com/docs/non-interactive-mode)。

4. 执行你审核过的检查命令，记录真实退出码；这一步不会执行计划里模型提供的命令字符串：

```sh
./gpt-orchestrator-cli verify --run runs/demo --apply -- python3 -m unittest -v
```

检查在创建 run 时选定的 workspace 中运行。`verify` 是**显式本地命令执行**，不提供额外操作系统沙箱；只传入你信任的命令。命令的输出保存在 run 内，默认不发送给 Chat。失败检查保留在记录中；修复后如需重新验收，导入修订后的计划、重新执行和检查，而不是删掉失败证据冒充通过。

5. 审查实际变更。手动把脱敏后的 diff、测试结果和验收观察写入 workspace 下的 `review-context.txt`，然后：

```sh
./gpt-orchestrator-cli review --run runs/demo --file review-context.txt
```

把生成的 `review-request.md` 交给 Chat，将回复保存为 `runs/demo/chat-review.txt`：

```sh
./gpt-orchestrator-cli import-packet --run runs/demo --stage review --file runs/demo/chat-review.txt
./gpt-orchestrator-cli accept --run runs/demo --confirm-acceptance
./gpt-orchestrator-cli status --run runs/demo
```

`accept` 要求真实记录的检查全部通过、当前计划已成功执行、审查为 `proceed`，并由你确认可观察的验收项。它不会自动证明任意自然语言标准；检查不充分、未提供 diff 或目标文件后来变化时，需要重新检查/审查。它只追踪自己的执行与检查记录，无法检测所有外部编辑。

示例协议回复在 `examples/plan-packet.json`；可以离线导入以练习格式，**它不是你的项目已完成规划或审查的证明**。

## 可选：专用浏览器自动规划/审查

先读 [SECURITY.md](docs/SECURITY.md)。使用的是 Playwright 的公开浏览器控制接口，不是 OpenAI 官方 Chat 自动化接口。

```sh
sh scripts/setup-browser.sh
.venv/bin/python -m gpt_orchestrator browser-login --allow-web
```

首次打开一个全新的独立浏览器配置。**由你手动登录**并选择模型，完成后在终端按 Enter；登录状态只由浏览器保存在项目 `.state/browser-profile/`。不要使用日常浏览器配置，不导出、复制、粘贴 Cookie 或 token。该目录含敏感登录状态，不要上传或打包。

创建一个新的 run 并提交一次规划：

```sh
.venv/bin/python -m gpt_orchestrator plan \
  --task-file examples/tasks/code.md --kind code \
  --workspace "$PWD/examples/demo-workspace" --out runs/browser-demo \
  --backend browser --allow-web
```

每次请求从新对话开始，读写可见编辑器和回答内容。原始回答先保存，验证协议后才交给执行器。不会自动选择网页模型；使用你手动选定、网页实际呈现的模型。

执行和检查完成后，可以用同一个 run 发起一次网页审查：

```sh
.venv/bin/python -m gpt_orchestrator review --run runs/browser-demo \
  --file review-context.txt --backend browser --allow-web
```

网页改版、登录失效、弹窗、CAPTCHA、限流、响应不完整都会中止。提交状态不明时不重发、不切换提供商；打开专用浏览器查看已有对话，把答案手动保存并 `import-packet`。必要时在另一个浏览器手动复制提示词，先确认前一次没有提交。`plan-response.json` / `review-response.json` 保留已收到但解析失败的回复。

目前默认用已安装 Chrome。若改为 `browser.channel="chromium"`，需在相同 `PLAYWRIGHT_BROWSERS_PATH` 下安装和运行 Chromium；交付不附带浏览器下载。选择器集中在配置中，按实际网页可见元素调整。存在显示条件差异时，适配层会超时，而不是假定生成已经完成。

## 路由举例与限制

```sh
./gpt-orchestrator-cli route --task-file examples/tasks/reasoning.md
./gpt-orchestrator-cli route --task-file examples/tasks/artifact.md --kind artifact
./gpt-orchestrator-cli route --task '运行已有的本地检查' --kind local
./gpt-orchestrator-cli route --task '处理不能外发的材料' --sensitive
```

- Chat 路由：直接在 Chat 完成纯推理/写作；不必额外启动执行流程。
- Work 路由：带着任务书手动进入 Work，调用文档/表格/网页工具。CLI 不声称能自动切换产品模式或调用 Work。
- local/sensitive 路由：只推荐本地或人工处理；阻止浏览器与 Codex 派发。运行本地工具前自行确认数据范围与网络行为。
- 自动分类是中英文关键词启发式，不是语义模型。用 `--kind` 覆盖误判。
- 默认顺序执行；CLI 不启动子代理、不建公网隧道、不部署、不发送消息。
- 外部返回的计划属于提案，仍需审阅。沙箱不是对恶意代码的完整隔离；不向不可信仓库提供机密。

## 测试与项目结构

```sh
sh scripts/check.sh
ORCHESTRATOR_BROWSER_TEST=1 .venv/bin/python -m unittest tests.test_browser -v
```

第二条用于让真实 Chrome 打开本地模拟 DOM，检查回答完成、弹窗与超时；不会访问 ChatGPT。旧开发环境曾阻止 Chrome 启动；恢复后的公开版本尚未重跑该项实测，可在普通本地终端运行。标准测试使用假的 Codex 执行器，验证完整状态转换；不会消耗模型额度。真实登录后的 ChatGPT 与真实 Codex 模型调用未自动运行，详见 [验证记录](docs/VALIDATION.md)。

```text
gpt_orchestrator/          路由、协议、安全浏览器、状态与 CLI
gpt-orchestrator/SKILL.md  自定义技能
vendor/superpowers/       固定提交的 6 个上游 Skill 与必要资源（MIT）
integrations/chatgpt-use/ 原始协议、MIT 许可、移植边界与校验值
scripts/                  安装、浏览器依赖、检查
examples/                 配置使用示例、任务、协议回复、演示工作区
upstream.lock.json        上游仓库与提交固定值
```

卸载项目内技能链接即可停止发现；其他项目的链接需要在相应 `.agents/skills` 中移除。不要删除其他技能。浏览器注销可在专用窗口中手动进行；如需彻底清理，先关闭该浏览器，再删除本项目 `.state/`。此操作会清除该专用配置的登录状态，不涉及日常浏览器。
