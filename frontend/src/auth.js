const TOKEN_KEY = 'railsync_auth_token'
const USER_KEY = 'railsync_auth_user'

export function loadSession() {
  const token = localStorage.getItem(TOKEN_KEY)
  const rawUser = localStorage.getItem(USER_KEY)
  if (!token || !rawUser) return null
  try {
    return { token, user: JSON.parse(rawUser) }
  } catch {
    clearSession()
    return null
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export const SAMPLE_CREDENTIALS = [
  {
    role: 'controller',
    username: 'controller',
    password: 'admin@123',
    label: 'Station Controller',
    hint: 'Full control: map, conflicts, approvals, overrides, what-if, analytics',
  },
  {
    role: 'passenger',
    username: 'passenger',
    password: 'pass@123',
    label: 'Passenger',
    hint: 'Read-only: live map, platform board, train search',
  },
]