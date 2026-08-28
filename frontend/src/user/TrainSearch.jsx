import React, { useState } from 'react'

export default function TrainSearch({ liveState }) {
  const [query, setQuery] = useState('')

  const trains = (liveState?.trains || []).filter((t) => t.status !== 'completed')
  const filtered = query
    ? trains.filter((t) => t.train_no.toLowerCase().includes(query.toLowerCase()) || t.name.toLowerCase().includes(query.toLowerCase()))
    : trains

  return (
    <div className="panel">
      <div className="panel-title">Find Your Train</div>
      <input
        className="filter-input"
        placeholder="Search by train number or name…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {filtered.length === 0 && <div className="empty-state">No matching trains.</div>}
      {filtered.map((t) => (
        <div key={t.train_no} className="board-row" style={{ gridTemplateColumns: '1fr 1fr 90px' }}>
          <span>{t.train_no} — {t.name}</span>
          <span style={{ color: 'var(--text-muted)' }}>{t.from} → {t.to}</span>
          <span className={`status-chip status-${t.status}`}>
            <span className="dot" />{t.status.replace('_', ' ')}
          </span>
        </div>
      ))}
    </div>
  )
}
