import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Dataset,
  Decision,
  LineageNode,
  LineageEdge,
  ChatMessage,
  CodeBlockData,
  GatePrompt,
  SkillSession,
  ContextInfo,
} from '@/types'

// Re-export for backward compatibility
export type {
  Dataset,
  Decision,
  LineageNode,
  LineageEdge,
  ChatMessage,
  CodeBlockData,
  GatePrompt,
  SkillSession,
  ContextInfo,
}

export const useSessionStore = defineStore('session', () => {
  // Datasets
  const datasets = ref<Dataset[]>([])
  const datasetsLoading = ref(false)

  // Decisions
  const decisions = ref<Decision[]>([])
  const decisionsLoading = ref(false)

  // Lineage graph
  const lineageNodes = ref<LineageNode[]>([])
  const lineageEdges = ref<LineageEdge[]>([])

  // Chat
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)

  // Skills
  const skillSessions = ref<SkillSession[]>([])
  const availableSkills = ref<string[]>([])

  // Context
  const contextInfo = ref<ContextInfo>({
    ready: false,
    datasets: 0,
    decisions: 0,
  })

  // WebSocket connection status
  const wsConnected = ref(false)

  // Parameters from params.json (8.8)
  const parameters = ref<Record<string, unknown>>({})

  // Currently selected dataset (8.4)
  const selectedDatasetId = ref<string | null>(null)

  // Derived
  const rawDatasets = computed(() =>
    datasets.value.filter((d) => {
      const p = d.path ?? ''
      return p.includes('/raw/') || p.includes('\\raw\\')
    })
  )

  const processedDatasets = computed(() =>
    datasets.value.filter((d) => {
      const p = d.path ?? ''
      return p.includes('/processed/') || p.includes('\\processed\\')
    })
  )

  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  // Actions
  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  function appendToLastMessage(content: string) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'ai') {
      last.content += content
    }
  }

  function clearMessages() {
    messages.value = []
  }

  function setDatasets(list: Dataset[]) {
    datasets.value = list
  }

  function addDataset(ds: Dataset) {
    datasets.value.push(ds)
  }

  function setDecisions(list: Decision[]) {
    decisions.value = list
  }

  function addDecision(d: Decision) {
    decisions.value.unshift(d)
    if (decisions.value.length > 100) decisions.value.pop()
  }

  function setLineageGraph(nodes: LineageNode[], edges: LineageEdge[]) {
    lineageNodes.value = nodes
    lineageEdges.value = edges
  }

  function addLineageNode(node: LineageNode) {
    const existing = lineageNodes.value.find((n) => n.id === node.id)
    if (!existing) lineageNodes.value.push(node)
  }

  function addLineageEdge(edge: LineageEdge) {
    const existing = lineageEdges.value.find(
      (e) => e.source === edge.source && e.target === edge.target
    )
    if (!existing) lineageEdges.value.push(edge)
  }

  function setWsConnected(connected: boolean) {
    wsConnected.value = connected
  }

  function setContextInfo(info: ContextInfo) {
    contextInfo.value = info
  }

  function setSkillSessions(sessions: SkillSession[]) {
    skillSessions.value = sessions
  }

  function setAvailableSkills(skills: string[]) {
    availableSkills.value = skills
  }

  function selectDataset(id: string | null) {
    selectedDatasetId.value = id
  }

  function setParameters(params: Record<string, unknown>) {
    parameters.value = params
  }

  return {
    datasets,
    datasetsLoading,
    decisions,
    decisionsLoading,
    lineageNodes,
    lineageEdges,
    messages,
    isStreaming,
    skillSessions,
    availableSkills,
    contextInfo,
    wsConnected,
    rawDatasets,
    processedDatasets,
    lastMessage,
    addMessage,
    appendToLastMessage,
    clearMessages,
    setDatasets,
    addDataset,
    setDecisions,
    addDecision,
    setLineageGraph,
    addLineageNode,
    addLineageEdge,
    setWsConnected,
    setContextInfo,
    setSkillSessions,
    setAvailableSkills,
    selectDataset,
    setParameters,
    parameters,
    selectedDatasetId,
  }
})
