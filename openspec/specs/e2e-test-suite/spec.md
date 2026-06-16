# e2e-test-suite Specification

## Purpose
TBD - created by archiving change datamind-e2e-test-debug. Update Purpose after archive.
## Requirements
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
- **WHEN** E2E 测试运行时设置 `DATAMIND_PROVIDER=deepseek`、`DATAMIND_API_KEY=<key>`、`DATAMIND_MODEL=deepseek-v4-flash`
- **THEN** 测试中的 LLM 调用通过真实 DeepSeek API 完成，API 调用成功返回有效响应

#### Scenario: Test server starts and stops cleanly
- **WHEN** Playwright `webServer` 配置启动 FastAPI 服务器
- **THEN** 服务器在 `http://127.0.0.1:9000` 接受请求，测试结束后进程被清理

