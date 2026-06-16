# debug-infrastructure Specification

## Purpose
TBD - created by archiving change datamind-e2e-test-debug. Update Purpose after archive.
## Requirements
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

