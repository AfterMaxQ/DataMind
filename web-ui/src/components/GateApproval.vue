<script setup lang="ts">
import { ref } from 'vue'
import type { GatePrompt } from '@/types'

const props = defineProps<{
  gate: GatePrompt
}>()

const emit = defineEmits<{
  approve: [sessionDir: string, phaseId: string, comment: string]
  reject: [sessionDir: string, phaseId: string, comment: string]
}>()

const comment = ref('')
const submitting = ref(false)
const decided = ref<'approved' | 'rejected' | null>(null)

async function handleApprove() {
  submitting.value = true
  try {
    await emit('approve', props.gate.session_dir, props.gate.phase_id, comment.value)
    decided.value = 'approved'
  } finally {
    submitting.value = false
  }
}

async function handleReject() {
  submitting.value = true
  try {
    await emit('reject', props.gate.session_dir, props.gate.phase_id, comment.value)
    decided.value = 'rejected'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="!decided" class="gate-prompt">
    <div class="gate-header">
      <span class="gate-icon">🚦</span>
      <span class="gate-title">Gate: {{ gate.phase_name }}</span>
    </div>
    <p v-if="gate.context" class="gate-context">{{ gate.context }}</p>
    <div class="gate-comment">
      <textarea
        v-model="comment"
        placeholder="Add a comment (optional)..."
        class="gate-input"
        :disabled="submitting"
        rows="2"
      ></textarea>
    </div>
    <div class="gate-actions">
      <button
        class="gate-btn approve"
        :disabled="submitting"
        @click="handleApprove"
      >
        {{ submitting ? '...' : 'Approve' }}
      </button>
      <button
        class="gate-btn reject"
        :disabled="submitting"
        @click="handleReject"
      >
        {{ submitting ? '...' : 'Reject' }}
      </button>
    </div>
  </div>
  <div v-else class="gate-decided" :class="decided">
    <span class="gate-icon">{{ decided === 'approved' ? '✅' : '❌' }}</span>
    <span>{{ decided === 'approved' ? 'Approved' : 'Rejected' }}</span>
  </div>
</template>

<style scoped>
.gate-prompt {
  border: 2px solid var(--color-warning);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  margin: var(--spacing-sm) 0;
  background: var(--color-bg-secondary);
}

.gate-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.gate-icon {
  font-size: var(--font-size-lg);
}

.gate-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.gate-context {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-md);
  line-height: 1.4;
}

.gate-comment {
  margin-bottom: var(--spacing-md);
}

.gate-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-input);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  outline: none;
  resize: vertical;
  font-family: inherit;
}

.gate-input:focus {
  border-color: var(--color-accent);
}

.gate-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.gate-btn {
  padding: var(--spacing-sm) var(--spacing-xl);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

.gate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.gate-btn.approve {
  background: var(--color-success);
  color: white;
}

.gate-btn.approve:hover:not(:disabled) {
  filter: brightness(1.1);
}

.gate-btn.reject {
  background: var(--color-error);
  color: white;
}

.gate-btn.reject:hover:not(:disabled) {
  filter: brightness(1.1);
}

.gate-decided {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-radius: var(--radius-md);
  margin: var(--spacing-sm) 0;
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.gate-decided.approved {
  background: var(--color-accent-light);
  color: var(--color-success);
}

.gate-decided.rejected {
  background: var(--color-bg-tertiary);
  color: var(--color-error);
}
</style>
