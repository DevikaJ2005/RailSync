import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../api.js'

export default function AnalyticsDashboard() {
  const [analytics, setAnalytics] = useState(null)

  useEffect(() => {
    const load = () => api.getAnalytics().then(setAnalytics).catch(() => {})
    load()
    const interval = setInterval(load, 4000)
    return () => clearInterval(interval)
  }, [])

  if (!analytics) return <div className="empty-state">Loading analytics…</div>

  const chartData = [
    { name: 'Without AI', delay: analytics.total_delay_without_ai },
    { name: 'With AI', delay: analytics.total_delay_with_ai },
  ]

  const stat = (label, value, color) => (
    <div className="panel" style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700, color: color || 'var(--text-primary)' }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
    </div>
  )

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        {stat('Conflicts Detected', analytics.conflicts_detected)}
        {stat('Conflicts Resolved', analytics.conflicts_resolved, 'var(--signal-green)')}
      </div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        {stat('Deadlocks Broken', analytics.deadlocks_broken, 'var(--signal-amber)')}
        {stat('Forced Releases', analytics.forced_releases, 'var(--signal-red)')}
      </div>

      <div className="panel">
        <div className="panel-title">Total Delay — With vs Without AI</div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData}>
            <CartesianGrid stroke="#232B38" vertical={false} />
            <XAxis dataKey="name" stroke="#6B7787" fontSize={11} />
            <YAxis stroke="#6B7787" fontSize={11} />
            <Tooltip contentStyle={{ background: '#161C26', border: '1px solid #232B38', fontSize: 12 }} />
            <Bar dataKey="delay" fill="#4F8FE8" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
