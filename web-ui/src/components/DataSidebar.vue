<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import type { Dataset } from '@/types'

const store = useSessionStore()
const dragOver = ref(false)
const uploadError = ref('')
const uploading = ref(false)

const MAX_UPLOAD_SIZE = 10 * 1024 * 1024 // 10 MB

function selectDataset(id: string) {
  store.selectDataset(id)
}

async function fetchDatasets() {
  store.datasetsLoading = true
  try {
    const res = await fetch('/api/datasets')
    if (res.ok) {
      const data = await res.json()
      store.setDatasets(data)
    }
  } catch {
    // backend may not be running
  } finally {
    store.datasetsLoading = false
  }
}

async function uploadFile(file: File) {
  if (file.size > MAX_UPLOAD_SIZE) {
    uploadError.value = `File exceeds maximum size of 10 MB`
    return
  }

  uploading.value = true
  uploadError.value = ''

  try {
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Upload failed')
    }

    const result = await res.json()
    store.addDataset({
      id: result.filename,
      name: result.filename,
      path: result.path,
    })

    // Refresh dataset list
    await fetchDatasets()
  } catch (e: unknown) {
    uploadError.value = e instanceof Error ? e.message : 'Upload failed'
  } finally {
    uploading.value = false
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}

function onDragLeave() {
  dragOver.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    uploadFile(files[0])
  }
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    uploadFile(input.files[0])
    input.value = ''
  }
}

function formatDate(iso: string | undefined): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString()
  } catch {
    return iso
  }
}

// Computed for datasets that don't match raw/processed patterns
const datasetsOther = computed(() =>
  store.datasets.filter((d) => {
    const p = d.path ?? ''
    return !p.includes('/raw/') && !p.includes('\\raw\\') && !p.includes('/processed/') && !p.includes('\\processed\\')
  })
)

onMounted(() => {
  fetchDatasets()
})
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-section">
      <h3 class="section-title">Datasets</h3>

      <div
        class="drop-zone"
        :class="{ 'drag-over': dragOver, uploading }"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
      >
        <label class="drop-zone-label">
          <input
            type="file"
            accept=".csv,.parquet,.xlsx,.json"
            class="file-input"
            @change="onFileSelect"
          />
          <span v-if="uploading">Uploading...</span>
          <span v-else>Drag &amp; drop or click to upload CSV</span>
        </label>
      </div>

      <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>

      <div v-if="store.datasetsLoading" class="loading">Loading datasets...</div>

      <template v-else>
        <!-- Raw datasets -->
        <div v-if="store.rawDatasets.length > 0" class="dataset-group">
          <h4 class="group-title">raw/</h4>
          <div
            v-for="ds in store.rawDatasets"
            :key="ds.id"
            class="dataset-item"
            :class="{ selected: store.selectedDatasetId === ds.id }"
            @click="selectDataset(ds.id)"
          >
            <span class="dataset-icon">📄</span>
            <div class="dataset-info">
              <span class="dataset-name">{{ ds.name }}</span>
              <span class="dataset-meta">
                <template v-if="ds.row_count !== undefined">
                  {{ ds.row_count }} rows, {{ ds.column_count ?? '?' }} cols
                </template>
                <template v-if="ds.created_at">&nbsp;&middot;&nbsp;{{ formatDate(ds.created_at) }}</template>
              </span>
            </div>
          </div>
        </div>

        <!-- Processed datasets -->
        <div v-if="store.processedDatasets.length > 0" class="dataset-group">
          <h4 class="group-title">processed/</h4>
          <div
            v-for="ds in store.processedDatasets"
            :key="ds.id"
            class="dataset-item"
            :class="{ selected: store.selectedDatasetId === ds.id }"
            @click="selectDataset(ds.id)"
          >
            <span class="dataset-icon">📊</span>
            <div class="dataset-info">
              <span class="dataset-name">{{ ds.name }}</span>
              <span class="dataset-meta">
                <template v-if="ds.row_count !== undefined">
                  {{ ds.row_count }} rows, {{ ds.column_count ?? '?' }} cols
                </template>
                <template v-if="ds.created_at">&nbsp;&middot;&nbsp;{{ formatDate(ds.created_at) }}</template>
              </span>
              <a
                v-if="ds.script_path"
                :href="'#'"
                class="script-link"
                @click.stop="selectDataset(ds.id)"
              >View Script</a>
            </div>
          </div>
        </div>

        <!-- Other datasets (not raw/processed) -->
        <div v-if="datasetsOther.length > 0" class="dataset-group">
          <h4 class="group-title">other</h4>
          <div
            v-for="ds in datasetsOther"
            :key="ds.id"
            class="dataset-item"
            :class="{ selected: store.selectedDatasetId === ds.id }"
            @click="selectDataset(ds.id)"
          >
            <span class="dataset-icon">📁</span>
            <div class="dataset-info">
              <span class="dataset-name">{{ ds.name }}</span>
              <span class="dataset-meta">
                <template v-if="ds.row_count !== undefined">
                  {{ ds.row_count }} rows, {{ ds.column_count ?? '?' }} cols
                </template>
              </span>
            </div>
          </div>
        </div>

        <div v-if="store.datasets.length === 0" class="empty-state">
          No datasets loaded
        </div>
      </template>
    </div>

    <div class="sidebar-section">
      <h3 class="section-title">Skills</h3>
      <div v-if="store.availableSkills.length > 0" class="skills-list">
        <div v-for="skill in store.availableSkills" :key="skill" class="skill-item">
          <span class="skill-icon">⚡</span>
          <span class="skill-name">{{ skill }}</span>
        </div>
      </div>
      <div v-else class="empty-state">
        No skills available
      </div>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  padding: 4px 0;
}

.drop-zone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px 12px;
  text-align: center;
  transition: border-color 0.15s, background 0.15s;
  cursor: pointer;
}

.drop-zone:hover,
.drop-zone.drag-over {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.drop-zone.uploading {
  opacity: 0.7;
  pointer-events: none;
}

.drop-zone-label {
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.file-input {
  display: none;
}

.upload-error {
  font-size: 12px;
  color: var(--color-error);
  padding: 4px 8px;
}

.loading {
  font-size: 12px;
  color: var(--color-text-muted);
  padding: 8px 0;
}

.dataset-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-title {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
  padding: 4px 8px 2px;
  font-family: var(--font-mono);
}

.dataset-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}

.dataset-item:hover {
  background: var(--color-bg-hover);
}

.dataset-item.selected {
  background: var(--color-accent-light);
}

.dataset-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.dataset-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.dataset-name {
  font-size: 13px;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dataset-meta {
  font-size: 11px;
  color: var(--color-text-muted);
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.skill-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.skill-icon {
  font-size: 12px;
}

.script-link {
  font-size: 11px;
  color: var(--color-accent);
  text-decoration: none;
  margin-top: 2px;
}

.script-link:hover {
  text-decoration: underline;
}

.empty-state {
  font-size: 12px;
  color: var(--color-text-muted);
  padding: 8px;
  font-style: italic;
}
</style>
