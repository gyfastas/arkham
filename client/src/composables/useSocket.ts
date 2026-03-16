import { inject } from 'vue'
import type { SocketClient } from '../network/SocketClient'

const SOCKET_KEY = Symbol('socket')

export function provideSocket(client: SocketClient) {
  return { key: SOCKET_KEY, value: client }
}

export function useSocket(): SocketClient {
  const client = inject<SocketClient>(SOCKET_KEY)
  if (!client) throw new Error('SocketClient not provided')
  return client
}

export { SOCKET_KEY }
