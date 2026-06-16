import { ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import type { ChatMessage, CodeBlockData, GatePrompt } from '@/types'

const API_BASE = '/api'

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 9)
}

export function useChat() {
  const store = useSessionStore()
  const inputText = ref('')
  const abortController = ref<AbortController | null>(null)

  function parseSkillCommand(text: string): { skill: string; target: string; message: string } | null {
    const match = text.trim().match(/^\/skill\s+(\S+)(?:\s+(.+))?/)
    if (!match) return null
    return {
      skill: match[1],
      target: match[2] || '',
      message: text.trim(),
    }
  }

  async function sendMessage(text: string): Promise<void> {
    if (!text.trim() || store.isStreaming) return

    // Add user message
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
      timestamp: Date.now(),
    }
    store.addMessage(userMsg)

    // Check for skill command
    const skillCmd = parseSkillCommand(text)

    // Create AI message placeholder
    const aiMsg: ChatMessage = {
      id: generateId(),
      role: 'ai',
      content: '',
      timestamp: Date.now(),
    }
    if (skillCmd) {
      aiMsg.skill_name = skillCmd.skill
    }
    store.addMessage(aiMsg)
    store.isStreaming = true

    // Abort any previous stream
    abortController.value?.abort()
    abortController.value = new AbortController()

    try {
      const params = new URLSearchParams()
      params.set('message', text.trim())
      if (skillCmd) {
        params.set('skill', skillCmd.skill)
        if (skillCmd.target) params.set('target', skillCmd.target)
      }

      const response = await fetch(`${API_BASE}/chat/stream?${params.toString()}`, {
        signal: abortController.value.signal,
      })

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.event === 'token' || data.content) {
                const content = typeof data.content === 'string' ? data.content : (data.data ? JSON.parse(data.data).content : '')
                if (content) {
                  store.appendToLastMessage(content)
                }
              } else if (data.event === 'error') {
                const errData = typeof data.data === 'string' ? JSON.parse(data.data) : data
                store.appendToLastMessage(`\n\n[Error: ${errData.error || 'unknown error'}]`)
              }
            } catch {
              // Skip lines that aren't valid JSON
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        store.appendToLastMessage(`\n\n[Error: ${err.message}]`)
      }
    } finally {
      store.isStreaming = false
      abortController.value = null
    }
  }

  async function approveGate(
    sessionDir: string,
    phaseId: string,
    approved: boolean,
    comment: string = ''
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/skill/gate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_dir: sessionDir,
        decision: {
          approved,
          phase_id: phaseId,
          comment,
        },
      }),
    })

    const result = await response.json()

    // Add system message about the decision
    const sysMsg: ChatMessage = {
      id: generateId(),
      role: 'system',
      content: approved
        ? `Gate approved. Continuing to phase: ${result.phase || 'next'}`
        : `Gate rejected. ${result.error || 'Rolling back.'}`,
      timestamp: Date.now(),
    }
    store.addMessage(sysMsg)

    return result
  }

  function stopStreaming() {
    abortController.value?.abort()
    store.isStreaming = false
  }

  function setInputText(text: string) {
    inputText.value = text
  }

  return {
    inputText,
    sendMessage,
    approveGate,
    stopStreaming,
    setInputText,
    parseSkillCommand,
  }
}
