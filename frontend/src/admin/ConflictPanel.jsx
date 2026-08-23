import React, { useState } from 'react'
import { api } from '../api.js'

export default function ConflictPanel({ liveState }) {
  const [updating, setUpdating] = useState(null)

  if (!liveState) return <div className="empty-state">Loading...</div>

  const resolutions = liveState.resolutions || []

  const handleApproval = async (decisionId, approved) => {
    setUpdating(decisionId)
    try {
      await api.approveDecision(decisionId, approved, approved
        ? 'Controller approved the ML recommendation and applied movement authority.'
        : 'Controller rejected or released this ML recommendation.')
    } finally {
      setUpdating(null)
    }
  }

  if (resolutions.length === 0) {
    return <div className="empty-state">No active conflicts right now - network running clear.</div>
  }

  return (
    <div>
      {resolutions.map((r, i) => (
        <div key={i} className={`decision-card severity-${r.severity}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <strong style={{ fontSize: 13 }}>{r.section}</strong>
            <span className={`badge badge-${r.approval_status === 'approved' ? 'admin' : r.approval_status === 'rejected' ? 'danger' : r.resolved_by}`}>
              {r.approval_status === 'approved' ? 'hold applied' : r.approval_status === 'rejected' ? 'released' : 'awaiting approval'}
            </span>
          </div>

          <div style={{ marginTop: 6, fontSize: 12.5 }}>
            <span style={{ color: 'var(--signal-green)' }}>{r.winner_train} proceeds</span>
            {' / '}
            <span style={{ color: 'var(--signal-amber)' }}>{r.held_trains.join(', ')} held</span>
          </div>

          <div className="impact-grid">
            <div>
              <span>Risk</span>
              <strong>{r.severity}</strong>
            </div>
            <div>
              <span>Trains</span>
              <strong>{r.affected_trains}</strong>
            </div>
            <div>
              <span>Max delay</span>
              <strong>{r.max_predicted_delay} min</strong>
            </div>
            <div>
              <span>Hold est.</span>
              <strong>{r.estimated_hold_minutes} min</strong>
            </div>
          </div>

          <div className="reason-text">{r.reason}</div>
          <div className="priority-explanation">
            <strong>Movement authority:</strong> approving this recommendation holds {r.held_trains.join(', ')}
            {' '}until {r.winner_train} clears the section. Releasing it removes the controller hold.
          </div>

          {r.approval_status === 'pending' && (
            <button
              className="btn btn-sm"
              style={{ marginTop: 8, marginRight: 6 }}
              disabled={updating === r.decision_id}
              onClick={() => handleApproval(r.decision_id, true)}
            >
              {updating === r.decision_id ? 'Updating...' : 'Approve and apply hold'}
            </button>
          )}
          {r.approval_status !== 'rejected' && (
            <button
              className="btn btn-sm btn-danger"
              style={{ marginTop: 8 }}
              disabled={updating === r.decision_id}
              onClick={() => handleApproval(r.decision_id, false)}
            >
              {r.approval_status === 'approved' ? 'Release hold' : 'Reject'}
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
