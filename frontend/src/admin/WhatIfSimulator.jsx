import React, { useState } from 'react'
import { api } from '../api.js'

export default function WhatIfSimulator({ liveState }) {
  const [trainNo, setTrainNo] = useState('')
  const [minutes, setMinutes] = useState(15)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const trains = liveState?.trains?.filter((t) => t.status !== 'completed') || []

  const run = async () => {
    if (!trainNo) return
    setLoading(true)
    try {
      const res = await api.whatIf(trainNo, Number(minutes))
      setResult(res)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel-title">What-If Simulator</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <select
          value={trainNo}
          onChange={(e) => setTrainNo(e.target.value)}
          style={{ background: 'var(--bg-panel)', border: '1px solid var(--line-steel)', color: 'var(--text-primary)', borderRadius: 6, padding: '6px 8px', fontSize: 12.5 }}
        >
          <option value="">Select train…</option>
          {trains.map((t) => <option key={t.train_no} value={t.train_no}>{t.train_no} — {t.name}</option>)}
        </select>
        <input
          type="number"
          value={minutes}
          onChange={(e) => setMinutes(e.target.value)}
          style={{ width: 64, background: 'var(--bg-panel)', border: '1px solid var(--line-steel)', color: 'var(--text-primary)', borderRadius: 6, padding: '6px 8px', fontSize: 12.5 }}
        />
        <span style={{ fontSize: 12, color: 'var(--text-muted)', alignSelf: 'center' }}>extra min</span>
        <button className="btn btn-primary" onClick={run} disabled={!trainNo || loading}>
          {loading ? 'Running…' : 'Simulate'}
        </button>
      </div>

      {result && (
        <div style={{ fontSize: 12.5 }}>
          <div style={{ marginBottom: 8 }}>
            Projected total network delay:{' '}
            <span className="split-flap-cell">{result.total_projected_network_delay} min</span>
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            Projected conflicts: {result.projected_conflicts.length}
          </div>
          {result.projected_resolutions.map((r, i) => (
            <div key={i} className="reason-text" style={{ marginTop: 6 }}>• {r.reason}</div>
          ))}
        </div>
      )}
    </div>
  )
}
