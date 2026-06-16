<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useChat } from '@/composables/useChat'
import CodeBlock from './CodeBlock.vue'
import GateApproval from './GateApproval.vue'

const store = useSessionStore()
const {
  inputText,
  sendMessage,
  approveGate,
  stopStreaming,
  parseSkillCommand,
} = useChat()

const chatContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

const skillCandidates = ['data-exploration', 'data-cleaning', 'feature-engineering', 'model-training', 'report-generation']
const showSkillSuggestions = ref(false)
const filteredSkills = ref<string[]>([])
function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, scrollToBottom)
watch(() => {
  const last = store.lastMessage
  return last?.content
}, scrollToBottom)

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (showSkillSuggestions.value && filteredSkills.value.length > 0) {
      completeSkill(filteredSkills.value[0])
      return
    }
    handleSend()
  }
  if (e.key === 'Escape') {
    showSkillSuggestions.value = false
  }
}

function handleInput() {
  const val = inputText.value
  // Check for /skill prefix
  if (val.startsWith('/')) {
    const parts = val.slice(1).toLowerCase().split(/\s+/)
    if (parts[0] === 'skill' && parts.length <= 2) {
      const query = parts[1] || ''
      filteredSkills.value = skillCandidates.filter((s) =>
        s.toLowerCase().includes(query.toLowerCase())
      )
      showSkillSuggestions.value = filteredSkills.value.length > 0
    } else {
      showSkillSuggestions.value = false
    }
  } else {
    showSkillSuggestions.value = false
  }
}

function completeSkill(skill: string) {
  inputText.value = `/skill ${skill} `
  showSkillSuggestions.value = false
  nextTick(() => inputRef.value?.focus())
}

async function handleSend() {
  if (!inputText.value.trim() || store.isStreaming) return
  const text = inputText.value
  inputText.value = ''
  showSkillSuggestions.value = false
  await sendMessage(text)
  scrollToBottom()
}

function handleStop() {
  stopStreaming()
}

const viewScriptPath = ref<string | null>(null)

function handleViewScripts(path: string) {
  viewScriptPath.value = path
  console.log('View scripts:', path)
}

async function onGateApprove(sessionDir: string, phaseId: string, comment: string) {
  await approveGate(sessionDir, phaseId, true, comment)
}

async function onGateReject(sessionDir: string, phaseId: string, comment: string) {
  await approveGate(sessionDir, phaseId, false, comment)
}

function highlightSkillCommands(text: string): string {
  return text.replace(
    /(\/skill\s+[\w-]+)/g,
    '<span class="skill-cmd">$1</span>'
  )
}

function parseCodeBlocks(content: string): Array<{ type: 'text' | 'code'; content: string; language?: string }> {
  const blocks: Array<{ type: 'text' | 'code'; content: string; language?: string }> = []
  const regex = /```(\w+)?\n([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'text', content: content.slice(lastIndex, match.index) })
    }
    blocks.push({ type: 'code', content: match[2].trim(), language: match[1] || 'plaintext' })
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < content.length) {
    blocks.push({ type: 'text', content: content.slice(lastIndex) })
  }

  return blocks
}

const parsedMessages = computed(() => {
  return new Map(store.messages.map(msg => [msg.id, parseCodeBlocks(msg.content)]))
})

onMounted(() => {
  inputRef.value?.focus()
})
</script>

<template>
  <div class="chat-panel">
    <div class="chat-messages" ref="chatContainer">
      <div v-if="store.messages.length === 0" class="chat-empty">
        <div class="empty-icon">💬</div>
        <h3>DataMind Studio</h3>
        <p>Type a message or use <code>/skill &lt;name&gt;</code> to invoke a skill.</p>
        <div class="skill-hints">
          <span
            v-for="skill in skillCandidates"
            :key="skill"
            class="skill-hint"
            @click="inputText = `/skill ${skill} `; inputRef?.focus()"
          >
            /skill {{ skill }}
          </span>
        </div>
      </div>

      <div
        v-for="msg in store.messages"
        :key="msg.id"
        class="chat-message"
        :class="`message-${msg.role}`"
      >
        <div v-if="msg.role === 'user'" class="message-bubble user-bubble">
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <div v-else-if="msg.role === 'system'" class="message-bubble system-bubble">
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <div v-else class="message-bubble ai-bubble">
          <template v-for="(block, idx) in parsedMessages.get(msg.id)" :key="idx">
            <span v-if="block.type === 'text'" class="message-text" v-html="highlightSkillCommands(block.content)"></span>
            <CodeBlock
              v-else
              :code="block.content"
              :language="block.language"
              :scriptPath="block.language === 'python' ? `scripts/${msg.skill_name || 'script'}_${idx}.py` : undefined"
              @view-scripts="handleViewScripts"
            />
          </template>

          <GateApproval
            v-if="msg.gate"
            :gate="msg.gate"
            @approve="onGateApprove"
            @reject="onGateReject"
          />

          <span v-if="store.isStreaming && msg === store.lastMessage" class="cursor-blink">|</span>
        </div>

        <div v-if="msg.skill_name" class="skill-tag">
          ⚡ {{ msg.skill_name }}
        </div>
      </div>
    </div>

    <div class="chat-input-area">
      <div v-if="showSkillSuggestions" class="skill-suggestions">
        <div
          v-for="skill in filteredSkills"
          :key="skill"
          class="skill-suggestion-item"
          @click="completeSkill(skill)"
        >
          ⚡ /skill {{ skill }}
        </div>
      </div>
      <div class="input-row">
        <input
          ref="inputRef"
          v-model="inputText"
          type="text"
          class="chat-input"
          placeholder="Type a message or /skill..."
          @keydown="handleKeydown"
          @input="handleInput"
          :disabled="store.isStreaming"
        />
        <button
          v-if="store.isStreaming"
          class="send-btn stop-btn"
          @click="handleStop"
        >
          Stop
        </button>
        <button
          v-else
          class="send-btn"
          @click="handleSend"
          :disabled="!inputText.trim()"
        >
          Send
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  gap: var(--spacing-sm);
  color: var(--color-text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-sm);
}

.chat-empty h3 {
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

.chat-empty p {
  font-size: var(--font-size-sm);
}

.chat-empty code {
  background: var(--color-bg-code);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.skill-hints {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  justify-content: center;
  margin-top: var(--spacing-md);
}

.skill-hint {
  padding: 4px 10px;
  background: var(--color-accent-light);
  color: var(--color-accent);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-family: var(--font-mono);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.skill-hint:hover {
  background: var(--color-accent);
  color: white;
}

.chat-message {
  display: flex;
  flex-direction: column;
  max-width: 85%;
}

.message-user {
  align-self: flex-end;
}

.message-ai {
  align-self: flex-start;
}

.message-system {
  align-self: center;
}

.message-bubble {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  line-height: 1.5;
  word-wrap: break-word;
}

.user-bubble {
  background: var(--color-message-user);
  color: var(--color-message-user-text);
  border-bottom-right-radius: 2px;
}

.ai-bubble {
  background: var(--color-message-ai);
  color: var(--color-message-ai-text);
  border-bottom-left-radius: 2px;
}

.system-bubble {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-style: italic;
}

.message-text {
  font-size: var(--font-size-base);
  white-space: pre-wrap;
}

.message-text :deep(.skill-cmd) {
  color: var(--color-accent);
  font-weight: 500;
  background: var(--color-accent-light);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: var(--color-accent);
}

@keyframes blink {
  50% { opacity: 0; }
}

.skill-tag {
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--color-accent);
  font-weight: 500;
}

/* Input area */
.chat-input-area {
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}

.skill-suggestions {
  margin-bottom: var(--spacing-xs);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.skill-suggestion-item {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-xs);
  font-family: var(--font-mono);
  color: var(--color-accent);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.skill-suggestion-item:hover {
  background: var(--color-accent-light);
}

.input-row {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.chat-input {
  flex: 1;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-input);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  outline: none;
  transition: border-color var(--transition-fast);
}

.chat-input:focus {
  border-color: var(--color-accent);
}

.chat-input:disabled {
  opacity: 0.7;
}

.send-btn {
  padding: var(--spacing-sm) var(--spacing-xl);
  background: var(--color-accent);
  color: white;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: background var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stop-btn {
  background: var(--color-error);
}

.stop-btn:hover {
  background: var(--color-error);
  filter: brightness(1.1);
}
</style>
