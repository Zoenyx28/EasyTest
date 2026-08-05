import { ref } from 'vue'

export function useWebSocket() {
  const lastMessage = ref<any>(null)
  const connected = ref(false)
  let ws: WebSocket | null = null
  const handlers: Array<(msg: any) => void> = []

  function connect(runId: string) {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/ws/run/${runId}`)
    ws.onopen = () => { connected.value = true }
    ws.onclose = () => { connected.value = false }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        lastMessage.value = msg
        handlers.forEach(h => h(msg))
      } catch {}
    }
  }

  function onMessage(handler: (msg: any) => void) { handlers.push(handler) }
  function close() { ws?.close(); ws = null }

  return { lastMessage, connected, connect, onMessage, close }
}
