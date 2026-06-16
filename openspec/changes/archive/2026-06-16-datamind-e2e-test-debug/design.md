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
- `DATAMIND_API_KEY=${DEEPSEEK_API_KEY}`
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
        return result
    except Exception as e:
        log_tool_call(name, args, str(e), time.time() - start, status="error")
        raise
```

### D5: E2E 测试结构

```
web-ui/tests/e2e/
├── fixtures/               # 测试数据文件
│   ├── sample.csv
│   ├── sample.xlsx
│   └── sample.parquet
├── app.spec.ts             # 已有：布局、主题、聊天基础
├── websocket.spec.ts       # 新增：WS 连接/断线/重连/事件
├── streaming.spec.ts       # 新增：SSE 流式对话
├── gate-approval.spec.ts   # 新增：Gate 审批完整流程
├── file-upload.spec.ts     # 新增：文件上传→解析→展示
├── skill-pipeline.spec.ts  # 新增：完整技能 Pipeline
└── error-scenarios.spec.ts # 新增：LLM 异常、工具超时等错误处理
```

## Risks / Trade-offs

- **[Risk] Playwright 测试不稳定** → 使用 `retries: 2`（CI 模式），mock LLM 保证确定性输出，固定测试数据
- **[Risk] 调试端点暴露内部状态** → 仅绑定 `127.0.0.1`，不对外暴露；生产环境通过 flag 禁用
- **[Risk] 日志文件膨胀** → 自动轮转，保留最近 7 天，单文件最大 10MB
- **[Trade-off] JSON Lines vs 纯文本日志** → JSON 可机器解析但人类阅读不如纯文本；同时输出两种格式（stdout 纯文本，文件 JSON）
- **[Trade-off] Mock LLM 无法测真实 AI 行为** → E2E 测试目标是验证系统集成正确性，AI 质量测试另行安排
