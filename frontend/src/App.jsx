import React, { useState, useEffect } from 'react'
import { connectLiveSocket, api } from './api.js'
import AdminPanel from './admin/AdminPanel.jsx'
import UserPanel from './user/UserPanel.jsx'

export default function App() {
  const [view, setView] = useState('admin')
  const [liveState, setLiveState] = useState(null)
  const [network, setNetwork] = useState(null)
  const [networkError, setNetworkError] = useState('')
  const [connected, setConnected] = useState(false)
  const [realTime, setRealTime] = useState(() => new Date())
  const [modelInfo, setModelInfo] = useState(null)

  useEffect(() => {
    let cancelled = false
    const loadNetwork = () => {
      api.getNetwork()
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
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setRealTime(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">
          <span className="brand-mark" />
          RailSync
        </div>
        <div className="view-toggle">
          <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>
            Controller View
          </button>
          <button className={view === 'user' ? 'active' : ''} onClick={() => setView('user')}>
            Passenger View
          </button>
        </div>
        <div className="sim-clock">
          {realTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          <span className="clock-label">LOCAL</span>
          {!connected && <span style={{ color: 'var(--signal-red)', marginLeft: 8 }}>● offline</span>}
        </div>
      </div>

      <div className="main-area">
        {view === 'admin' ? (
          <AdminPanel liveState={liveState} network={network} networkError={networkError} connected={connected} modelInfo={modelInfo} />
        ) : (
          <UserPanel liveState={liveState} network={network} networkError={networkError} connected={connected} />
        )}
      </div>
    </div>
  )
}
