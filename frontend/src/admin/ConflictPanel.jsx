import React, { useState } from 'react'
import { api } from '../api.js'

export default function ConflictPanel({ liveState }) {
  const [updating, setUpdating] = useState(null)
  const [message, setMessage] = useState('')

  if (!liveState) return <div className="empty-state">Loading...</div>

  const resolutions = liveState.resolutions || []
  const trainsByNo = Object.fromEntries((liveState.trains || []).map((train) => [train.train_no, train]))
  const controllerHolds = liveState.controller_holds || {}

  const handleApproval = async (decisionId, approved) => {
    setUpdating(`decision:${decisionId}`)
    setMessage('')
    try {
      await api.approveDecision(
        decisionId,
        approved,
        approved
          ? 'Controller approved the simulated rule-based recommendation and applied a hold.'
          : 'Controller rejected or released the simulated rule-based recommendation.',
      )
      setMessage(approved ? 'Controller hold applied.' : 'Recommendation released.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setUpdating(null)
    }
  }

  const handleOverride = async (trainNo, action) => {
    setUpdating(`override:${trainNo}:${action}`)
    setMessage('')
    try {
      const result = await api.override(trainNo, action, `Controller override: ${action}`)
      setMessage(result.success ? `Override applied to ${trainNo}.` : result.error || 'Override could not be applied.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setUpdating(null)
    }
  }

  const manualHolds = Object.entries(controllerHolds)
    .filter(([_, hold]) => hold.manual)
    .map(([trainNo]) => trainNo)

  if (resolutions.length === 0 && manualHolds.length === 0) {
    return <div className="empty-state">No active simulated section conflicts right now.</div>
  }

  return (
    <div>
      <div className="scope-note">
        Delay values are model predictions. Conflict detection and recommendations use simulated operational rules; the controller remains in control.
      </div>
      {message && <div className="action-message">{message}</div>}
      {resolutions.length === 0 && manualHolds.length > 0 && (
        <div className="empty-state">No active simulated section conflicts right now.</div>
      )}
      {resolutions.map((resolution, index) => (
        <div key={resolution.decision_id || index} className={`decision-card severity-${resolution.severity}`}>
          <div className="decision-head">
            <div className="decision-title">
              <span className={`decision-severity severity-${resolution.severity}`}>
                <span className="severity-dot" />{String(resolution.severity).toUpperCase()} CONFLICT
              </span>
              <strong className="decision-section">{resolution.section}</strong>
            </div>
            <span className={`badge badge-${resolution.approval_status === 'approved' ? 'admin' : resolution.approval_status === 'rejected' ? 'danger' : 'simulation'}`}>
              {resolution.approval_status === 'approved' ? 'hold applied' : resolution.approval_status === 'rejected' ? 'released' : 'simulation rule'}
            </span>
          </div>

          <div style={{ marginTop: 6, fontSize: 12.5 }}>
            <span style={{ color: 'var(--signal-green)' }}>{resolution.winner_train} proceeds</span>
            {' / '}
            <span style={{ color: 'var(--signal-amber)' }}>{resolution.held_trains.join(', ')} held</span>
          </div>

          <div className="impact-grid">
            <div>
              <span>Risk</span>
              <strong>{resolution.severity}</strong>
            </div>
            <div>
              <span>Trains</span>
              <strong>{resolution.affected_trains}</strong>
            </div>
            <div>
              <span>Model delay</span>
              <strong>{resolution.max_predicted_delay} min</strong>
            </div>
            <div>
              <span>Hold est.</span>
              <strong>{resolution.estimated_hold_minutes} min</strong>
            </div>
          </div>

          <div className="reason-text">{resolution.reason}</div>
<div className="priority-explanation">
  <strong>Why this choice:</strong> express trains and more-delayed trains go first. Approving applies a simulated hold — the waiting train stops until the chosen train has passed.
</div>

          <div className="decision-actions">
            {resolution.approval_status === 'pending' && (
              <button
                className="btn btn-sm btn-success"
                disabled={updating === `decision:${resolution.decision_id}`}
                onClick={() => handleApproval(resolution.decision_id, true)}
              >
                {updating === `decision:${resolution.decision_id}` ? 'Updating...' : 'Approve & Apply Hold'}
              </button>
            )}
            {resolution.approval_status !== 'rejected' && (
              <button
                className="btn btn-sm btn-danger"
                disabled={updating === `decision:${resolution.decision_id}`}
                onClick={() => handleApproval(resolution.decision_id, false)}
              >
                {resolution.approval_status === 'approved' ? 'Release hold' : 'Reject'}
              </button>
            )}

            {resolution.held_trains.map((trainNo) => {
              const train = trainsByNo[trainNo]
              const isManualHold = Boolean(controllerHolds[trainNo]?.manual)
              const canApplyManualHold = ['moving', 'checking'].includes(train?.status)
              if (!isManualHold && !canApplyManualHold) return null
              const action = isManualHold ? 'release_manual_hold' : 'hold_train'
              return (
                <button
                  key={`${trainNo}:${action}`}
                  className="btn btn-sm"
                  disabled={updating === `override:${trainNo}:${action}`}
                  onClick={() => handleOverride(trainNo, action)}
                >
                  {updating === `override:${trainNo}:${action}`
                    ? 'Updating...'
                    : isManualHold
                      ? `Release manual hold: ${trainNo}`
                      : `Manual hold: ${trainNo}`}
                </button>
              )
            })}
          </div>
        </div>
      ))}

      {manualHolds.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div className="panel-title" style={{ marginBottom: 10 }}>Active Manual Holds</div>
          {manualHolds.map((trainNo) => (
            <div key={trainNo} className="decision-card severity-minor" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 15px' }}>
              <div><strong>{trainNo}</strong> is manually held</div>
              <button
                className="btn btn-sm"
                disabled={updating === `override:${trainNo}:release_manual_hold`}
                onClick={() => handleOverride(trainNo, 'release_manual_hold')}
              >
                {updating === `override:${trainNo}:release_manual_hold`
                  ? 'Updating...'
                  : `Release manual hold`}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
