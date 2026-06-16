// ============================================================
// DataMind Studio — Core TypeScript Types
// ============================================================

// --- Message Roles ---
export type MessageRole = 'user' | 'ai' | 'system'

// --- Tool Calls ---
export type ToolCallStatus = 'pending' | 'running' | 'completed' | 'error'

export interface ToolResult {
  success: boolean
  data?: unknown
  error?: string
}

export interface ToolCall {
  id: string
  toolName: string
  args: Record<string, unknown>
  result?: ToolResult
  status: ToolCallStatus
}

// --- Gate Approval ---
export interface GatePrompt {
  phase_id: string
  phase_name: string
  context: string
  session_dir: string
}

// --- SSE Events ---
export type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; tool: string; result: Record<string, unknown> }
  | { type: 'phase'; phase: string; status: 'started' | 'completed' }
  | { type: 'gate'; phase: string; gate_name: string }
  | { type: 'done' }
  | { type: 'error'; message: string }

// --- Chat Messages ---
export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: number
  code_blocks?: CodeBlockData[]
  gate?: GatePrompt
  skill_name?: string
  phase_id?: string
  toolCalls?: ToolCall[]
  gateStatus?: GateStatus
  isStreaming?: boolean
}

export interface CodeBlockData {
  language: string
  code: string
  script_path?: string
}

export interface GateStatus {
  gateName: string
  phase: string
  resolved: boolean
  approved?: boolean
  comment?: string
}

// --- Datasets ---
export interface Dataset {
  id: string
  name: string
  path?: string
  created_at?: string
  row_count?: number
  column_count?: number
  script_path?: string
}

// --- Decisions ---
export interface Decision {
  id: string
  what: string
  why: string
  alternatives: string[]
  timestamp: string
}

export interface DecisionRecord {
  phase: string
  approved: boolean
  comment?: string
  timestamp: number
}

// --- Lineage Graph ---
export interface LineageNode {
  id: string
  type: string
  name: string
  label?: string
  path?: string
  metadata?: Record<string, unknown>
  created_at?: string
}

export interface LineageEdge {
  source: string
  target: string
  edge_type?: string
  label?: string
}

// --- Skills ---
export interface Skill {
  name: string
  displayName: string
  description: string
  category: string
}

export interface SkillSession {
  session_id: string
  skill: string
  target: string
  phase: string
  result: string | null
}

// --- Phase / Workflow ---
export interface PhaseInfo {
  name: string
  status: 'idle' | 'running' | 'completed' | 'gate'
  startedAt?: number
  parameters?: Record<string, unknown>
}

// --- Context ---
export interface ContextInfo {
  ready: boolean
  datasets: number
  decisions: number
  checkpoint_version?: string
  last_session?: string
}

// --- WebSocket ---
export type WSEventType = 'phase_transition' | 'lineage_update' | 'decision_update' | 'token_stream'

export interface WSEvent {
  type: WSEventType
  [key: string]: unknown
}

export interface WsEvent {
  event: string
  data: Record<string, unknown>
}
