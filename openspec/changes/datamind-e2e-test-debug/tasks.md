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
