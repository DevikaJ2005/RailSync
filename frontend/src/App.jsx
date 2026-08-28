import React, { useState, useEffect } from 'react'
import { connectLiveSocket, api } from './api.js'
import AdminPanel from './admin/AdminPanel.jsx'
import UserPanel from './user/UserPanel.jsx'

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

export default function App() {
  const [view, setView] = useState('admin')
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

  const systemClockTime = systemTime.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  const systemClockDate = `${WEEKDAYS[systemTime.getDay()]}, ${String(systemTime.getDate()).padStart(2, '0')} ${MONTHS[systemTime.getMonth()]} ${systemTime.getFullYear()}`

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
        <div className="system-clock">
          <div className="system-clock-head">
            <span className="clock-label">SYSTEM TIME</span>
            {!connected && <span className="offline-flag">● OFFLINE</span>}
          </div>
          <div className="system-clock-time">{systemClockTime}</div>
          <div className="system-clock-date">{systemClockDate}</div>
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
