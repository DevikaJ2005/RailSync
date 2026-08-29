import React, { useEffect, useState } from 'react'
import { connectLiveSocket, api } from './api.js'
import { loadSession, saveSession, clearSession } from './auth.js'
import logo from './assets/logo.png'
import AdminPanel from './admin/AdminPanel.jsx'
import UserPanel from './user/UserPanel.jsx'
import LoginScreen from './LoginScreen.jsx'

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

export default function App() {
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginError, setLoginError] = useState('')
  const [liveState, setLiveState] = useState(null)
  const [network, setNetwork] = useState(null)
  const [networkError, setNetworkError] = useState('')
  const [connected, setConnected] = useState(false)
  const [modelInfo, setModelInfo] = useState(null)
  const [systemTime, setSystemTime] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setSystemTime(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const session = loadSession()
    if (!session) {
      setAuthLoading(false)
      return
    }
    api
      .getMe()
      .then((payload) => setUser({ ...session.user, ...payload }))
      .catch(() => clearSession())
      .finally(() => setAuthLoading(false))
  }, [])

  useEffect(() => {
    const handleUnauthorized = () => setUser(null)
    window.addEventListener('railsync:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('railsync:unauthorized', handleUnauthorized)
  }, [])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    const loadNetwork = () => {
      api
        .getNetwork()
        .then((data) => {
          if (!cancelled) {
            setNetwork(data)
            setNetworkError('')
          }
        })
        .catch((error) => {
          if (!cancelled) setNetworkError(error.message)
        })
    }
    loadNetwork()
    api.getModelInfo().then(setModelInfo).catch(() => {})
    const retryTimer = window.setInterval(loadNetwork, 3000)
    const ws = connectLiveSocket(setLiveState, setConnected)
    return () => {
      cancelled = true
      window.clearInterval(retryTimer)
      ws.close()
    }
  }, [user])

  const handleLogin = async (username, password) => {
    setLoginError('')
    try {
      const { token, user: loggedInUser } = await api.login(username, password)
      saveSession(token, loggedInUser)
      setUser(loggedInUser)
    } catch (error) {
      setLoginError(error.message)
    }
  }

  const handleLogout = () => {
    clearSession()
    setUser(null)
    setLiveState(null)
    setNetwork(null)
  }

  if (authLoading) {
    return (
      <div className="login-screen">
        <div className="empty-state">Restoring session…</div>
      </div>
    )
  }

  if (!user) {
    return <LoginScreen onLogin={handleLogin} error={loginError} />
  }

  const systemClockTime = systemTime.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  const systemClockDate = `${WEEKDAYS[systemTime.getDay()]}, ${String(systemTime.getDate()).padStart(2, '0')} ${MONTHS[systemTime.getMonth()]} ${systemTime.getFullYear()}`

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">
          <img src={logo} alt="RailSync Logo" className="brand-logo" />
        </div>
        <div className="session-info">
          <span className={`role-pill role-${user.role}`}>{user.role}</span>
          <span className="session-name">{user.display_name || user.username}</span>
          <button className="btn btn-sm btn-logout" onClick={handleLogout}>
            Sign out
          </button>
        </div>
        <div className="system-clock">
          <div className="system-clock-head">
            {connected ? (
              <span className="online-flag"><span className="online-dot" />SYSTEM ONLINE</span>
            ) : (
              <span className="offline-flag">● OFFLINE</span>
            )}
            <span className="system-clock-time">◷ {systemClockTime}</span>
          </div>
          <div className="system-clock-date">{systemClockDate}</div>
        </div>
      </div>

      <div className="main-area">
        {user.role === 'controller' ? (
          <AdminPanel liveState={liveState} network={network} networkError={networkError} connected={connected} modelInfo={modelInfo} />
        ) : (
          <UserPanel liveState={liveState} network={network} networkError={networkError} connected={connected} />
        )}
      </div>
    </div>
  )
}