# DataMind Studio Web UI — Vue 3 SPA 前端组件生成任务

---

## 一、项目概述

DataMind Studio 是一个数据分析 Agent 平台。用户上传数据集（CSV、Parquet、Excel），通过聊天界面调用技能（如 `/skill data-cleaning`），由 LangGraph 驱动的 Agent 引擎执行多阶段工作流。部分阶段需要人工审批（GATE 阶段），界面上会嵌入 Approve/Reject 按钮。

你需要为这个平台生成一套完整的、生产级质量的 Vue 3 单文件组件（SFC）。请严格按照以下规范生成每一个文件，确保代码可直接运行，无需任何修改。

---

## 二、技术栈与版本要求

| 技术 | 版本要求 |
|------|----------|
| Vue | 3.4+，使用 `<script setup lang="ts">` |
| TypeScript | strict 模式，所有类型必须显式声明，禁止 `any` |
| Vite | 5+，作为构建工具 |
| Pinia | 最新稳定版，状态管理 |
| Vue Router | 4.x，基本路由（单页应用即可） |
| D3.js | v7，用于血缘图（Lineage Graph） |
| highlight.js | 最新版，代码块语法高亮 |
| CSS | **纯 CSS（无 UI 库）**，使用 CSS 自定义属性（custom properties）实现主题切换 |

**特别禁止：** 不得使用 Element Plus、Ant Design、Vuetify 等任何 UI 组件库。所有 UI 必须手写 CSS。

---

## 三、后端 API 规范

后端运行在 `localhost:8000`，Vite 开发服务器运行在 `localhost:5173`，通过 Vite proxy 转发 `/api`、`/chat`、`/ws`、`/upload`、`/skill` 到后端。

### 3.1 REST 端点

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| `POST` | `/chat/stream` | SSE 流式聊天 | JSON: `{ session_id, message, skill? }` |
| `POST` | `/upload` | 文件上传 | multipart/form-data，字段名 `file` |
| `POST` | `/skill/gate` | Gate 审批 | JSON: `{ session_id, gate_name, decision: { approved: boolean, comment?: string } }` |
| `GET` | `/api/datasets` | 数据集列表 | - |
| `GET` | `/api/skills` | 技能列表 | - |

### 3.2 WebSocket 端点

| 路径 | 说明 |
|------|------|
| `GET /ws` | 实时事件推送（lineage_update, decision_update, phase_transition, token_stream） |

### 3.3 SSE 事件格式（`/chat/stream`）

每条消息以 `data: ` 开头，内容是 JSON 字符串。**注意：type 为 `done` 和 `error` 后可能还有额外的换行以结束 SSE 流，前端需正确处理。**

```
data: {"type": "token", "content": "Hello"}
data: {"type": "tool_call", "tool": "read_csv", "args": {"path": "data.csv"}}
data: {"type": "tool_result", "tool": "read_csv", "result": {"columns": ["A","B"], "rows": 100}}
data: {"type": "phase", "phase": "analyze", "status": "started"}
data: {"type": "gate", "phase": "review", "gate_name": "gate-approve"}
data: {"type": "done"}
data: {"type": "error", "message": "file not found: data.csv"}
```

**SSE 类型说明：**

- `token`：AI 输出的单个 token，逐字追加到当前助手消息中
- `tool_call`：Agent 调用了一个工具，展示工具卡片
- `tool_result`：工具执行结果，更新对应工具卡片
- `phase`：工作流阶段切换（status: started / completed）
- `gate`：进入人工审批阶段，需要展示 Approve/Reject 按钮
- `done`：当前对话轮次结束
- `error`：错误信息，展示为系统消息

### 3.4 WebSocket 事件格式

```json
{"type": "phase_transition", "from": "analyze", "to": "review", "session": "abc123"}
{"type": "lineage_update", "nodes": [{"id":"1","label":"data.csv","type":"dataset"},{"id":"2","label":"clean","type":"operation"},{"id":"3","label":"cleaned.csv","type":"result"}], "edges": [{"source":"1","target":"2"},{"source":"2","target":"3"}]}
{"type": "decision_update", "approved": true, "phase": "review", "next_phase": "execute"}
```

**WebSocket 连接要求：**
- 页面加载时自动连接
- 断线后自动重连，使用指数退避（1s → 2s → 4s → 8s → 最大 30s）
- 根据事件 type 分发到对应的 Pinia store 处理

---

## 四、TypeScript 类型定义

请在 `src/types/` 目录下生成以下类型文件：

### 4.1 `src/types/index.ts` — 核心数据类型

```typescript
// 消息角色
export type MessageRole = 'user' | 'assistant' | 'system';

// 聊天消息
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  // 工具调用（可能存在多个）
  toolCalls?: ToolCall[];
  // Gate 审批状态（仅 assistant 消息可能出现）
  gateStatus?: GateStatus;
  // SSE 流式传输中标识
  isStreaming?: boolean;
}

// 工具调用
export interface ToolCall {
  id: string;
  toolName: string;
  args: Record<string, unknown>;
  result?: ToolResult;
  status: 'pending' | 'running' | 'completed' | 'error';
}

// 工具结果
export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
}

// Gate 审批状态
export interface GateStatus {
  gateName: string;
  phase: string;
  resolved: boolean;
  approved?: boolean;
  comment?: string;
}

// SSE 流事件
export type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; tool: string; result: Record<string, unknown> }
  | { type: 'phase'; phase: string; status: 'started' | 'completed' }
  | { type: 'gate'; phase: string; gate_name: string }
  | { type: 'done' }
  | { type: 'error'; message: string };

// 数据集
export interface Dataset {
  id: string;
  name: string;
  type: 'raw' | 'processed';
  format: 'csv' | 'parquet' | 'excel';
  size: number;       // bytes
  rows?: number;
  columns?: string[];
  createdAt: string;  // ISO 8601
}

// 技能
export interface Skill {
  name: string;
  displayName: string;
  description: string;
  category: string;
}

// 工作流阶段
export interface PhaseInfo {
  name: string;
  status: 'idle' | 'running' | 'completed' | 'gate';
  startedAt?: number;
}

// WebSocket 事件类型
export type WSEventType = 'phase_transition' | 'lineage_update' | 'decision_update' | 'token_stream';

export interface WSEvent {
  type: WSEventType;
  [key: string]: unknown;
}

// 血缘图节点与边
export interface LineageNode {
  id: string;
  label: string;
  type: 'dataset' | 'operation' | 'result';
}

export interface LineageEdge {
  source: string;
  target: string;
}
```

---

## 五、CSS 主题系统 (CSS Custom Properties)

### 5.1 设计令牌定义

在 `src/assets/theme.css` 中定义全局 CSS 自定义属性。暗色模式为默认；亮色模式通过 `[data-theme="light"]` 切换。

完整令牌清单如下——**每一行都必须出现在最终代码中**：

```css
/* ===== 基础色板 ===== */
--color-bg-primary          /* 主背景 */
--color-bg-secondary        /* 次级背景（卡片、面板） */
--color-bg-tertiary         /* 三级背景（输入框、hover） */
--color-bg-elevated         /* 浮层背景（dropdown、tooltip） */
--color-surface             /* 表面色 */
--color-border              /* 边框色 */
--color-border-light        /* 浅边框 */

/* ===== 文字色 ===== */
--color-text-primary        /* 主文字 */
--color-text-secondary      /* 次级文字 */
--color-text-tertiary       /* 辅助文字 */
--color-text-inverse        /* 反色文字 */

/* ===== 品牌色 / 语义色 ===== */
--color-accent              /* 主强调色（按钮、链接） */
--color-accent-hover        /* 强调色 hover */
--color-success             /* 成功 */
--color-warning             /* 警告 */
--color-error               /* 错误 */
--color-info                /* 信息 */

/* ===== 消息气泡色 ===== */
--color-bubble-user         /* 用户消息气泡背景 */
--color-bubble-assistant    /* 助手消息气泡背景 */
--color-bubble-system       /* 系统消息气泡背景 */

/* ===== 代码块 ===== */
--color-code-bg             /* 代码块背景 */
--color-code-text           /* 代码块文字 */

/* ===== 间距 ===== */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 12px;
--spacing-lg: 16px;
--spacing-xl: 24px;
--spacing-2xl: 32px;

/* ===== 圆角 ===== */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-full: 9999px;

/* ===== 阴影 ===== */
--shadow-sm
--shadow-md
--shadow-lg

/* ===== 字体 ===== */
--font-sans
--font-mono
--font-size-xs: 12px;
--font-size-sm: 13px;
--font-size-base: 14px;
--font-size-lg: 16px;
--font-size-xl: 20px;
--font-size-2xl: 24px;

/* ===== 过渡 ===== */
--transition-fast: 150ms ease;
--transition-normal: 250ms ease;

/* ===== 布局 ===== */
--sidebar-width: 280px;
--context-panel-width: 320px;
--header-height: 48px;
```

### 5.2 暗色模式（`:root` 默认）

```
--color-bg-primary: #0f1117
--color-bg-secondary: #161822
--color-bg-tertiary: #1e2030
--color-bg-elevated: #252838
--color-surface: #1a1c2a
--color-border: #2a2d3e
--color-border-light: #222436
--color-text-primary: #e1e3ec
--color-text-secondary: #9ca0b0
--color-text-tertiary: #5f6376
--color-text-inverse: #0f1117
--color-accent: #6c8cff
--color-accent-hover: #8aa4ff
--color-code-bg: #0d0f18
--color-code-text: #c9d1d9
--color-bubble-user: #2a3a6e
--color-bubble-assistant: #1e2030
--color-bubble-system: #2a2818
```

### 5.3 亮色模式（`[data-theme="light"]`）

```
--color-bg-primary: #f5f6fa
--color-bg-secondary: #ffffff
--color-bg-tertiary: #edf0f5
--color-bg-elevated: #ffffff
--color-surface: #ffffff
--color-border: #dde1e8
--color-border-light: #edf0f5
--color-text-primary: #1a1d2e
--color-text-secondary: #5f6376
--color-text-tertiary: #9ca0b0
--color-text-inverse: #ffffff
--color-accent: #4b6bf5
--color-accent-hover: #3b54cc
--color-code-bg: #f0f2f7
--color-code-text: #24273a
--color-bubble-user: #dce6ff
--color-bubble-assistant: #f5f6fa
--color-bubble-system: #fff8dc
```

### 5.4 主题切换逻辑

- 使用 Pinia `theme` store 管理状态
- `data-theme` 属性设在 `<html>` 元素上
- 用户切换时同时写入 `localStorage.setItem('datamind-theme', theme)`
- 初始化时从 `localStorage` 读取，无记录则默认暗色
- 参考系统偏好：若无 localStorage 记录，使用 `window.matchMedia('(prefers-color-scheme: light)')` 决定初始值

---

## 六、Pinia Store 定义

### 6.1 `src/stores/session.ts` — 会话状态

```
State:
  sessionId: string | null
  currentSkill: Skill | null        // 当前激活的技能
  currentPhase: PhaseInfo | null    // 当前工作流阶段
  phaseHistory: PhaseInfo[]         // 阶段历史
  gatePending: GateStatus | null    // 当前等待审批的 gate

Actions:
  setSession(id: string): void
  setSkill(skill: Skill | null): void
  updatePhase(phase: PhaseInfo): void
  setGatePending(gate: GateStatus | null): void
  approveGate(approved: boolean, comment?: string): Promise<void>   // 调用 POST /skill/gate
  reset(): void

Getters:
  isInGate: boolean                  // gatePending !== null && !gatePending.resolved
  currentPhaseName: string
```

### 6.2 `src/stores/chat.ts` — 聊天状态

```
State:
  messages: ChatMessage[]
  isLoading: boolean                  // 是否正在等待 SSE 响应
  streamingMessageId: string | null   // 当前正在流式接收的消息 ID
  error: string | null

Actions:
  sendMessage(content: string, skill?: string): Promise<void>
    // 1. 创建 user 消息，追加到 messages
    // 2. 创建空的 assistant 消息（isStreaming: true, id 即 streamingMessageId）
    // 3. 发起 fetch POST /chat/stream，读取 SSE 流
    // 4. 根据 event.type 分发处理（见下方 SSE 处理逻辑）
    // 5. 流结束时设置 isLoading=false, streamingMessageId=null
  clearMessages(): void
  addSystemMessage(content: string): void

SSE 处理逻辑（sendMessage 内部）：
  - 收到 token → 追加 content 到 streamingMessageId 对应的消息
  - 收到 tool_call → 创建 ToolCall 对象，追加到消息的 toolCalls[]
  - 收到 tool_result → 更新对应 toolCall 的 result 和 status
  - 收到 phase → 调用 session store 的 updatePhase
  - 收到 gate → 调用 session store 的 setGatePending
  - 收到 done → 将 streamingMessage 的 isStreaming 置为 false
  - 收到 error → 创建系统消息展示错误

Getters:
  lastMessage: ChatMessage | null
  messageCount: number
```

### 6.3 `src/stores/datasets.ts` — 数据集状态

```
State:
  datasets: Dataset[]
  rawDatasets: Dataset[]              // computed: datasets.filter(d => d.type === 'raw')
  processedDatasets: Dataset[]        // computed: datasets.filter(d => d.type === 'processed')
  isUploading: boolean
  uploadProgress: number              // 0-100
  uploadError: string | null

Actions:
  fetchDatasets(): Promise<void>      // GET /api/datasets
  uploadFile(file: File): Promise<void>
    // 1. FormData 包装，字段名 "file"
    // 2. POST /upload
    // 3. 成功后重新 fetchDatasets
    // 4. 失败设置 uploadError
  removeDataset(id: string): Promise<void>
```

### 6.4 `src/stores/theme.ts` — 主题状态

```
State:
  mode: 'dark' | 'light'

Actions:
  init(): void
    // 从 localStorage 'datamind-theme' 读取
    // 无记录时用 matchMedia('(prefers-color-scheme: light)')
  toggle(): void
    // 切换 mode，更新 <html> data-theme，写入 localStorage
  setTheme(mode: 'dark' | 'light'): void

Getters:
  isDark: boolean
```

### 6.5 `src/stores/skills.ts` — 技能列表

```
State:
  skills: Skill[]
  isLoading: boolean

Actions:
  fetchSkills(): Promise<void>       // GET /api/skills

Getters:
  skillNames: string[]                // 用于 autocomplete
  skillsByCategory: Record<string, Skill[]>
```

### 6.6 `src/composables/useWebSocket.ts` — WebSocket 连接

这不是 Pinia store，而是一个 composable，在 `App.vue` 的 `onMounted` 中调用。

```
export function useWebSocket() {
  // 内部状态
  ws: WebSocket | null
  reconnectAttempt: number           // 当前重连次数
  maxReconnectDelay: 30000           // 30s
  baseDelay: 1000

  // 方法
  connect(): void
    // new WebSocket('ws://localhost:8000/ws')
    // 或通过 Vite proxy: const url = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`

  disconnect(): void

  handleMessage(event: MessageEvent): void
    // 解析 JSON，根据 event.type 分发：
    //   phase_transition → sessionStore.updatePhase
    //   lineage_update → 传给 ContextPanel / LineageGraph（通过 provide/inject 或 store）
    //   decision_update → 更新 gate 状态
    //   token_stream → 忽略（SSE 已处理）

  scheduleReconnect(): void
    // delay = min(baseDelay * 2^reconnectAttempt, maxReconnectDelay)
    // setTimeout → connect()
    // 连接成功后 reconnectAttempt 归零

  onOpen / onClose / onError 回调
}
```

---

## 七、组件树与完整规范

按以下顺序生成组件，**从叶子节点到根节点**。每个组件的规范包含：

- 文件路径
- Props（含类型）
- Emits（含类型）
- 内部状态
- 关键行为
- 模板结构
- CSS 要点

---

### 7.1 `src/components/chat/CodeBlock.vue`

**文件路径：** `src/components/chat/CodeBlock.vue`

**Props：**
```typescript
defineProps<{
  code: string;
  language?: string;   // 默认 'python'
}>()
```

**Emits：** 无

**功能：**
1. 使用 `highlight.js` 对代码进行语法高亮（在 `onMounted` 和 `watch` 中调用 `hljs.highlight(code, { language })`）
2. 代码块右上角有语言标签和"在 Scripts 中查看"按钮
3. 代码块左上角有"复制"按钮，点击复制全部代码到剪贴板，复制成功后短暂显示 "已复制"
4. 代码块可水平滚动（`overflow-x: auto`）
5. 字体使用 `--font-mono`，字号 `--font-size-sm`

**CSS：**
- 背景色 `--color-code-bg`，文字色 `--color-code-text`
- 圆角 `--radius-md`
- 边框 `1px solid var(--color-border)`
- 顶部工具栏：flex, space-between，半透明背景
- 代码块内边距：`--spacing-md`
- 按钮：透明背景，hover 时 `--color-bg-tertiary`，过渡 `--transition-fast`

---

### 7.2 `src/components/chat/ToolCallCard.vue`

**文件路径：** `src/components/chat/ToolCallCard.vue`

**Props：**
```typescript
defineProps<{
  toolCall: ToolCall;
}>()
```

**Emits：** 无

**功能：**
1. 卡片头部显示工具名称和状态图标（pending: 旋转 spinner, running: 脉冲, completed: 绿色勾, error: 红色叉）
2. 可折叠的参数/结果区域（默认折叠）
3. 展开后显示参数（格式化为 JSON，使用 `<pre>` 标签）和结果摘要
4. `status === 'running'` 时卡片有脉冲边框动画
5. 点击头部可切换展开/折叠

**CSS：**
- 背景 `--color-bg-tertiary`，边框 `--color-border`
- 圆角 `--radius-md`
- 头部：flex 布局，左侧工具图标 + 工具名，右侧状态图标
- 折叠区域有 `max-height` 过渡动画
- 脉冲动画：`@keyframes pulse-border`，边框从 `--color-accent` 渐变到透明

---

### 7.3 `src/components/chat/GateApproval.vue`

**文件路径：** `src/components/chat/GateApproval.vue`

**Props：**
```typescript
defineProps<{
  gateStatus: GateStatus;
}>()
```

**Emits：**
```typescript
defineEmits<{
  approve: [comment?: string];
  reject: [comment?: string];
}>()
```

**功能：**
1. 显示 Gate 名称和描述（例如"数据清洗结果审查 — 请确认清洗规则是否正确"）
2. 两个主按钮：绿色"Approve ✓"和红色"Reject ✗"
3. 可选评论输入框：一个可折叠的 `<textarea>`，placeholder 为"添加审批意见（可选）…"
4. 点击 Approve 后 emit `approve` 事件，携带 comment（如有）
5. 点击 Reject 后 emit `reject` 事件，携带 comment（如有）
6. 按钮点击后立刻 disabled，防止重复提交
7. **`gateStatus.resolved === true` 时不渲染任何内容**（已审批完成）

**CSS：**
- 卡片：背景 `--color-bg-tertiary`，左侧有 3px 宽的强调色边框（`--color-warning`）
- 标题："需要你的审批"，字体 `--font-size-lg`，颜色 `--color-text-primary`
- Approve 按钮：背景 `--color-success`，白色文字
- Reject 按钮：背景 `--color-error`，白色文字
- 按钮 hover 时亮度降低 10%（使用 `filter: brightness(0.9)`）
- 按钮 disabled 时 opacity 0.5
- 评论框：100% 宽度，背景 `--color-bg-secondary`，边框 `--color-border`
- 整体内边距 `--spacing-lg`

---

### 7.4 `src/components/chat/ChatMessage.vue`

**文件路径：** `src/components/chat/ChatMessage.vue`

**Props：**
```typescript
defineProps<{
  message: ChatMessage;
}>()
```

**Emits：**
```typescript
defineEmits<{
  'approve-gate': [gateName: string, approved: boolean, comment?: string];
}>()
```

**功能：**
1. 根据 `message.role` 渲染不同样式：
   - `user`：右对齐，背景 `--color-bubble-user`，圆角左上为 `--radius-lg`，其余为 `--radius-sm`
   - `assistant`：左对齐，背景 `--color-bubble-assistant`，圆角右上为 `--radius-lg`，其余为 `--radius-sm`
   - `system`：居中，背景 `--color-bubble-system`，字号略小
2. 消息内容中的 Markdown 代码块（```语言\n代码\n```）自动识别并渲染为 `<CodeBlock>` 组件
3. 消息内容中的 `/skill xxx` 指令高亮显示（使用 `<span class="skill-cmd">` 包裹）
4. 如果 `message.isStreaming`，在内容末尾显示闪烁光标 `<span class="typing-cursor">|</span>`
5. 如果有 `message.toolCalls`，在消息内容下方渲染 `<ToolCallCard>` 列表
6. 如果有 `message.gateStatus && !message.gateStatus.resolved`，渲染 `<GateApproval>` 组件

**CSS：**
- 气泡：最大宽度 80%，`word-wrap: break-word`，`white-space: pre-wrap`
- user 气泡 `margin-left: auto`，assistant 气泡 `margin-right: auto`
- system 气泡居中，`margin: 0 auto`
- 闪烁光标动画：`@keyframes blink`，`opacity` 在 0 和 1 之间切换，周期 1s

---

### 7.5 `src/components/chat/MessageList.vue`

**文件路径：** `src/components/chat/MessageList.vue`

**Props：**
```typescript
defineProps<{
  messages: ChatMessage[];
}>()
```

**Emits：**
```typescript
defineEmits<{
  'approve-gate': [gateName: string, approved: boolean, comment?: string];
}>()
```

**功能：**
1. 使用 `v-for` 渲染消息列表，每条消息使用 `<ChatMessage>` 组件
2. 自动滚动到底部：`watch` 监听 `messages.length` 和 `messages` 深度变化，调用 `scrollToBottom()`
3. 底部留有足够的 padding 避免最后一条消息被输入框遮挡
4. 消息为空时显示占位文字："开始对话，上传数据集或使用 /skill 命令"
5. `isLoading` 时如果有新的 token 流式更新，滚动条保持在底部

**CSS：**
- `overflow-y: auto`，`flex: 1`
- 滚动条美化：宽度 6px，thumb 颜色 `--color-border`，track 透明
- 消息间距：`margin-bottom: --spacing-md`
- 空状态文字居中，颜色 `--color-text-tertiary`

---

### 7.6 `src/components/chat/ChatInput.vue`

**文件路径：** `src/components/chat/ChatInput.vue`

**Props：**
```typescript
defineProps<{
  disabled?: boolean;
  skillNames?: string[];    // 用于 /skill 自动补全
}>()
```

**Emits：**
```typescript
defineEmits<{
  send: [content: string];
}>()
```

**功能：**
1. 多行 `<textarea>`，自动调整高度（最小 1 行，最大 6 行）
2. 发送按钮（纸飞机图标，使用 SVG inline）
3. `/skill ` 触发自动补全：
   - 检测输入以 `/skill ` 开头时，弹出下拉列表显示匹配的技能名
   - 键盘上下箭头选择，Enter 确认，Escape 关闭
   - 选中后自动填充 `/skill skill-name `（末尾带空格）
4. Enter 发送（Shift+Enter 换行），发送时 trim 后若为空则忽略
5. 发送后清空输入框并重置高度
6. `disabled` 时 textarea 和按钮均禁用

**CSS：**
- 容器：flex row，背景 `--color-bg-tertiary`，圆角 `--radius-lg`，边框 `--color-border`
- textarea：`flex: 1`，无边框，无 outline，background transparent，resize none
- 发送按钮：圆形，宽高 36px，背景 `--color-accent`，白色图标
- disabled 发送按钮：opacity 0.4
- 自动补全下拉：`position: absolute`, `bottom: 100%`，背景 `--color-bg-elevated`，边框，最大高度 200px 滚动
- 自动补全条目：padding `--spacing-sm` `--spacing-md`，hover 时背景 `--color-bg-tertiary`，选中时用 `--color-accent` 标记

---

### 7.7 `src/components/chat/ChatPanel.vue`

**文件路径：** `src/components/chat/ChatPanel.vue`

**Props：** 无

**Emits：** 无（直接操作 Pinia store）

**功能：**
1. 引用 `chatStore` 和 `skillsStore`
2. 布局：顶部为阶段指示器，中间 `<MessageList>`，底部 `<ChatInput>`
3. 阶段指示器：
   - 水平步骤条，显示当前工作流阶段
   - 阶段列表：`prepare → analyze → review → execute → done`
   - 当前阶段高亮（`--color-accent`），完成阶段显示勾，Gate 阶段闪烁
   - 从 `sessionStore.currentPhase` 读取当前状态
4. 将 `chatStore.messages` 传给 `<MessageList>`
5. 将 `skillsStore.skillNames` 传给 `<ChatInput>`
6. `<ChatInput>` 的 `@send` 调用 `chatStore.sendMessage(content)`
7. `<MessageList>` 的 `@approve-gate` 调用 `sessionStore.approveGate(...)`

**CSS：**
- 容器：`display: flex; flex-direction: column; height: 100%`
- 分隔线：`border-right: 1px solid var(--color-border)`（chat panel 的右边界）
- 阶段指示器：`padding: --spacing-md --spacing-lg`，flex row，gap `--spacing-sm`
- 阶段步骤：圆形图标（24px），连线（2px 宽），文字标签

---

### 7.8 `src/components/data/UploadZone.vue`

**文件路径：** `src/components/data/UploadZone.vue`

**Props：**
```typescript
defineProps<{
  isUploading?: boolean;
  uploadProgress?: number;
}>()
```

**Emits：**
```typescript
defineEmits<{
  'file-selected': [file: File];
}>()
```

**功能：**
1. 拖拽上传区域（点击或拖拽文件到此区域触发上传）
2. `dragenter` / `dragover` 时显示蓝色高亮边框（`--color-accent`），并显示"释放文件以上传"
3. `dragleave` 时恢复默认样式
4. `drop` 时提取第一个文件，emit `file-selected`
5. 点击区域时打开文件选择对话框（`<input type="file" hidden>`），接受 `.csv,.parquet,.xlsx,.xls`
6. `isUploading` 为 true 时显示进度条和"上传中…"文字
7. 默认状态显示上传图标（SVG）和"拖拽文件到此处，或点击选择"

**CSS：**
- 虚线边框：`2px dashed var(--color-border)`，圆角 `--radius-md`
- 拖拽高亮：边框变为 `2px dashed var(--color-accent)`，背景变为 `--color-accent` 的 10% 透明度
- 过渡：边框色、背景色 `--transition-normal`
- 高度：120px，flex center
- 进度条：高 4px，背景 `--color-bg-primary`，填充色 `--color-accent`，过渡 `width 300ms`

---

### 7.9 `src/components/data/DatasetList.vue`

**文件路径：** `src/components/data/DatasetList.vue`

**Props：**
```typescript
defineProps<{
  datasets: Dataset[];
  title: string;         // '原始数据集' | '已处理数据集'
}>()
```

**Emits：** 无

**功能：**
1. 显示分组标题和数据集数量
2. 每个数据集显示：文件图标（根据 format）、文件名、行数/列数、文件大小
3. 空列表显示"暂无数据集"
4. hover 时显示更多信息（tooltip 或展开区域）

**CSS：**
- 标题：`--font-size-sm`，`--color-text-secondary`，uppercase，letter-spacing
- 每个数据集条目：padding `--spacing-sm` `--spacing-md`，hover 背景 `--color-bg-tertiary`，圆角 `--radius-sm`
- 文件图标：不同 format 不同颜色（csv: 绿色, parquet: 蓝色, excel: 绿色较深）
- 文件大小格式化显示（< 1KB / KB / MB / GB）

---

### 7.10 `src/components/data/DataSidebar.vue`

**文件路径：** `src/components/data/DataSidebar.vue`

**Props：** 无

**Emits：** 无

**功能：**
1. 引用 `datasetsStore`
2. 布局：顶部 `<UploadZone>`，下部 `<DatasetList>`（原始数据集 + 已处理数据集两组）
3. `onMounted` 时调用 `datasetsStore.fetchDatasets()`
4. `<UploadZone>` 的 `@file-selected` 调用 `datasetsStore.uploadFile(file)`

**CSS：**
- 宽度：`var(--sidebar-width)`
- `display: flex; flex-direction: column; height: 100%`
- 背景：`--color-bg-secondary`
- 右边界：`1px solid var(--color-border)`
- UploadZone 和 DatasetList 之间有分隔线
- DatasetList 区域 `flex: 1; overflow-y: auto`

---

### 7.11 `src/components/context/LineageGraph.vue`

**文件路径：** `src/components/context/LineageGraph.vue`

**Props：**
```typescript
defineProps<{
  nodes: LineageNode[];
  edges: LineageEdge[];
}>()
```

**Emits：** 无

**功能：**
1. 使用 D3.js v7 力导向图渲染数据血缘关系
2. 三种节点的视觉区分：
   - `dataset`：圆形，蓝色系
   - `operation`：圆角矩形，橙色系
   - `result`：菱形，绿色系
3. 节点标签显示节点 `label`
4. 边为灰色箭头线
5. 支持拖拽节点（D3 drag behavior）
6. 支持缩放和平移（D3 zoom behavior）
7. 首次渲染时自动居中
8. `watch` 监听 `nodes` / `edges` 变化时重新渲染
9. 组件卸载时清理 D3 绑定（`onUnmounted` 中移除 SVG 内容）

**CSS：**
- 容器：100% 宽度，`min-height: 300px`，`flex: 1`
- SVG：100% 宽高，背景 `--color-bg-primary`
- 鼠标指针在节点上时变为 `grab`/`grabbing`

D3 力导向图配置：
- `forceLink`：distance 100
- `forceManyBody`：strength -300
- `forceCenter`：容器中心
- `forceCollide`：radius 30

---

### 7.12 `src/components/context/DecisionsList.vue`

**文件路径：** `src/components/context/DecisionsList.vue`

**Props：**
```typescript
defineProps<{
  decisions: Array<{
    phase: string;
    approved: boolean;
    comment?: string;
    timestamp: number;
  }>;
}>()
```

**Emits：** 无

**功能：**
1. 历史审批记录列表，最新在上
2. 每条记录显示：
   - 审批阶段名称
   - 审批结果：`approved ? '✓ 已批准' : '✗ 已拒绝'`，对应绿色/红色
   - 审批意见（如有）
   - 时间戳（格式化为相对时间，如"3 分钟前"）
3. 空列表显示"暂无审批记录"

**CSS：**
- 列表项：padding `--spacing-md`，底部边框 `1px solid var(--color-border-light)`
- 审批结果：字体加粗
- 意见：`--color-text-secondary`，字号 `--font-size-sm`，斜体
- 时间：`--color-text-tertiary`，字号 `--font-size-xs`

---

### 7.13 `src/components/context/ParametersDisplay.vue`

**文件路径：** `src/components/context/ParametersDisplay.vue`

**Props：**
```typescript
defineProps<{
  parameters: Record<string, unknown>;
}>()
```

**Emits：** 无

**功能：**
1. 以键值对列表形式展示当前阶段的参数
2. 参数值根据类型智能渲染：
   - `boolean`：开关图标
   - `number`：格式化（千分位等）
   - `string`：直接显示
   - `object / array`：格式化为 JSON（使用 `<pre>`）
3. 空参数显示"当前阶段无参数"

**CSS：**
- 键值对：flex row，键名 `--color-text-secondary`，键值 `--color-text-primary`
- 间距：`margin-bottom: --spacing-sm`
- JSON pre：`--font-mono`，`--font-size-xs`，`--color-text-tertiary`

---

### 7.14 `src/components/context/ContextPanel.vue`

**文件路径：** `src/components/context/ContextPanel.vue`

**Props：** 无

**Emits：** 无

**功能：**
1. Tab 切换：`血缘图 | 审批决策 | 参数`
2. 根据当前 Tab 渲染对应的子组件：
   - "血缘图" → `<LineageGraph>`（数据来自 WebSocket `lineage_update` 事件，存在 reactive 变量中）
   - "审批决策" → `<DecisionsList>`（数据来自 WebSocket `decision_update` 事件累计）
   - "参数" → `<ParametersDisplay>`（数据来自 `sessionStore.currentPhase`）
3. 右上角折叠/展开按钮，折叠后只显示 Tab 标签，再次点击展开
4. 宽度：展开时 `var(--context-panel-width)`，折叠时 40px
5. 过渡动画：`width var(--transition-normal)`

**CSS：**
- 容器：`position: relative; overflow: hidden`
- 左边界：`1px solid var(--color-border)`
- Tab 标签：flex row，bottom border 指示器
- 激活 Tab：`--color-accent` 底部边框，文字色 `--color-text-primary`
- 非激活 Tab：`--color-text-tertiary`，hover 时 `--color-text-secondary`
- 内容区：`flex: 1; overflow-y: auto`
- 折叠按钮：绝对定位左上角

---

### 7.15 `src/components/layout/AppHeader.vue`

**文件路径：** `src/components/layout/AppHeader.vue`

**Props：** 无

**Emits：** 无

**功能：**
1. 左侧：应用标题 "DataMind Studio" + 版本号
2. 中间：技能选择器 `<select>`，从 `skillsStore.skills` 读取，"无技能"为默认选项
3. 右侧：暗色模式切换按钮（月亮/太阳图标 SVG）
4. 切换技能时调用 `sessionStore.setSkill(skill)`
5. 切换主题时调用 `themeStore.toggle()`
6. `onMounted` 时调用 `skillsStore.fetchSkills()` 和 `themeStore.init()`

**CSS：**
- 高度：`var(--header-height)`
- 背景：`--color-bg-secondary`，底部边框 `1px solid var(--color-border)`
- flex row，align-items center，padding `0 --spacing-xl`
- 标题：`--font-size-lg`，字体加粗 600，`--color-text-primary`
- 技能选择器：`--font-size-sm`，背景 `--color-bg-tertiary`，边框 `--color-border`，圆角 `--radius-sm`
- 主题按钮：宽高 36px，圆形，hover 背景 `--color-bg-tertiary`，图标色 `--color-text-secondary`
- 过渡：`--transition-fast`

---

### 7.16 `src/App.vue`

**文件路径：** `src/App.vue`

**功能：**
1. 在 `<html>` 上设置 `data-theme` 属性
2. 调用 `useWebSocket()` composable（在 `onMounted` 中 connect，`onUnmounted` 中 disconnect）
3. 布局：
   ```
   +------------------------------------------+
   |              AppHeader                    |
   +----------+-------------------+-----------+
   |          |                   |           |
   | Data     |    ChatPanel      | Context   |
   | Sidebar  |                   | Panel     |
   |          |                   |           |
   +----------+-------------------+-----------+
   ```
4. 使用 CSS Grid 实现三栏布局：
   - `grid-template-columns: var(--sidebar-width) 1fr var(--context-panel-width)`
   - `grid-template-rows: var(--header-height) 1fr`
5. 响应式处理：当视口宽度 < 900px 时，ContextPanel 折叠；< 600px 时 DataSidebar 也隐藏（通过汉堡菜单切换）

**CSS：**
- 全高度 `height: 100vh`，`overflow: hidden`
- 主内容区：`overflow: hidden`

---

## 八、Vite 配置

请生成 `vite.config.ts`：

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/upload': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/skill': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

---

## 九、入口文件

### 9.1 `src/main.ts`

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/theme.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

### 9.2 `index.html`

标准 Vite Vue 3 入口 HTML，`<div id="app"></div>`，`<script type="module" src="/src/main.ts"></script>`

---

## 十、package.json

```json
{
  "name": "datamind-studio-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "d3": "^7.9.0",
    "highlight.js": "^11.9.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vue-tsc": "^2.0.0"
  }
}
```

---

## 十一、生成顺序与交付要求

### 生成顺序（重要，必须按此顺序）

1. `src/types/index.ts` — 类型定义
2. `src/assets/theme.css` — 主题 CSS 变量 + 基础 reset
3. `src/stores/theme.ts`
4. `src/stores/skills.ts`
5. `src/stores/session.ts`
6. `src/stores/datasets.ts`
7. `src/stores/chat.ts`
8. `src/composables/useWebSocket.ts`
9. `src/components/chat/CodeBlock.vue`
10. `src/components/chat/ToolCallCard.vue`
11. `src/components/chat/GateApproval.vue`
12. `src/components/chat/ChatMessage.vue`
13. `src/components/chat/MessageList.vue`
14. `src/components/chat/ChatInput.vue`
15. `src/components/chat/ChatPanel.vue`
16. `src/components/data/UploadZone.vue`
17. `src/components/data/DatasetList.vue`
18. `src/components/data/DataSidebar.vue`
19. `src/components/context/LineageGraph.vue`
20. `src/components/context/DecisionsList.vue`
21. `src/components/context/ParametersDisplay.vue`
22. `src/components/context/ContextPanel.vue`
23. `src/components/layout/AppHeader.vue`
24. `src/App.vue`
25. `vite.config.ts`
26. `src/main.ts`
27. `index.html`
28. `package.json`
29. `tsconfig.json`

### 交付要求

1. **每个文件必须完整**，不省略任何代码。不允许出现 `// ... 其他代码`、`/* 省略 */` 等占位符。
2. **TypeScript strict 模式**，所有类型显式声明，不使用 `any`。
3. **CSS 全部使用自定义属性**，不硬编码颜色或尺寸值（reset 中的 `margin: 0; padding: 0; box-sizing: border-box` 除外）。
4. **CSS 不依赖任何 UI 库**，全部手写。
5. **每个组件必须有 `<style scoped>`**，确保样式隔离。
6. **适度的微交互动画**：hover 过渡、按钮点击反馈、加载状态——但不夸张，保持专业感。
7. **handle SSE 流的正确方式**：使用 `fetch` + `ReadableStream` + 手动解析 `data:` 行；不使用 `EventSource`（它不支持 POST）。
8. **错误处理**：网络请求失败时显示错误状态，不静默失败；但不过度处理不可能出现的场景。
9. **每个 `.vue` SFC 的 `<template>`、`<script setup lang="ts">`、`<style scoped>` 三区块都必填**（即使某区块为空也要写出来）。

---

## 十二、补充说明

### SSE 流读取的关键代码模式（chat store）

请使用以下模式读取 SSE 流（不要用 EventSource）：

```typescript
const response = await fetch('/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id: sessionId, message: content, skill }),
})

const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n')
  buffer = lines.pop() || ''   // 最后一行可能不完整，留在 buffer
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event: SSEEvent = JSON.parse(line.slice(6))
      // 分发处理...
    }
  }
}
```

### WebSocket 重连的模式

```typescript
let reconnectAttempt = 0
const maxDelay = 30000

function scheduleReconnect() {
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), maxDelay)
  reconnectAttempt++
  setTimeout(() => connect(), delay)
}
// 在 onOpen 中: reconnectAttempt = 0
// 在 onClose / onError 中: scheduleReconnect()
```

### D3 力导向图的关键代码模式

- 使用 `d3.forceSimulation(nodes)` 创建模拟
- `d3.forceLink(edges).id(d => d.id)` 链接
- `d3.forceManyBody().strength(-300)` 排斥力
- `d3.forceCenter(width / 2, height / 2)` 居中
- `d3.zoom()` 缩放
- SVG marker 定义箭头：`<defs><marker id="arrowhead" ...></marker></defs>`
- 每次数据更新时：移除旧的 simulation，创建新的；不要试图复用 simulation（会导致内存泄漏）

---

请严格按上述规范生成全部 29 个文件。每个文件单独输出，文件名和路径作为标题。代码必须完整、可运行、生产就绪。
