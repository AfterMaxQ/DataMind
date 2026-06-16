---
comet_change: datamind-e2e-test-debug
role: technical-design
canonical_spec: openspec
---

# DataMind E2E Testing & Debug Infrastructure — Technical Design

## Context

DataMind Studio v3 已完整运行（Vue 3 + FastAPI + LangGraph + DeepSeek V4 Flash），310 个后端测试全部通过。但缺少浏览器端到端自动化测试和运行时故障排查基础设施。本设计在不变更 v3 核心架构的前提下，增加可测试性和可观测性。

v3 关键集成点：
- `DataMindAgent` (engine/agent.py) — 持有 `_state_machine` 实例变量，单 session 驱动
- `LangGraphAgent` (engine/langgraph_agent.py) — v3 引擎，SqliteSaver checkpoint
- `ToolRegistry` (engine/tools.py) — 7 个工具，`execute(name, args)` 调度
- FastAPI (api/app.py) — REST + WebSocket + SSE，通过 `app.state` 持有 agent 引用

## Goals / Non-Goals

**Goals:**
- Playwright E2E 测试套件，覆盖 WebSocket、SSE、Gate 审批、文件上传、技能 Pipeline、错误场景
- 运行时调试端点：`/debug/state`、`/debug/sessions`、`/debug/logs`
- JSON 结构化日志 + session 关联 + 工具调用追踪
- 测试运行手册 + 故障排查决策树

**Non-Goals:**
- 不重写现有 310 个测试
- 不给 DataMind 引擎增加业务功能
- 不引入外部日志服务（ELK、Loki）
- 不实现生产级 APM 或告警

## Decisions

### D1: Playwright 直连 FastAPI，真实 DeepSeek API

Playwright 启动 FastAPI（`python -m uvicorn serve:app --host 127.0.0.1 --port 9000`），注入 DeepSeek 环境变量：

```
DATAMIND_PROVIDER=deepseek
DATAMIND_MODEL=deepseek-v4-flash
DATAMIND_API_KEY=${DEEPSEEK_API_KEY}
DATAMIND_API_BASE=https://api.deepseek.com
```

两级分层：渲染类测试（布局/主题/侧栏）用 `page.route()` 拦截 API 调用，避免消耗配额；交互类测试（WebSocket/SSE/Gate/上传/Pipeline/错误）走真实 DeepSeek API。

**替代方案**: Vite dev server 代理 → 拒绝（多一层代理增加不确定性）。

### D2: JSON Lines 结构化日志

```python
# 日志格式
{
  "ts": "2026-06-16T12:00:00.000Z",
  "level": "INFO",
  "module": "langgraph_agent",
  "session_id": "abc123",
  "event": "phase_transition",
  "data": {"from": "phase-2", "to": "phase-3"},
  "elapsed_ms": 1234
}
```

- stdout: 人类可读文本；文件: JSON Lines（`.datamind/logs/app.jsonl`）
- 不引入第三方库，基于 Python 标准 `logging` + 自定义 `JsonFormatter`
- `RotatingFileHandler`: 10MB/文件，保留 7 天
- 日志级别通过 `DATAMIND_LOG_LEVEL` 环境变量控制，默认 `INFO`

### D3: Debug 端点设计

独立 router `datamind/api/debug.py`，通过 `DATAMIND_DEBUG_DISABLE` 环境变量控制挂载：

```
GET  /debug/state/{session_id}  → {session_id, skill_name, current_phase,
                                    messages, tool_calls, checkpoint_id}
GET  /debug/sessions            → [{session_id, skill_name, phase, started_at}]
GET  /debug/logs                → ?session_id=&level=&limit=100
```

Debug 端点通过 `app.state.session_registry` 访问活跃 session。`/debug/logs` 读取 `.datamind/logs/` 目录下 JSONL 文件。

### D4: Tool Call Tracing

在 `ToolRegistry.execute()` 方法中注入追踪：

```python
def execute(self, name: str, args: dict) -> dict:
    start = time.time()
    session_id = _current_session_id.get()  # from contextvars
    try:
        result = self._tools[name](**args)
        _log_tool_event(session_id, name, "success", time.time() - start)
        return result
    except Exception as e:
        _log_tool_event(session_id, name, "error", time.time() - start, str(e))
        raise
```

### D5: E2E 测试结构

```
web-ui/tests/e2e/
├── fixtures/
│   ├── sample.csv           # 100 行测试数据
│   ├── sample.xlsx          # Excel 格式
│   └── sample.parquet       # Parquet 格式
├── app.spec.ts              # 已有：布局/主题/聊天/侧栏（mock API）
├── websocket.spec.ts        # WebSocket 连接/断线/重连/事件（真实 API）
├── streaming.spec.ts        # SSE token-by-token / 命令高亮（真实 API）
├── gate-approval.spec.ts    # Approve/Reject 完整流程（真实 API）
├── file-upload.spec.ts      # 上传/拖拽/错误提示（真实 API）
├── skill-pipeline.spec.ts   # CSV→探索→清洗→特征→建模（真实 API）
└── error-scenarios.spec.ts  # 空消息/无效文件/超时恢复（真实 API）
```

### D6: session_id 传播 — contextvars

```
                 ┌──────────────────────┐
                 │  FastAPI Middleware   │
                 │  _session_id.set(id)  │
                 └──────────┬───────────┘
                            │
          ┌─────────────────┼──────────────────┐
          ▼                 ▼                  ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
   │ app.py      │  │ agent.py    │  │ tools.py         │
   │ log.info()  │  │ log.info()  │  │ _log_tool_event()│
   │ auto-reads  │  │ auto-reads  │  │ auto-reads       │
   │ session_id  │  │ session_id  │  │ session_id       │
   └─────────────┘  └─────────────┘  └─────────────────┘
```

使用 Python `contextvars.ContextVar`，FastAPI 中间件在请求入口设置。`JsonFormatter` 从当前 context 读取 session_id 写入日志。不修改任何函数签名。

### D7: Session 注册表

```python
# api/app.py — app startup
app.state.session_registry: dict[str, object] = {}

# After agent.run() or agent.approve_gate()
app.state.session_registry[session_id] = {
    "agent": agent,
    "state_machine": sm,
    "started_at": datetime.now(),
}
```

Debug 端点查询此注册表返回 session 状态。

### D8: Debug Router 隔离

```python
# datamind/api/debug.py
from fastapi import APIRouter
debug_router = APIRouter(prefix="/debug")

@debug_router.get("/state/{session_id}")
async def get_state(session_id: str): ...

@debug_router.get("/sessions")
async def list_sessions(): ...

@debug_router.get("/logs")
async def query_logs(session_id: str = None, level: str = None, limit: int = 100): ...

# api/app.py — conditional mount
if not os.environ.get("DATAMIND_DEBUG_DISABLE"):
    from datamind.api.debug import debug_router
    app.include_router(debug_router)
```

## Risks / Trade-offs

- **[Risk] DeepSeek API 调用耗时** — 完整 Pipeline 测试可能 30-60s。Playwright `timeout: 120000` per test，CI 并行执行
- **[Risk] Playwright Chromium 下载** — 首次 ~150MB。CI 环境预缓存 `PLAYWRIGHT_BROWSERS_PATH`
- **[Risk] contextvars 隐式传播调试困难** — `/debug/logs` 端点提供日志查询补偿可观测性
- **[Trade-off] Session 注册表内存存储** — 重启丢失，但作为调试工具可接受
- **[Trade-off] JSON Lines vs 纯文本** — stdout 输出人类可读文本，文件存 JSON 供机器解析

## Migration Plan

1. 实现结构化日志 + contextvars → 不改变现有行为，纯增量
2. 实现 ToolRegistry 追踪 → 包装现有 execute() 方法
3. 实现 Debug 端点 + Session 注册表 → 独立 router，条件挂载
4. 编写 Playwright E2E 测试 → 新增测试文件，不影响现有代码
5. 编写流程文档 → 纯文档

回滚：删除新增文件和 router 注册即可，无需数据迁移。
