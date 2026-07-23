import { ref, onUnmounted } from 'vue'

export interface ProgressEvent {
  event: 'progress' | 'log' | 'complete' | 'error'
  stage?: string
  current?: number
  total?: number | null
  message?: string
  output?: any
}

export function useWs() {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let taskId: string | null = null
  let onMessage: ((e: ProgressEvent) => void) | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect(id: string, handler: (e: ProgressEvent) => void) {
    disconnect()
    taskId = id
    onMessage = handler
    _connect()
  }

  function _connect() {
    if (!taskId) return
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${location.host}/api/ws/${taskId}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ProgressEvent
        if (onMessage) onMessage(data)
        if (data.event === 'complete' || data.event === 'error') {
          setTimeout(() => disconnect(), 500)
        }
      } catch { console.warn('useWs: failed to parse message', event.data) }
    }

    ws.onclose = () => {
      connected.value = false
    }

    ws.onerror = () => {
      connected.value = false
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    connected.value = false
    taskId = null
    onMessage = null
  }

  onUnmounted(() => disconnect())

  return { connected, connect, disconnect }
}
