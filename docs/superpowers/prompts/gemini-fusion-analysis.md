# Gemini Fusion Analysis: DataMind Studio Web UI

## Sources Compared

- **Source A**: Current `web-ui/src/` implementation (Task 8 agent)
- **Source B**: Gemini 3.5 Flash full SPA (29-file Vue 3 + TypeScript)
- **Source C**: Gemini 3.1 Pro full SPA (29-file Vue 3 + TypeScript)

---

## 1. Type System

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Location** | Inline in `session.ts` store | Dedicated `src/types/index.ts` | Dedicated `src/types/index.ts` | **Both Geminis** |
| **SSEEvent** | No typed event — parsed as `Record<string, unknown>` | Discriminated union: `{ type: 'token' \| 'tool_call' \| ... }` | Same discriminated union | **Both Geminis** |
| **ToolCall** | Not typed | `ToolCall` with `id`, `toolName`, `args`, `result`, `status` | Same structure | **Both Geminis** |
| **ToolCallStatus** | N/A | `'pending' \| 'running' \| 'completed' \| 'error'` | Same | **Both Geminis** |
| **Skill** | Not typed (inline strings) | `Skill` with `name`, `displayName`, `description`, `category` | Same | **Both Geminis** |
| **PhaseInfo** | Implicit in `SkillSession` | `PhaseInfo` with `name`, `status: 'idle'\|'running'\|'completed'\|'gate'` | Same but without `gate` | **Gemini Flash** |
| **ChatMessage** | `role: 'user'\|'ai'\|'system'`, has `code_blocks`, `gate`, `skill_name`, `phase_id` | `role: 'user'\|'assistant'\|'system'`, has `toolCalls`, `gateStatus`, `isStreaming` | Same as Flash | **Gemini Flash** (cleaner concern separation) |
| **Dataset** | `id`, `name`, `path?`, `created_at?`, `row_count?`, `column_count?`, `script_path?` | `id`, `name`, `type: 'raw'\|'processed'`, `format`, `size`, `rows?`, `columns?`, `createdAt` | Same as Flash | **Both Geminis** (richer metadata) |

**Verdict**: Both Geminis win on type system. The dedicated types file with discriminated unions for SSE events and explicit ToolCall types is significantly better than the current inline approach. **Adopt: Create `src/types/index.ts` with the best from both Geminis.**

---

## 2. CSS / Theming

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Default theme** | Light | Dark | Dark | Preference-based |
| **Selector** | `[data-theme='dark']` | `[data-theme="light"]` (default dark) | `html[data-theme="light"]` | **Current** (light default is more conventional) |
| **Spacing scale** | None (inline values) | `--spacing-xs` through `--spacing-2xl` (6 steps) | Same (6 steps) | **Both Geminis** |
| **Font size scale** | None (inline values) | `--font-size-xs` through `--font-size-2xl` (6 steps) | Same (6 steps) | **Both Geminis** |
| **Transition tokens** | None (inline `0.15s`) | `--transition-fast: 150ms ease`, `--transition-normal: 250ms ease` | Same | **Both Geminis** |
| **Color granularity** | 30 variables | 35+ variables with `--color-bg-elevated`, `--color-surface`, `--color-text-tertiary` | ~30 variables | **Gemini Flash** |
| **Code colors** | None (relies on highlight.js theme) | `--color-code-bg`, `--color-code-text` per theme | Same | **Both Geminis** |
| **Shadow depth** | 3 levels (`sm`, `md`, `lg`) | 3 levels, darker in dark mode | 3 levels | Tie |
| **Font stack** | Inter + JetBrains Mono (explicit) | System font stack (generic) | System font stack (generic) | **Current** (explicit fonts) |
| **`--radius-full`** | No | `--radius-full: 9999px` | Same | **Both Geminis** |

**Verdict**: Both Geminis win on CSS architecture. The spacing scale, font-size scale, and transition tokens eliminate magic numbers. **Adopt: Add spacing, font-size, and transition scales. Add `--color-bg-elevated`, `--color-text-tertiary`, `--radius-full`. Keep current dark/light color values and font stacks.**

---

## 3. Component Design

### ChatPanel

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Structure** | Monolithic 448-line SFC | Decomposed: ChatPanel + ChatMessage + MessageList + ChatInput | Same decomposition | **Both Geminis** |
| **Phase indicator** | None | Pipeline step tracker with animated nodes | Phase indicator stepper | **Gemini Pro** |
| **Skill autocomplete** | Inline in ChatPanel | Dedicated ChatInput with Arrow key nav | Dedicated ChatInput with Arrow key nav | **Both Geminis** |
| **Code parsing** | Inline `parseCodeBlocks` function | In ChatMessage via `messageParts` computed | In ChatMessage via `parsedContent` computed | Tie |

### CodeBlock

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **highlight.js loading** | Dynamic import with Promise.all for languages | Static import (bundled) | Static import | **Current** (dynamic import = code splitting) |
| **Copy feedback** | No visual feedback | "Copied" badge with 2s timeout | "Copied" feedback | **Gemini Flash** |
| **Language display** | `displayLang` computed (case normalization) | `language-tag` lowercase | `lang` uppercase | **Current** (normalization) |
| **View Scripts btn** | Conditional emit | Always shown as `nav-btn` | Always shown | **Current** (conditional is cleaner) |

### GateApproval

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Visual** | 2px warning border, clear button colors | 3px left warning border, SVG icon, detailed description | 3px left warning border | **Gemini Flash** (richer UI with SVG icon and description) |
| **Comment input** | `<input>` | `<textarea>` | `<textarea>` | **Both Geminis** (textarea better for comments) |
| **Emits** | `(sessionDir, phaseId, comment)` | `(comment?)` | `(comment?)` | **Current** (passes necessary IDs) |

### ToolCallCard — NOT in current, present in both Geminis

Currently missing entirely. Both Geminis have a rich expandable card with status icons, parameter display, and result display. **Adopt: Add ToolCallCard component.**

### ContextPanel

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Layout** | Flat list of sections | Tabbed with collapsible panel | Tabbed with collapsible panel | **Gemini Pro** (cleanest tabs) |
| **Tabs** | No tabs | Lineage / Decisions / Params tabs | Lineage / Decisions / Params tabs with active indicator | **Gemini Pro** |
| **Collapse** | No | Collapse toggle button (overlaps at left edge) | Collapse toggle button (integrated in header) | **Gemini Pro** |

### LineageGraph

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Library** | Manual SVG DOM manipulation | D3.js force simulation | D3.js force simulation | **Both Geminis** (D3 is far superior) |
| **Interactivity** | None | Zoom + drag nodes | Zoom + drag nodes | **Both Geminis** |
| **Node shapes** | Circle only | Circle (dataset), Rect (operation), Diamond (result) | Circle, Rect, Diamond | **Both Geminis** |
| **Layout** | Manual BFS vertical layout | Force-directed (D3) | Force-directed (D3) | **Both Geminis** |
| **Responsive** | Fixed width 300px | Resize listener, fills parent | Resize listener, fills parent | **Both Geminis** |

### App.vue Layout

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Layout method** | Flexbox (3-panel) | CSS Grid (2-row, flex body) | CSS Grid (2-row, 3-col) | **Gemini Pro** (Grid is cleaner for this layout) |
| **Responsive** | Hides context at 900px, sidebar at 600px | Same approach via :deep() | Same approach | **Current** (simpler scoped CSS) |
| **AppHeader** | Inline in App.vue | Separate component with skill dropdown | Separate component with skill dropdown | **Both Geminis** |

---

## 4. Composables

### useWebSocket

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Reconnect** | Exponential backoff (1s-30s), timer cleanup | Exponential backoff, `onUnmounted` disconnect | Exponential backoff, `onUnmounted` disconnect | **Current** (better timer management with `destroyed` flag) |
| **Auto-connect** | `onMounted` auto-connects | Caller must call `connect()` | Caller must call `connect()` | **Current** (auto-connect is convenient) |
| **Data sharing** | Writes directly to store | Accepts callbacks | Uses global refs (`wsLineageNodes`, etc.) | **Gemini Pro** (global refs avoid store coupling for visualization data) |
| **Event handling** | Switch on `event` string with manual casting | Switch on `type` string, passes to callbacks | Switch on `type` string, uses global refs | Tie |

### useChat (Current only — Geminis have chat store instead)

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Architecture** | Composable with local state | Store (`useChatStore`) | Store (`useChatStore`) | **Geminis** (store is more Vue-idiomatic) |
| **SSE parsing** | Simple line-by-line with buffer | Switch-based on `SSEEvent` discriminated union | Switch-based on `SSEEvent` | **Both Geminis** |
| **Skill parsing** | Regex `parseSkillCommand` | Done in ChatPanel | Done in ChatPanel | **Current** (composable has it) |
| **Abort handling** | `AbortController` with clean stop/replace | Not implemented | Not implemented | **Current** |

---

## 5. Stores (Pinia)

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Store count** | 2 (session + theme) | 5 (theme, skills, session, datasets, chat) | 5 (theme, skills, session, datasets, chat) | Both approaches valid — depends on app complexity |
| **Store style** | Composition API (`setup` stores) | Options API stores | Composition API stores | **Current / Gemini Pro** (Composition API) |
| **Chat in session** | Yes (messages, streaming) | Separate `chat` store | Separate `chat` store | **Geminis** (better separation of concerns) |
| **Datasets in session** | Yes | Separate `datasets` store | Separate `datasets` store | **Geminis** (better separation) |
| **Skills store** | Inline in session (`availableSkills`) | Separate `skills` store with categories | Separate `skills` store with categories | **Both Geminis** |
| **Gate in session** | `GatePrompt` on message | Separate `gatePending` in session store | Separate `gatePending` in session store | Tie |

---

## 6. SSE Parsing

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Event type** | `event` field (string) | `type` field (discriminated union) | `type` field (discriminated union) | **Both Geminis** |
| **Handler** | Inline if/else in read loop | Dedicated `handleIncomingSSEEvent` with switch | Dedicated `handleSSEEvent` with switch | **Both Geminis** |
| **Tool calls** | Not handled | Full structured handling: create ToolCall, update result | Same | **Both Geminis** |
| **Phase tracking** | Not handled | Updates session store phase | Same | **Both Geminis** |
| **Gate events** | Not handled via SSE | Creates gate status, sets pending | Same | **Both Geminis** |
| **Error events** | Basic content append | Creates system message | Creates system message | Tie |

---

## 7. Error Handling

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Stream errors** | Appended to message content | Creates system message + cleans up streaming state | Creates system message + cleans up streaming state | **Both Geminis** |
| **Upload errors** | Display in `uploadError` ref | Display in store `uploadError`, console.error | Display in store `uploadError` | **Current** (local error state is cleaner) |
| **Network errors** | Silent catch in onMounted fetches | Fallback data in store | console.error only | **Current** (silent catch is appropriate for optional data) |
| **Tool errors** | N/A | Displayed in ToolCallCard with red styling | Displayed in ToolCallCard | **Both Geminis** |

---

## 8. UX Details

| Aspect | Current | Gemini Flash | Gemini Pro | Winner |
|--------|---------|-------------|------------|--------|
| **Icons** | Emoji (💬, 📄, 📊, 🚦, ⚡) | SVG icons (inline paths) | SVG icons (inline paths) | **Both Geminis** (SVG is more professional, theme-aware) |
| **Animations** | Blink cursor, hover transitions | Pulse nodes, spin tool icons, pulse border on running tools | Blink cursor, pulse gate | **Gemini Flash** (richest animations) |
| **File size formatting** | None | `formatBytes()` function | `formatSize()` function | **Both Geminis** |
| **Relative time** | `toLocaleDateString()` / `toLocaleTimeString()` | `formatRelativeTime()` ("Just now", "5m ago") | `formatTime()` ("X秒前", "X分钟前") | **Gemini Flash** (English relative time) |
| **Keyboard nav** | Enter to send, Escape to close suggestions | Arrow keys in autocomplete, Enter to select | Arrow keys in autocomplete, Enter to select | **Both Geminis** (better autocomplete UX) |
| **Progress bar** | None | Upload progress bar with percentage | Upload progress bar with percentage | **Both Geminis** |
| **Empty states** | Simple text | Rich SVG illustration + descriptive text | Simple text | **Gemini Flash** |
| **ARIA / a11y** | None | `type="button"` on buttons, aria via roles | `type="button"` on buttons | **Gemini Flash** (marginally better) |

---

## Summary of Best Patterns to Adopt

### From Gemini 3.5 Flash (Source B):
1. **Type system**: Separate `src/types/index.ts` with discriminated SSEEvent union, ToolCall types
2. **CSS scale tokens**: `--spacing-*`, `--font-size-*`, `--transition-*`
3. **CodeBlock**: Copy-to-clipboard with visual feedback ("Copied" badge)
4. **Relative time formatting**: `formatRelativeTime()` function
5. **Rich empty states**: SVG illustrations with descriptive text
6. **Upload progress bar**: Visual progress indicator during file upload
7. **ToolCallCard component**: Expandable card with status animations
8. **GateApproval enhancements**: SVG warning icon, descriptive text, textarea for comments

### From Gemini 3.1 Pro (Source C):
1. **D3.js LineageGraph**: Force-directed layout with zoom, drag, varied node shapes
2. **Collapsible ContextPanel**: Tab-based navigation with collapse toggle
3. **CSS Grid layout**: Cleaner App.vue layout using CSS Grid
4. **Phase indicator stepper**: Visual pipeline progress in ChatPanel
5. **Global refs in useWebSocket**: Cleaner data sharing for lineage/decisions
6. **ChatInput auto-resize**: textarea with dynamic height adjustment
7. **File format badges**: Color-coded dataset icons by format type
8. **AppHeader with skill dropdown**: Better skill selection UX

### Kept from Current Implementation:
1. **Light theme default**: More conventional than dark default
2. **Explicit font stacks**: Inter + JetBrains Mono (better than system fonts)
3. **Dynamic highlight.js import**: Code splitting (vs. bundling)
4. **Flexbox layout**: Simpler than CSS Grid for this app
5. **onMounted auto-connect**: Convenient WebSocket lifecycle
6. **AbortController streaming**: Better stream cancellation
7. **Conditional View Scripts button**: Only shown when scriptPath exists
8. **Current color palette**: Tested with dark/light themes, works well
