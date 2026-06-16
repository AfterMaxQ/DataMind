# Comet Design Handoff

- Change: datamind-e2e-test-debug
- Phase: design
- Mode: compact
- Context hash: f0ebc096554303ad8627ecea2cf369c9448a7b49c30e7632cb7793dec9bbc39e

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/datamind-e2e-test-debug/proposal.md

- Source: openspec/changes/datamind-e2e-test-debug/proposal.md
- Lines: 1-29
- SHA256: 8b9c58d29e44476bb5f2533c5b112a39f67bbb7711b63b3a7f155ba0ed881a4e

```md
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
```

## openspec/changes/datamind-e2e-test-debug/design.md

- Source: openspec/changes/datamind-e2e-test-debug/design.md
- Lines: 1-110
- SHA256: ab319c2857fb3a55cfe95b7bee0df9fb25442a77d61a7c6d39b30f6645b83239

[TRUNCATED]

```md
## Context

DataMind Studio v3 是一个完整的 Web 应用：Vue 3 前端 + FastAPI 后端 + LangGraph 状态图引擎 + DeepSeek V4 Flash LLM。当前 310 个单元/集成测试全部通过，但缺乏浏览器端到端自动化测试和运行时调试基础设施。

v3 采用 LangGraph `SqliteSaver` 做 checkpoint，7 个技能通过 `SkillGraphBuilder` 编译为 `StateGraph`，工具通过 `ToolRegistry` 注册执行。系统已有 `mock_llm` 机制用于测试隔离。

本设计不改变 v3 核心架构，只在现有基础上增加可测试性和可观测性。

## Goals / Non-Goals

**Goals:**
- 建立 Playwright 自动化 E2E 测试套件，覆盖 WebSocket、SSE、Gate 审批、文件上传、技能 Pipeline、错误场景
- 提供运行时调试端点：session 状态查看、结构化日志查询、活跃 session 列表
- 增强日志系统：JSON 结构化输出、session 关联、工具调用追踪
- 编写测试运行手册和故障排查决策树

**Non-Goals:**
- 不重写现有 310 个测试
- 不给 DataMind 引擎增加业务功能
- 不引入外部日志服务（ELK、Loki 等）
- 不实现生产级 APM 或告警

## Decisions

### D1: Playwright 直接连 FastAPI，真实 DeepSeek API

Playwright 测试启动 FastAPI 服务器（`serve:app`），浏览器通过 `http://127.0.0.1:9000` 访问。**使用真实 DeepSeek V4 Flash API**（`deepseek-v4-flash`，API Base `https://api.deepseek.com`），确保端到端验证覆盖真实的 LLM 响应质量。

测试配置通过环境变量注入：
- `DATAMIND_PROVIDER=deepseek`
- `DATAMIND_MODEL=deepseek-v4-flash`
- `DATAMIND_API_KEY=<REDACTED>`
- `DATAMIND_API_BASE=https://api.deepseek.com`

轻量级渲染测试（布局、主题）使用 `page.route()` 拦截 API 调用避免消耗配额；完整流程测试（技能 Pipeline、Gate 审批）走真实 API。不可用 `deepseek-chat` 和 `deepseek-reasoner`（将于 2026/07/24 弃用）。

**替代方案**: Playwright 连 Vite dev server 再代理到 FastAPI。拒绝原因：多一层代理增加不确定性，且 Vite 代理配置需要额外维护。

### D2: JSON Lines 结构化日志

```python
# 日志格式
{
  "ts": "2026-06-16T12:00:00.000Z",
  "level": "INFO",
  "module": "langgraph_agent",
  "session_id": "abc123",
  "event": "phase_transition",
  "data": {"from": "phase-2", "to": "phase-3", "skill": "data-cleaning"},
  "elapsed_ms": 1234
}
```

- 每行一个 JSON 对象（JSON Lines）
- 同时输出到 stdout（开发）和 `.datamind/logs/` 目录（持久化）
- 日志级别通过 `DATAMIND_LOG_LEVEL` 环境变量控制，默认 `INFO`
- 不引入第三方日志库，使用 Python 标准 `logging` + 自定义 `JsonFormatter`

### D3: 调试端点设计

```
GET  /debug/state/{session_id}       → 完整 agent 状态快照
GET  /debug/sessions                 → 活跃 session 列表 + 状态摘要
GET  /debug/logs?session_id=&level   → 查询结构化日志（最近 N 条）
```

- `/debug/state` 返回：phase、messages、tool_calls、checkpoint_id、skill_name
- `/debug/sessions` 返回：session_id、skill_name、current_phase、started_at、last_active
- `/debug/logs` 读取 `.datamind/logs/` 目录下的 JSON Lines 文件，支持 session_id 和 level 过滤

### D4: 工具调用追踪

在 `ToolRegistry.execute()` 方法中注入追踪逻辑：

```python
def execute(self, name: str, args: dict) -> dict:
    start = time.time()
    try:
        result = self._tools[name](**args)
        log_tool_call(name, args, result, time.time() - start, status="success")
```

Full source: openspec/changes/datamind-e2e-test-debug/design.md

## openspec/changes/datamind-e2e-test-debug/tasks.md

- Source: openspec/changes/datamind-e2e-test-debug/tasks.md
- Lines: 1-49
- SHA256: 2d944e3c6bad2d1c18d8ced13186d1f7ff8ca50d6f59dd5c9759dd033fd096f6

```md
## 1. 基础设施准备

- [ ] 1.1 安装 Playwright 浏览器（chromium），配置 `playwright.config.ts` 指向 `http://127.0.0.1:9000`
- [ ] 1.2 创建 E2E 测试 fixture 数据文件（`sample.csv`、`sample.xlsx`、`sample.parquet`）
- [ ] 1.3 配置 Playwright `webServer` 启动 FastAPI（`python -m uvicorn serve:app --host 127.0.0.1 --port 9000`），注入 DeepSeek 环境变量

## 2. 结构化日志系统

- [ ] 2.1 实现 `JsonFormatter(logging.Formatter)` 子类，输出 JSON Lines 格式日志（ts、level、module、event、session_id、data 字段）
- [ ] 2.2 修改 `datamind/__init__.py` 或 `config.py`，在应用启动时配置 root logger 使用 `JsonFormatter`
- [ ] 2.3 添加日志文件轮转（`RotatingFileHandler`，10MB/文件，保留 7 天），写入 `.datamind/logs/`
- [ ] 2.4 在 `langgraph_agent.py` 中注入 session_id 到日志上下文（`LoggerAdapter` 或 `extra` 参数）

## 3. 工具调用追踪

- [ ] 3.1 修改 `ToolRegistry.execute()`，在每次调用前后记录 `tool_call` 事件日志（工具名、参数、耗时、状态）
- [ ] 3.2 编写工具追踪单元测试（成功/失败/超时三种场景）

## 4. Debug 端点

- [ ] 4.1 实现 `GET /debug/state/{session_id}` 端点，返回 session 完整运行时状态
- [ ] 4.2 实现 `GET /debug/sessions` 端点，返回活跃 session 摘要列表
- [ ] 4.3 实现 `GET /debug/logs` 端点，支持 `?session_id=&level=&limit=` 查询过滤
- [ ] 4.4 实现 Debug Guard：通过 `DATAMIND_DEBUG_DISABLE` 环境变量控制 `/debug/*` 可用性
- [ ] 4.5 编写 Debug 端点单元测试（正常返回、404、禁用后返回 404）

## 5. Playwright E2E — 核心交互

- [ ] 5.1 编写 `websocket.spec.ts`：WebSocket 连接建立、消息接收、断线重连、UI 状态同步
- [ ] 5.2 编写 `streaming.spec.ts`：SSE 流式对话 token-by-token 渲染、`/skill` 命令高亮、流完成后状态重置
- [ ] 5.3 扩展 `app.spec.ts`：验证三栏联动（选数据集 → 聊天引用 → 上下文更新）

## 6. Playwright E2E — 业务流程

- [ ] 6.1 编写 `gate-approval.spec.ts`：启动 data-cleaning → GATE 出现 → Approve 继续 → Reject 路由 → 决策记录更新
- [ ] 6.2 编写 `file-upload.spec.ts`：点击上传 CSV、拖拽上传 Excel、上传后数据集展示（名称/行列数）、无效文件错误提示
- [ ] 6.3 编写 `skill-pipeline.spec.ts`：上传 CSV → data-exploration → data-cleaning → feature-engineering → model-training 全链路（使用真实 DeepSeek API）
- [ ] 6.4 编写 `error-scenarios.spec.ts`：空消息拒绝、无效文件格式错误、LLM 异常恢复、工具超时处理

## 7. 流程文档

- [ ] 7.1 编写测试运行手册（`docs/testing-runbook.md`）：环境准备、运行命令、结果解读、CI 集成指南
- [ ] 7.2 编写故障排查决策树（`docs/debugging-runbook.md`）：按症状分类 → 定位方法 → 修复验证步骤

## 8. 最终验证

- [ ] 8.1 全量 Python 测试通过（310 tests → pass）
- [ ] 8.2 Playwright E2E 全部通过（使用真实 DeepSeek API）
- [ ] 8.3 Debug 端点功能验证（curl 测试全部端点）
```

## openspec/changes/datamind-e2e-test-debug/specs/debug-infrastructure/spec.md

- Source: openspec/changes/datamind-e2e-test-debug/specs/debug-infrastructure/spec.md
- Lines: 1-63
- SHA256: f7017f05a9ab5337c885b8532466e24a27aa738228ea3ebdaabe08f24a7df4ff

```md
﻿## ADDED Requirements

### Requirement: JSON Structured Logging
系统 SHALL 提供 JSON Lines 格式的结构化日志输出，每条日志包含时间戳、级别、模块、session_id、事件类型和事件数据。

#### Scenario: Log entry is valid JSON
- **WHEN** 系统任意模块产生一条日志
- **THEN** 日志在 stdout 输出一行有效 JSON，包含 `ts`、`level`、`module`、`event` 字段

#### Scenario: Log includes session correlation
- **WHEN** 日志事件发生在某个 skill session 上下文中
- **THEN** 日志 JSON 中包含 `session_id` 字段，可用于关联同一 session 的所有日志

#### Scenario: Log file rotation
- **WHEN** 日志文件超过 10MB 或超过 7 天
- **THEN** 系统自动轮转日志文件，旧日志被归档或删除

### Requirement: Debug State Endpoint
系统 SHALL 提供 `GET /debug/state/{session_id}` 端点，返回指定 session 的完整运行时状态。

#### Scenario: Get active session state
- **WHEN** GET 请求 `/debug/state/{session_id}` 且 session 处于活跃状态
- **THEN** 返回 JSON 包含 `session_id`、`skill_name`、`current_phase`、`phase_results`、`messages`、`tool_calls`、`checkpoint_id`

#### Scenario: Session not found returns 404
- **WHEN** GET 请求 `/debug/state/{session_id}` 且 session 不存在
- **THEN** 返回 HTTP 404，body 包含 `{"error": "session not found"}`

### Requirement: Debug Sessions Endpoint
系统 SHALL 提供 `GET /debug/sessions` 端点，返回当前所有活跃 session 的摘要列表。

#### Scenario: List all active sessions
- **WHEN** GET 请求 `/debug/sessions`
- **THEN** 返回 JSON 数组，每项包含 `session_id`、`skill_name`、`current_phase`、`started_at`、`last_active`

### Requirement: Debug Logs Endpoint
系统 SHALL 提供 `GET /debug/logs` 端点，支持按 session_id 和日志级别查询结构化日志。

#### Scenario: Query logs by session
- **WHEN** GET 请求 `/debug/logs?session_id=abc123&level=ERROR&limit=50`
- **THEN** 返回最近 50 条匹配 session 和级别的日志条目

### Requirement: Tool Call Tracing
系统 SHALL 在每次工具调用时自动记录追踪日志，包含工具名称、参数、返回值、执行耗时和执行状态。

#### Scenario: Successful tool call is traced
- **WHEN** `ToolRegistry.execute("read_csv", {"path": "data.csv"})` 成功返回
- **THEN** 日志中包含 `{"event": "tool_call", "data": {"tool": "read_csv", "status": "success", "elapsed_ms": <N>}}`

#### Scenario: Failed tool call is traced
- **WHEN** 工具执行抛出异常
- **THEN** 日志中包含 `{"event": "tool_call", "data": {"tool": "<name>", "status": "error", "error": "<message>"}}`

### Requirement: Debug Guard
系统 SHALL 通过配置开关控制调试端点的启用/禁用，默认仅在本地开发环境启用。

#### Scenario: Debug endpoints enabled on localhost
- **WHEN** 服务器绑定 `127.0.0.1` 且未设置 `DATAMIND_DEBUG_DISABLE=true`
- **THEN** `/debug/*` 端点可访问

#### Scenario: Debug endpoints disabled in production
- **WHEN** 设置环境变量 `DATAMIND_DEBUG_DISABLE=true`
- **THEN** `/debug/*` 端点返回 HTTP 404
```

## openspec/changes/datamind-e2e-test-debug/specs/e2e-test-suite/spec.md

- Source: openspec/changes/datamind-e2e-test-debug/specs/e2e-test-suite/spec.md
- Lines: 1-86
- SHA256: fc3d4a520703f173d3ba148f18178509f37863a3768c0c52abaf1aeef0235fdf

[TRUNCATED]

```md
﻿## ADDED Requirements

### Requirement: WebSocket Connection Lifecycle
系统 SHALL 通过 Playwright 自动化测试验证 WebSocket 连接的完整生命周期：连接建立、消息收发、断线重连、连接关闭。

#### Scenario: WebSocket connects successfully
- **WHEN** 浏览器加载主页面
- **THEN** WebSocket 连接在 5 秒内建立，`wsConnected` 状态变为 `true`

#### Scenario: WebSocket receives lineage updates
- **WHEN** 服务端广播 `lineage_update` 事件
- **THEN** 前端在 1 秒内更新血缘图节点和边

#### Scenario: WebSocket reconnects on disconnect
- **WHEN** WebSocket 连接异常断开
- **THEN** 客户端自动重连，指数退避延迟不超过 30 秒，重连后恢复 `wsConnected` 状态

### Requirement: SSE Streaming Chat
系统 SHALL 通过 Playwright 验证聊天 SSE 流式输出的完整流程，包含 token-by-token 渲染和技能命令高亮。

#### Scenario: Chat message streams token by token
- **WHEN** 用户在聊天框输入消息并发送
- **THEN** 回复内容以 token 为单位逐步渲染，流式完成后 `isStreaming` 变为 `false`

#### Scenario: Skill command is highlighted
- **WHEN** 用户输入 `/skill data-cleaning` 并发送
- **THEN** 聊天面板中 `/skill` 命令以高亮样式显示

### Requirement: Gate Approval Full Flow
系统 SHALL 通过 Playwright 验证 Gate 审批的完整流程：技能启动 → GATE 阶段 → Approve/Reject 按钮出现 → 用户做出审批 → 技能继续执行。

#### Scenario: Gate approval button appears at GATE phase
- **WHEN** 用户启动包含 GATE 阶段的技能（如 data-cleaning）
- **THEN** 技能执行到 GATE 阶段时，聊天面板中出现 Approve 和 Reject 按钮

#### Scenario: Approve continues execution
- **WHEN** 用户点击 Approve 按钮
- **THEN** 技能继续执行到下一阶段，GATE 按钮消失，决策记录出现在上下文面板

#### Scenario: Reject routes correctly
- **WHEN** 用户点击 Reject 按钮并填写反馈
- **THEN** 技能按 YAML frontmatter 路由规则跳转到指定阶段

### Requirement: File Upload and Dataset Display
系统 SHALL 通过 Playwright 验证文件上传的完整流程：拖拽/点击上传 → 文件解析 → 数据集出现在侧边栏。

#### Scenario: Upload CSV file via click
- **WHEN** 用户通过侧边栏上传按钮选择 CSV 文件
- **THEN** 上传成功后，数据集出现在侧边栏，显示文件名、行数、列数

#### Scenario: Upload Excel file via drag-and-drop
- **WHEN** 用户拖拽 Excel 文件到侧边栏
- **THEN** 文件被解析，数据集出现在侧边栏

### Requirement: Full Skill Pipeline
系统 SHALL 通过 Playwright 验证完整技能 Pipeline：上传数据 → 启动数据探索 → 数据清洗 → 特征工程 → 模型训练，全链路端到端执行。

#### Scenario: Data exploration to model training pipeline
- **WHEN** 用户上传 CSV 数据后依次执行 `/skill data-exploration`、`/skill data-cleaning`、`/skill feature-engineering`、`/skill model-training`
- **THEN** 每个技能依次完成执行，血缘图中显示完整的数据处理链路

### Requirement: Error Scenario Handling
系统 SHALL 通过 Playwright 验证常见错误场景的处理：无效文件上传、空消息、LLM 返回异常、工具执行超时。

#### Scenario: Invalid file upload shows error
- **WHEN** 用户尝试上传非支持格式的文件（如 .exe）
- **THEN** 界面显示清晰的错误提示，不崩溃

#### Scenario: Empty message rejected
- **WHEN** 用户发送空消息
- **THEN** 消息不被发送，输入框保持焦点

#### Scenario: Tool timeout shows error
- **WHEN** 工具执行超过 300 秒超时
- **THEN** 聊天面板显示超时错误信息，session 不 crash，用户可以继续操作

### Requirement: E2E Test Configuration
系统 SHALL 提供 E2E 测试配置和 fixture，支持使用真实 DeepSeek API 执行测试。

#### Scenario: Tests use real DeepSeek API
```

Full source: openspec/changes/datamind-e2e-test-debug/specs/e2e-test-suite/spec.md

