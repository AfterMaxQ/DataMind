# Brainstorm Summary

- Change: datamind-e2e-test-debug
- Date: 2026-06-16

## Confirmed Technical Approach

1. **session_id 传播**: Python `contextvars` 在异步上下文中隐式传播，FastAPI 中间件在请求入口设置，`JsonFormatter` 从 context 读取
2. **E2E API 分层**: 渲染类测试（布局/主题/侧栏）使用 Playwright `page.route()` mock API；交互类测试（WebSocket/SSE/Gate/上传/Pipeline）走真实 DeepSeek API
3. **Session 注册表**: `app.state.session_registry = dict[session_id, agent_ref]`，API 层维护，Debug 端点查询
4. **Debug 端点**: 独立 `datamind/api/debug.py` router，通过 `DATAMIND_DEBUG_DISABLE` 环境变量控制挂载
5. **JSON 结构化日志**: Python 标准 `logging` + 自定义 `JsonFormatter`，stdout 文本 + 文件 JSON Lines，文件轮转 10MB/7天
6. **工具追踪**: `ToolRegistry.execute()` 注入计时 + 事件日志
7. **Playwright 配置**: 直连 FastAPI port 9000，环境变量注入 DeepSeek 凭证

## Key Trade-offs and Risks

- DeepSeek API 调用耗时（Pipeline 测试 30-60s）→ timeout 120s + 并行执行
- Playwright 首次下载 Chromium ~150MB → CI 预缓存
- contextvars 隐式传播调试不如显式传参直观 → 侵入性最低，通过 `/debug/logs` 端点补偿可观测性
- Debug 端点仅在 127.0.0.1 启用，生产通过 `DATAMIND_DEBUG_DISABLE=true` 禁用

## Testing Strategy

- 单元测试: JsonFormatter, Debug 端点 (mock agent), 工具追踪
- Playwright E2E: 两级分层——渲染类 mock + 交互类真实 API
- 集成: 全部 310 现有测试 + Playwright 测试通过
- DeepSeek 凭证: `deepseek-v4-flash` @ `https://api.deepseek.com`

## Spec Patches

None — delta specs from open phase are complete
