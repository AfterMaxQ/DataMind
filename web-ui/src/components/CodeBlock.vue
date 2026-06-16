<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

const props = defineProps<{
  code: string
  language?: string
  scriptPath?: string
}>()

const emit = defineEmits<{
  'view-scripts': [path: string]
}>()

const codeRef = ref<HTMLElement | null>(null)
const isCopied = ref(false)

const displayLang = computed(() => {
  if (props.language) {
    const lower = props.language.toLowerCase()
    if (lower === 'py' || lower === 'python') return 'python'
    if (lower === 'ts' || lower === 'typescript') return 'typescript'
    if (lower === 'js' || lower === 'javascript') return 'javascript'
    if (lower === 'sql') return 'sql'
    return lower
  }
  return 'plaintext'
})

async function copyCode() {
  try {
    await navigator.clipboard.writeText(props.code)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch {
    // clipboard may not be available
  }
}

onMounted(async () => {
  if (codeRef.value) {
    try {
      const hljs = await import('highlight.js')
      // Import common languages
      await Promise.all([
        import('highlight.js/lib/languages/python'),
        import('highlight.js/lib/languages/javascript'),
        import('highlight.js/lib/languages/typescript'),
        import('highlight.js/lib/languages/sql'),
        import('highlight.js/lib/languages/bash'),
      ])

      const lang = displayLang.value
      try {
        const result = hljs.default.highlight(props.code, { language: lang })
        codeRef.value!.innerHTML = result.value
      } catch {
        codeRef.value!.textContent = props.code
      }
    } catch {
      if (codeRef.value) {
        codeRef.value.textContent = props.code
      }
    }
  }
})
</script>

<template>
  <div class="code-block">
    <div class="code-block-header">
      <span class="code-lang">{{ displayLang }}</span>
      <div class="code-block-actions">
        <button
          v-if="scriptPath"
          class="code-action-btn"
          @click="emit('view-scripts', scriptPath)"
          title="View in Scripts"
        >
          View in Scripts
        </button>
        <button class="code-action-btn" @click="copyCode" :title="isCopied ? 'Copied!' : 'Copy code'">
          {{ isCopied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
    </div>
    <pre><code ref="codeRef" class="code-content"></code></pre>
  </div>
</template>

<style scoped>
.code-block {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin: var(--spacing-sm) 0;
  background: var(--color-code-bg);
}

.code-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-xs) var(--spacing-md);
  background: var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border);
}

.code-lang {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--color-text-muted);
  text-transform: uppercase;
  font-family: var(--font-mono);
}

.code-block-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.code-action-btn {
  font-size: var(--font-size-xs);
  padding: 2px var(--spacing-sm);
  border-radius: var(--radius-sm);
  color: var(--color-accent);
  transition: background var(--transition-fast);
}

.code-action-btn:hover {
  background: var(--color-accent-light);
}

pre {
  padding: var(--spacing-md);
  overflow-x: auto;
  margin: 0;
}

.code-content {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.5;
  color: var(--color-code-text);
  tab-size: 4;
}
</style>
