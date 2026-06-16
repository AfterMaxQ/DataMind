import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore, type Dataset } from '@/stores/session'

describe('Session Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with empty messages', () => {
    const store = useSessionStore()
    expect(store.messages).toHaveLength(0)
  })

  it('starts with empty datasets', () => {
    const store = useSessionStore()
    expect(store.datasets).toHaveLength(0)
  })

  it('adds a user message', () => {
    const store = useSessionStore()
    store.addMessage({
      id: '1',
      role: 'user',
      content: 'Hello',
      timestamp: Date.now(),
    })
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[0].content).toBe('Hello')
  })

  it('appends to last AI message', () => {
    const store = useSessionStore()
    store.addMessage({
      id: '1',
      role: 'ai',
      content: 'Hello',
      timestamp: Date.now(),
    })
    store.appendToLastMessage(' world')
    expect(store.messages[0].content).toBe('Hello world')
  })

  it('categorizes datasets as raw or processed', () => {
    const store = useSessionStore()
    store.setDatasets([
      { id: '1', name: 'sales.csv', path: 'data/raw/sales.csv' },
      { id: '2', name: 'cleaned.csv', path: 'data/processed/cleaned.csv' },
      { id: '3', name: 'other.csv', path: 'somewhere/other.csv' },
    ])
    expect(store.rawDatasets).toHaveLength(1)
    expect(store.processedDatasets).toHaveLength(1)
    expect(store.rawDatasets[0].name).toBe('sales.csv')
    expect(store.processedDatasets[0].name).toBe('cleaned.csv')
  })

  it('adds decisions in reverse chronological order', () => {
    const store = useSessionStore()
    store.addDecision({
      id: '1',
      what: 'First',
      why: '',
      alternatives: [],
      timestamp: new Date().toISOString(),
    })
    store.addDecision({
      id: '2',
      what: 'Second',
      why: '',
      alternatives: [],
      timestamp: new Date().toISOString(),
    })
    expect(store.decisions).toHaveLength(2)
    expect(store.decisions[0].what).toBe('Second')
  })

  it('adds lineage nodes without duplicates', () => {
    const store = useSessionStore()
    store.addLineageNode({ id: 'n1', type: 'dataset', name: 'test.csv' })
    store.addLineageNode({ id: 'n1', type: 'dataset', name: 'test.csv' })
    expect(store.lineageNodes).toHaveLength(1)
  })

  it('sets WebSocket connection status', () => {
    const store = useSessionStore()
    expect(store.wsConnected).toBe(false)
    store.setWsConnected(true)
    expect(store.wsConnected).toBe(true)
  })

  it('clears messages', () => {
    const store = useSessionStore()
    store.addMessage({ id: '1', role: 'user', content: 'hi', timestamp: Date.now() })
    store.clearMessages()
    expect(store.messages).toHaveLength(0)
  })

  // -- Gap 1: Dataset metadata (8.4) --

  it('accepts datasets with row_count and column_count metadata (8.4)', () => {
    const store = useSessionStore()
    store.setDatasets([
      { id: '1', name: 'sales.csv', path: 'data/raw/sales.csv', row_count: 1000, column_count: 12 },
      { id: '2', name: 'cleaned.csv', path: 'data/processed/cleaned.csv', row_count: 950, column_count: 8, script_path: 'scripts/clean.py' },
    ])
    expect(store.datasets[0].row_count).toBe(1000)
    expect(store.datasets[0].column_count).toBe(12)
    expect(store.datasets[1].script_path).toBe('scripts/clean.py')
  })

  it('selectDataset highlights the node in lineage graph (8.4)', () => {
    const store = useSessionStore()
    store.setDatasets([
      { id: '1', name: 'sales.csv', path: 'data/raw/sales.csv' },
    ])
    store.selectDataset('1')
    expect(store.selectedDatasetId).toBe('1')
    store.selectDataset(null)
    expect(store.selectedDatasetId).toBeNull()
  })

  // -- Gap 2: Parameters display (8.8) --

  it('starts with empty parameters (8.8)', () => {
    const store = useSessionStore()
    expect(store.parameters).toEqual({})
  })

  it('setParameters updates parameters (8.8)', () => {
    const store = useSessionStore()
    store.setParameters({ learning_rate: 0.001, epochs: 10 })
    expect(store.parameters).toEqual({ learning_rate: 0.001, epochs: 10 })
  })
})
