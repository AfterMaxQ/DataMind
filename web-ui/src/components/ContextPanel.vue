<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import LineageGraph from './LineageGraph.vue'

const store = useSessionStore()

const recentDecisions = computed(() => store.decisions.slice(0, 10))

onMounted(async () => {
  try {
    const res = await fetch('/api/decisions?limit=10')
    if (res.ok) {
      const data = await res.json()
      store.setDecisions(data)
    }
  } catch {}
})
</script>

<template>
  <div class="context-panel">
    <!-- Session Status -->
    <div class="panel-section">
      <h4 class="section-title">Session Context</h4>
      <div class="context-status" :class="{ ready: store.contextInfo.ready }">
        <span class="status-indicator" :class="{ active: store.contextInfo.ready }"></span>
        <span>{{ store.contextInfo.ready ? 'Context: Ready' : 'Context: Loading...' }}</span>
      </div>
      <div v-if="store.contextInfo.ready" class="context-details">
        <div class="detail-row">
          <span class="detail-label">Datasets</span>
          <span class="detail-value">{{ store.contextInfo.datasets }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Decisions</span>
          <span class="detail-value">{{ store.contextInfo.decisions }}</span>
        </div>
        <div v-if="store.contextInfo.checkpoint_version" class="detail-row">
          <span class="detail-label">Checkpoint</span>
          <span class="detail-value">{{ store.contextInfo.checkpoint_version }}</span>
        </div>
        <div v-if="store.contextInfo.last_session" class="detail-row">
          <span class="detail-label">Last Session</span>
          <span class="detail-value">{{ store.contextInfo.last_session }}</span>
        </div>
      </div>
    </div>

    <!-- Skill Sessions -->
    <div class="panel-section">
      <h4 class="section-title">Active Skills</h4>
      <div v-if="store.skillSessions.length > 0" class="sessions-list">
        <div v-for="sess in store.skillSessions" :key="sess.session_id" class="session-item">
          <div class="session-header">
            <span class="session-skill">⚡ {{ sess.skill }}</span>
            <span class="session-phase" :class="sess.phase">{{ sess.phase }}</span>
          </div>
          <div v-if="sess.target" class="session-target">Target: {{ sess.target }}</div>
          <div v-if="sess.result" class="session-result">{{ sess.result }}</div>
        </div>
      </div>
      <div v-else class="empty-state">No active skill sessions</div>
    </div>

    <!-- Lineage Graph -->
    <div class="panel-section">
      <LineageGraph />
    </div>

    <!-- Active Parameters (8.8) -->
    <div class="panel-section">
      <h4 class="section-title">Parameters</h4>
      <div v-if="Object.keys(store.parameters).length > 0" class="params-list">
        <div v-for="[key, value] in Object.entries(store.parameters)" :key="key" class="param-row">
          <span class="param-key">{{ key }}</span>
          <span class="param-value">{{ typeof value === 'object' ? JSON.stringify(value) : value }}</span>
        </div>
      </div>
      <div v-else class="empty-state">No parameters loaded</div>
    </div>

    <!-- Recent Decisions -->
    <div class="panel-section">
      <h4 class="section-title">Recent Decisions</h4>
      <div v-if="recentDecisions.length > 0" class="decisions-list">
        <div v-for="d in recentDecisions" :key="d.id" class="decision-item">
          <div class="decision-what">{{ d.what }}</div>
          <div v-if="d.why" class="decision-why">{{ d.why }}</div>
          <div class="decision-time">{{ new Date(d.timestamp).toLocaleTimeString() }}</div>
        </div>
      </div>
      <div v-else class="empty-state">No decisions recorded</div>
    </div>
  </div>
</template>

<style scoped>
.context-panel {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.section-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  padding-bottom: var(--spacing-xs);
  border-bottom: 1px solid var(--color-border-light);
}

.context-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  padding: var(--spacing-sm);
  background: var(--color-bg-primary);
  border-radius: var(--radius-sm);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-muted);
}

.status-indicator.active {
  background: var(--color-success);
}

.context-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--spacing-xs) var(--spacing-sm);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
}

.detail-label {
  color: var(--color-text-muted);
}

.detail-value {
  color: var(--color-text-primary);
  font-weight: 500;
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.session-item {
  padding: var(--spacing-sm);
  background: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.session-skill {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--color-text-primary);
}

.session-phase {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-muted);
  text-transform: uppercase;
  font-weight: 500;
}

.session-phase.completed {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.session-target {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-top: 2px;
}

.session-result {
  font-size: var(--font-size-xs);
  color: var(--color-success);
  margin-top: 2px;
  font-weight: 500;
}

.decisions-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.decision-item {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-bg-primary);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-accent);
}

.decision-what {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--color-text-primary);
}

.decision-why {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.decision-time {
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.params-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px var(--spacing-sm);
  font-size: var(--font-size-xs);
  background: var(--color-bg-primary);
  border-radius: var(--radius-sm);
}

.param-key {
  color: var(--color-accent);
  font-weight: 500;
  font-family: var(--font-mono);
}

.param-value {
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-state {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  padding: var(--spacing-sm);
  font-style: italic;
}
</style>
