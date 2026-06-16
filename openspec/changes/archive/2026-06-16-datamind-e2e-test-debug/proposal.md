## Why

DataMind Studio v3 已经可以端到端运行（Web UI → API → LangGraph → DeepSeek V4 Flash → 工具执行），但缺乏系统化的自动化端到端测试和运行时故障排查能力。当前 310 个单元/集成测试覆盖了后端模块，但浏览器端用户路径（WebSocket、SSE 流、Gate 审批、文件上传、完整技能 Pipeline）没有自动化验证。同时，服务运行时出现故障（LLM 异常、工具超时、Graph 中断）时，缺乏结构化的调试入口和日志追踪。

## What Changes

- **新增** Playwright 自动化 E2E 测试套件，覆盖全部关键用户路径：WebSocket 连接生命周期、SSE 流式对话、Gate 审批完整流程、文件上传→解析→展示、完整技能 Pipeline、错误场景处理
- **新增** 运行时调试端点：`/debug/state`（session 状态查看）、`/debug/logs`（结构化日志查询）、`/debug/sessions`（活跃 session 列表）
- **新增** 结构化日志系统：JSON 格式日志、分类标签、时间线追踪、工具调用链记录
- **新增** 测试运行手册和故障排查决策树文档

## Capabilities

### New Capabilities

- `e2e-test-suite`: 基于 Playwright 的浏览器端到端自动化测试，覆盖 WebSocket、SSE、Gate 审批、文件上传、技能 Pipeline、错误场景
- `debug-infrastructure`: 运行时调试端点（state/logs/sessions）、JSON 结构化日志、工具调用追踪

### Modified Capabilities

（无现有 spec 需求变更）

## Impact

- `web-ui/tests/e2e/` — 新增多个 Playwright 测试文件
- `datamind/api/app.py` — 新增 `/debug/*` 路由
- `datamind/engine/` — 注入结构化 logger，工具调用追踪
- `datamind/config.py` — 新增日志配置项
- `pyproject.toml` / `package.json` — 可能新增测试/日志依赖
