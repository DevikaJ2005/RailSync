import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function DecisionLog() {
  const [logs, setLogs] = useState([])
  const [filter, setFilter] = useState('')

  useEffect(() => {
    const load = () => api.getLogs(filter || undefined).then(setLogs).catch(() => {})
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [filter])

  return (
    <div>
      <input
        className="filter-input"
        placeholder="Search by train number…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {logs.length === 0 && <div className="empty-state">No decisions logged yet.</div>}
      {logs.map((log, i) => (
        <div key={i} className="decision-card" style={{ borderLeftColor: 'var(--line-steel-bright)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)' }}>
            <span className="split-flap" style={{ padding: '1px 6px' }}>{log.sim_timestamp}</span>
            <span className={`badge badge-${log.resolved_by}`}>{log.resolved_by}</span>
          </div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
            {log.trains_involved?.join(', ')} · {log.conflict_type}
          </div>
          <div className="reason-text">{log.reason}</div>
        </div>
      ))}
    </div>
  )
}
