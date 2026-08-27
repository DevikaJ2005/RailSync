import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function AnalyticsDashboard({ modelInfo }) {
  const [analytics, setAnalytics] = useState(null)

  useEffect(() => {
    const load = () => api.getAnalytics().then(setAnalytics).catch(() => {})
    load()
    const interval = setInterval(load, 4000)
    return () => clearInterval(interval)
  }, [])

  if (!analytics) return <div className="empty-state">Loading analyticsâ€¦</div>

  const stat = (label, value, color) => (
    <div className="panel" style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 21, fontWeight: 700, color: color || 'var(--text-primary)' }}>
        {value}
      </div>
      <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
    </div>
  )

  const testBaseline = modelInfo?.metrics?.test_baseline_metrics

  return (
    <div>
      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-title">Delay Model Evaluation</div>
        <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.45, marginBottom: 10 }}>
          {modelInfo?.scope?.prediction || 'Synthetic per-section delay prediction.'}
        </div>
        {modelInfo?.metrics?.mae_min != null ? (
          <div style={{ display: 'flex', gap: 10 }}>
            {stat('Test MAE', `${modelInfo.metrics.mae_min} min`, 'var(--signal-green)')}
            {stat('Test RMSE', `${modelInfo.metrics.rmse_min} min`, 'var(--signal-amber)')}
            {stat('Test RÂ²', modelInfo.metrics.r2, 'var(--rail-blue)')}
          </div>
        ) : (
          <div className="empty-state">Evaluation metrics unavailable</div>
        )}
        {modelInfo?.metrics?.splits?.test && (
          <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 10 }}>
            Chronological holdout: {modelInfo.metrics.splits.test.rows.toLocaleString()} unseen synthetic section records
            {testBaseline?.mae_min != null && ` | Mean baseline MAE: ${testBaseline.mae_min} min`}
          </div>
        )}
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-title">Simulation Operations</div>
        <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
          {stat('Conflict Onsets', analytics.conflicts_detected)}
          {stat('Active Conflicts', analytics.active_conflicts, 'var(--signal-amber)')}
        </div>
        <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
          {stat('Controller Holds Applied', analytics.controller_resolutions_applied, 'var(--signal-green)')}
          {stat('Safety Interventions', analytics.forced_releases + analytics.deadlocks_broken, 'var(--signal-red)')}
        </div>
        {stat('Active Predicted Delay', `${analytics.active_predicted_delay_min} min`, 'var(--rail-blue)')}
      </div>

      <div className="panel" style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.5 }}>
        <strong style={{ color: 'var(--text-secondary)' }}>Scope note:</strong> delay is the model output. Section and platform conflicts are detected and resolved by explainable simulation rules; these operational counters are not an “AI versus no-AI” experiment.
      </div>
    </div>
  )
}
