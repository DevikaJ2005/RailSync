import React, { useEffect, useState } from 'react'
import { connectLiveSocket, api } from './api.js'
import { loadSession, saveSession, clearSession } from './auth.js'
import logo from './assets/logo.png'
import AdminPanel from './admin/AdminPanel.jsx'
import UserPanel from './user/UserPanel.jsx'
import LoginScreen from './LoginScreen.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginError, setLoginError] = useState('')
  const [liveState, setLiveState] = useState(null)
  const [network, setNetwork] = useState(null)
  const [networkError, setNetworkError] = useState('')
  const [connected, setConnected] = useState(false)
  const [modelInfo, setModelInfo] = useState(null)
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
    let retryTimer = null
    const loadNetwork = () => {
      api
        .getNetwork()
        .then((data) => {
          if (!cancelled) {
            setNetwork(data)
            setNetworkError('')
            if (retryTimer) {
              window.clearInterval(retryTimer)
              retryTimer = null
            }
          }
        })
        .catch((error) => {
          if (!cancelled) setNetworkError(error.message)
        })
    }
    loadNetwork()
    api.getModelInfo().then(setModelInfo).catch(() => {})
    retryTimer = window.setInterval(loadNetwork, 3000)
    const ws = connectLiveSocket(setLiveState, setConnected)
    return () => {
      cancelled = true
      if (retryTimer) window.clearInterval(retryTimer)
      ws.close()
    }
  }, [user])

  const refreshLiveState = () => api.getState().then(setLiveState).catch(() => {})

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

  const simulationClockTime = liveState?.sim_time
    ? liveState.sim_time.slice(11, 16)
    : '--:--'
  const simulationClockDate = liveState?.sim_time
    ? new Date(liveState.sim_time.replace(' ', 'T')).toLocaleDateString('en-GB', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).toUpperCase()
    : 'SIMULATION STARTING'

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
          <div className="simulation-clock">
            <span className="clock-label">SIMULATION TIME</span>
            <span className="simulation-clock-time">{simulationClockTime}</span>
          </div>
          <div className="system-clock-date">{simulationClockDate}</div>
        </div>
      </div>

      <div className="main-area">
        {user.role === 'controller' ? (
          <AdminPanel liveState={liveState} network={network} networkError={networkError} connected={connected} modelInfo={modelInfo} onActionComplete={refreshLiveState} />
        ) : (
          <UserPanel liveState={liveState} network={network} networkError={networkError} connected={connected} />
        )}
      </div>
    </div>
  )
}