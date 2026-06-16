import { ref, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import type { WsEvent } from '@/types'

const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000

export function useWebSocket(sessionId = 'global') {
  const socket = ref<WebSocket | null>(null)
  const connected = ref(false)
  const reconnectAttempts = ref(0)
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  const store = useSessionStore()

  function connect() {
    if (destroyed) return
    if (socket.value && (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws?session_id=${encodeURIComponent(sessionId)}`

    try {
      socket.value = new WebSocket(url)
    } catch {
      scheduleReconnect()
      return
    }

    socket.value.onopen = () => {
      connected.value = true
      store.setWsConnected(true)
      reconnectAttempts.value = 0
    }

    socket.value.onmessage = (event) => {
      try {
        const msg: WsEvent = JSON.parse(event.data)
        handleEvent(msg)
      } catch {}
    }

    socket.value.onclose = () => {
      connected.value = false
      store.setWsConnected(false)
      socket.value = null
      scheduleReconnect()
    }

    socket.value.onerror = () => {
      socket.value?.close()
    }
  }

  function scheduleReconnect() {
    if (destroyed) return
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts.value),
      RECONNECT_MAX_MS
    )
    reconnectAttempts.value++
    reconnectTimer = setTimeout(connect, delay)
  }

  function handleEvent(msg: WsEvent) {
    switch (msg.event) {
      case 'lineage_update': {
        const data = msg.data as Record<string, unknown>
        if (data.dataset_id) {
          store.addLineageNode({
            id: data.dataset_id as string,
            type: 'dataset',
            name: (data.filename as string) || (data.dataset_id as string),
            path: data.path as string,
          })
        }
        break
      }
      case 'decision_update': {
        const data = msg.data as Record<string, unknown>
        store.addDecision({
          id: (data.phase as string) || Date.now().toString(),
          what: (data.skill as string) || 'decision',
          why: (data.comment as string) || '',
          alternatives: [],
          timestamp: new Date().toISOString(),
        })
        break
      }
      case 'phase_transition': {
        const data = msg.data as Record<string, unknown>
        // Update skill sessions when phase changes
        break
      }
    }
  }

  function send(eventType: string, data: Record<string, unknown>) {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ event: eventType, data }))
    }
  }

  function disconnect() {
    destroyed = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (socket.value) {
      socket.value.onclose = null // prevent reconnect
      socket.value.close()
      socket.value = null
    }
    connected.value = false
    store.setWsConnected(false)
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    connected,
    reconnectAttempts,
    connect,
    disconnect,
    send,
  }
}
