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
          className="field-input"
          value={trainNo}
          onChange={(e) => setTrainNo(e.target.value)}
        >
          <option value="">Select train…</option>
          {trains.map((t) => <option key={t.train_no} value={t.train_no}>{t.train_no} — {t.name}</option>)}
        </select>
        <input
          type="number"
          className="field-input"
          style={{ width: 64 }}
          value={minutes}
          onChange={(e) => setMinutes(e.target.value)}
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
            <div key={i} className="reason-text" style={{ marginTop: 6 }}>• {r.explanation || r.reason}</div>
          ))}
        </div>
      )}
    </div>
  )
}
