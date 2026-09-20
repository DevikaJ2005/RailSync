const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000'
const TOKEN_KEY = 'railsync_auth_token'

function authHeaders() {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function connectLiveSocket(onMessage, onStatusChange) {
  let socket
  let reconnectTimer
  let closed = false

  const connect = () => {
    if (closed) return
    socket = new WebSocket(`${WS_BASE}/ws/live`)
    socket.onopen = () => onStatusChange?.(true)
    socket.onclose = () => {
      onStatusChange?.(false)
      if (!closed) reconnectTimer = window.setTimeout(connect, 2000)
    }
    socket.onerror = () => socket.close()
    socket.onmessage = (event) => onMessage(JSON.parse(event.data))
  }

  connect()
  return {
    close: () => {
      closed = true
      window.clearTimeout(reconnectTimer)
      socket?.close()
    },
  }
}

async function req(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(options.headers || {}) },
    ...options,
  })
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('railsync_auth_user')
    window.dispatchEvent(new Event('railsync:unauthorized'))
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status}) for ${path}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch { /* non-JSON error body */ }
    const error = new Error(detail)
    error.status = res.status
    throw error
  }
  return res.json()
}

export const api = {
  login: (username, password) =>
    req('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => req('/api/auth/me'),
  getNetwork: () => req('/api/network'),
  getState: () => req('/api/state'),
  getAnalytics: () => req('/api/analytics'),
  getLogs: (trainNo) => req(`/api/logs${trainNo ? `?train_no=${trainNo}` : ''}`),
  explainLog: (entry) => req('/api/logs/explain', {
    method: 'POST',
    body: JSON.stringify(entry),
  }),
  getModelInfo: () => req('/api/model-info'),
  getModelStatus: () => req('/api/model-status'),
  whatIf: (trainNo, extraMinutes) =>
    req('/api/whatif', {
      method: 'POST',
      body: JSON.stringify({ train_no: trainNo, extra_delay_minutes: extraMinutes }),
    }),
  override: (trainNo, action, adminNote = '') =>
    req('/api/override', {
      method: 'POST',
      body: JSON.stringify({ train_no: trainNo, action, admin_note: adminNote }),
    }),
  approveDecision: (decisionId, approved = true, controllerNote = '') =>
    req('/api/decisions/approve', {
      method: 'POST',
      body: JSON.stringify({ decision_id: decisionId, approved, controller_note: controllerNote }),
    }),
  pauseSimulation: () => req('/api/simulation/pause', { method: 'POST' }),
  resumeSimulation: () => req('/api/simulation/resume', { method: 'POST' }),
  resetSimulation: () => req('/api/simulation/reset', { method: 'POST' }),
  setSpeed: (multiplier) =>
    req('/api/simulation/speed', {
      method: 'POST',
      body: JSON.stringify({ multiplier }),
    }),
}
