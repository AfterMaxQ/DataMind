<script setup lang="ts">
import { onMounted } from 'vue'
import DataSidebar from './components/DataSidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import ContextPanel from './components/ContextPanel.vue'
import { useThemeStore } from './stores/theme'
import { useSessionStore } from './stores/session'
import { useWebSocket } from './composables/useWebSocket'

const themeStore = useThemeStore()
const sessionStore = useSessionStore()

// Start WebSocket connection
const { connected: wsConnected } = useWebSocket()

// Load initial data
onMounted(async () => {
  try {
    // Fetch context
    const ctxRes = await fetch('/api/context')
    if (ctxRes.ok) {
      const ctxData = await ctxRes.json()
      sessionStore.setContextInfo({
        ready: true,
        datasets: 0,
        decisions: 0,
      })
    }
  } catch {}

  try {
    // Fetch datasets
    const dsRes = await fetch('/api/datasets')
    if (dsRes.ok) {
      const dsData = await dsRes.json()
      sessionStore.setDatasets(dsData)
    }
  } catch {}

  try {
    // Fetch skills
    const skillRes = await fetch('/api/skills')
    if (skillRes.ok) {
      const skillData = await skillRes.json()
      if (Array.isArray(skillData)) {
        sessionStore.setAvailableSkills(skillData)
      }
    }
  } catch {}
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-left">
        <h1 class="app-title">DataMind Studio</h1>
        <span v-if="wsConnected" class="status-dot connected" title="WebSocket connected"></span>
        <span v-else class="status-dot disconnected" title="WebSocket disconnected"></span>
      </div>
      <div class="header-right">
        <span class="context-status">
          {{ sessionStore.contextInfo.ready ? 'Context: Ready' : 'Context: Loading...' }}
        </span>
        <button
          class="theme-toggle"
          @click="themeStore.toggle()"
          :title="themeStore.theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'"
        >
          {{ themeStore.theme === 'light' ? '🌙' : '☀️' }}
        </button>
      </div>
    </header>

    <div class="app-body">
      <DataSidebar class="panel sidebar-panel" />
      <ChatPanel class="panel chat-panel" />
      <ContextPanel class="panel context-panel" />
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.app-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.connected {
  background: var(--color-success);
}

.status-dot.disconnected {
  background: var(--color-error);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.context-status {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.theme-toggle {
  font-size: 18px;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.theme-toggle:hover {
  background: var(--color-bg-hover);
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.panel {
  height: 100%;
  overflow-y: auto;
}

.sidebar-panel {
  width: var(--sidebar-width);
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-sidebar-bg);
}

.chat-panel {
  flex: 1;
  background: var(--color-chat-bg);
}

.context-panel {
  width: var(--context-width);
  flex-shrink: 0;
  border-left: 1px solid var(--color-border);
  background: var(--color-context-bg);
}

@media (max-width: 900px) {
  .context-panel {
    display: none;
  }
}

@media (max-width: 600px) {
  .sidebar-panel {
    display: none;
  }
}
</style>
