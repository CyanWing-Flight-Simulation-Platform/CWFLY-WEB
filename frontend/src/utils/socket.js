import { io } from 'socket.io-client'

let socket = null

// 登录凭证在 HttpOnly Cookie 中，同源 Socket.IO 握手会自动携带，无需 JS 读取 token。
export function getSocket() {
  if (!socket) {
    socket = io(window.location.origin, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionAttempts: Infinity
    })
  }
  return socket
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}
