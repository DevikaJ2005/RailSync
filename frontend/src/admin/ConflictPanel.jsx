import React, { useState } from 'react'
import { api } from '../api.js'

function formatWaiting(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0))
  return total < 60 ? `${total} min` : `${Math.floor(total / 60)}h ${total % 60}m`
}

function fallbackReason(resolution) {
  const winner = resolution.decision_evidence?.winner
  const held = resolution.decision_evidence?.held_trains || []
  const winnerNo = resolution.winner_train || winner?.train_no
  const heldNos = resolution.held_trains?.length ? resolution.held_trains.join(', ') : ''
  const rule = resolution.decision_evidence?.selection_rule || resolution.decision_evidence?.reason_type
  const winnerWait = Number(winner?.minutes_waited || 0)
  const longestHeldWait = Math.max(...held.map((train) => Number(train.minutes_waited) || 0), 0)

  if (rule === 'starvation_safeguard' || winnerWait >= 15) {
    return `${winnerNo} has been waiting for an extended period, so RailSync gives it priority to prevent prolonged waiting.${heldNos ? ` ${heldNos} ${held.length === 1 ? 'is' : 'are'} recommended to wait.` : ''}`
  }
  if (winner && winnerWait > longestHeldWait && winnerWait > 0) {
    return `${winnerNo} has been waiting the longest, so RailSync recommends allowing it to continue first.${heldNos ? ` ${heldNos} ${held.length === 1 ? 'is' : 'are'} recommended to wait while the conflict is resolved.` : ''}`
  }
  if (winner?.train_type && held.some((h) => h.train_type && h.train_type !== winner.train_type)) {
    return `${winnerNo} is an ${winner.train_type} train and has higher operational priority in this conflict, so RailSync recommends allowing it to continue first.${heldNos ? ` ${heldNos} ${held.length === 1 ? 'is' : 'are'} recommended to wait while the conflicting movement is resolved.` : ''}`
  }
  if (resolution.reason && !resolution.reason.includes('configured operating policy')) {
    return resolution.reason
  }
  return `${winnerNo} has higher operational priority in this conflict, so RailSync recommends allowing it to continue first.${heldNos ? ` ${heldNos} ${held.length === 1 ? 'is' : 'are'} recommended to wait.` : ''}`
}

function resolveExplanation(resolution) {
  if (resolution.explanation && !resolution.explanation.includes('configured operating policy')) {
    return resolution.explanation
  }
  return fallbackReason(resolution)
}

function sectionRoute(section) {
  return String(section || '').replace(' <-> ', ' → ')
}

function statusLabel(train) {
  const status = train?.status || train?.operational_status
  if (!status) return null
  return {
    moving: 'Moving',
    checking: 'Approaching station',
    waiting: 'Waiting',
    held: 'Held',
    at_platform: 'At platform',
    completed: 'Completed',
  }[status] || status.replaceAll('_', ' ')
}

function round(val, places = 1) {
  return Number(val || 0).toFixed(places)
}

export default function ConflictPanel({ liveState, selectedConflictId, onSelectConflict, onActionComplete }) {
  const [updating, setUpdating] = useState(null)
  const [message, setMessage] = useState('')
  const [showProjected, setShowProjected] = useState(false)

  if (!liveState) return <div className="empty-state">Loading...</div>

  const resolutions = liveState.resolutions || []
  const activeResolutionCount = resolutions.filter((resolution) => resolution.conflict_status === 'active').length
  const projectedResolutionCount = resolutions.filter((resolution) => resolution.conflict_status === 'predicted').length
  const visibleResolutions = showProjected
    ? resolutions
    : resolutions.filter((resolution) => resolution.conflict_status === 'active')
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
          : 'Controller rejected the simulated rule-based recommendation.',
      )
      await onActionComplete?.()
      setMessage(approved ? 'Controller hold applied.' : 'Recommendation marked resolved.')
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
      await onActionComplete?.()
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

  const lifecycleLabel = (resolution) => {
    if (resolution.approval_status === 'approved') return 'APPROVED'
    if (resolution.approval_status === 'rejected') return 'RESOLVED'
    return 'RECOMMENDATION'
    if (resolution.approval_status === 'rejected') return 'REJECTED'
    return 'ACTION REQUIRED'
  }

  if (resolutions.length === 0 && manualHolds.length === 0) {
    return <div className="empty-state">No active simulated section conflicts right now.</div>
  }

  return (
    <div>
      <div className="scope-note">
        <strong>{activeResolutionCount} active conflict{activeResolutionCount === 1 ? '' : 's'}</strong> · {projectedResolutionCount} projected interaction{projectedResolutionCount === 1 ? '' : 's'}. Review recommended actions below, then approve or reject them.
      </div>
      {message && <div className="action-message">{message}</div>}
      {projectedResolutionCount > 0 && (
        <button className="projected-toggle" onClick={() => setShowProjected((visible) => !visible)}>
          {showProjected ? 'Hide projected interactions' : `Show ${projectedResolutionCount} projected interactions`}
        </button>
      )}
      {activeResolutionCount === 0 && !showProjected && (
        <div className="operations-clear" role="status">
          <div className="operations-clear-label">NO ACTIVE ACTIONS</div>
          <strong>Operations clear</strong>
          <p>No trains currently require a controller decision. Projected interactions remain available for review above.</p>
        </div>
      )}
      {resolutions.length === 0 && manualHolds.length > 0 && (
        <div className="empty-state">No active simulated section conflicts right now.</div>
      )}
      {visibleResolutions.map((resolution, index) => {
        const trainsInvolved = (
          resolution.trains_involved && resolution.trains_involved.length > 0
            ? resolution.trains_involved
            : Object.keys(resolution.train_predictions || {}).length > 0
              ? Object.keys(resolution.train_predictions)
              : [resolution.winner_train, ...resolution.held_trains]
        ).filter((trainNo, trainIndex, trainNumbers) => trainNo && trainNumbers.indexOf(trainNo) === trainIndex)
        const isSelected = selectedConflictId === (resolution.conflict_id || resolution.decision_id)

        return (
          <div
            key={resolution.decision_id || index}
            className={`decision-card severity-${resolution.severity}${isSelected ? ' is-selected-conflict' : ''}`}
            role="article"
            tabIndex={0}
            onClick={() => onSelectConflict?.(resolution.conflict_id || resolution.decision_id)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onSelectConflict?.(resolution.conflict_id || resolution.decision_id)
              }
            }}
          >
            {/* 1. Header: ACTION REQUIRED / Situation / Section */}
            <div className="decision-head">
              <div className="decision-title">
                <div className="action-required">ACTION REQUIRED</div>
                <strong className="decision-situation">
                  {resolution.conflict_status === 'predicted' ? 'Trains are scheduled to interact' : 'Trains are currently interacting'}
                </strong>
                <div className="decision-section-tag">
                  {sectionRoute(resolution.section)}
                </div>
              </div>
              <span className={`badge badge-${resolution.approval_status === 'approved' ? 'admin' : resolution.approval_status === 'rejected' ? 'danger' : 'simulation'}`}>
                {lifecycleLabel(resolution)}
              </span>
            </div>

            {/* 2. TRAINS INVOLVED */}
            <div className="involved-trains-block">
              <div className="involved-trains-heading">TRAINS INVOLVED</div>
              <div className="involved-trains-pills">
                {trainsInvolved.map((trainNo) => (
                  <span className="train-id-badge" key={`involved:${trainNo}`}>
                    {trainNo}
                  </span>
                ))}
              </div>
            </div>

            {/* 3. RECOMMENDED ACTION */}
            <div className="recommendation-block">
              <div className="recommendation-heading">RECOMMENDED ACTION</div>
              <div className="recommendation-action proceed">
                <span className="rec-action-type">ALLOW TO CONTINUE</span>
                <strong className="rec-action-train">{resolution.winner_train}</strong>
              </div>
              <div className="recommendation-action wait">
                <span className="rec-action-type">WAIT</span>
                <strong className="rec-action-train">{resolution.held_trains.join(', ')}</strong>
              </div>
            </div>

            {/* 4. WHY? */}
            <div className="reason-block">
              <div className="reason-label">WHY?</div>
              <div className="reason-text">{resolveExplanation(resolution)}</div>
            </div>

            {resolution.approval_status === 'approved' && (
              <div className="hold-lifecycle-note">
                ✓ Hold active. RailSync releases it automatically when {resolution.winner_train} clears this logical section or the conflict is no longer active.
              </div>
            )}

            {/* 5. ACTION BUTTONS: [ APPROVE ] [ REJECT RECOMMENDATION ] */}
            <div className="decision-actions">
              {resolution.approval_status === 'pending' && (
                <>
                  <button
                    className="btn btn-sm btn-approve"
                    disabled={updating === `decision:${resolution.decision_id}`}
                    onClick={(event) => { event.stopPropagation(); handleApproval(resolution.decision_id, true) }}
                  >
                    {updating === `decision:${resolution.decision_id}` ? 'Updating...' : 'APPROVE'}
                  </button>
                  <button
                    className="btn btn-sm btn-reject"
                    disabled={updating === `decision:${resolution.decision_id}`}
                    onClick={(event) => { event.stopPropagation(); handleApproval(resolution.decision_id, false) }}
                  >
                    REJECT RECOMMENDATION
                  </button>
                </>
              )}

              <details className="manual-controls">
                <summary>Other actions</summary>
                {resolution.approval_status === 'approved' && (
                  <button
                    className="btn btn-sm btn-danger"
                    disabled={updating === `decision:${resolution.decision_id}`}
                    onClick={(event) => { event.stopPropagation(); handleApproval(resolution.decision_id, false) }}
                  >
                    Cancel approved hold
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
                      onClick={(event) => { event.stopPropagation(); handleOverride(trainNo, action) }}
                    >
                      {updating === `override:${trainNo}:${action}`
                        ? 'Updating...'
                        : isManualHold
                          ? `Release manual hold: ${trainNo}`
                          : `Manual hold: ${trainNo}`}
                    </button>
                  )
                })}
              </details>
            </div>

            {/* 6. TECHNICAL DETAILS (Collapsed by default) */}
            <details className="priority-explanation">
              <summary>Why did RailSync recommend this? ▾</summary>
              <div className="technical-details-content">
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Train Type</span>
                  <span className="tech-detail-val">
                    {[resolution.winner_train, ...resolution.held_trains].map((tNo) => (
                      <span key={tNo} style={{ marginRight: 10 }}>
                        <strong>{tNo}</strong>: {trainsByNo[tNo]?.type || 'Standard'}
                      </span>
                    ))}
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Predicted Delay</span>
                  <span className="tech-detail-val">
                    {[resolution.winner_train, ...resolution.held_trains].map((tNo) => {
                      const delay = resolution.train_predictions?.[tNo]?.predicted_delay_min ?? trainsByNo[tNo]?.predicted_delay_min ?? 0
                      return (
                        <span key={tNo} style={{ marginRight: 10 }}>
                          <strong>{tNo}</strong>: {round(delay, 1)} min
                        </span>
                      )
                    })}
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Historical Support</span>
                  <span className="tech-detail-val">
                    {resolution.train_predictions?.[resolution.winner_train]?.prediction_context?.historical_pattern || 'Corridor pattern match'} · Confidence: {resolution.train_predictions?.[resolution.winner_train]?.prediction_context?.prediction_confidence || 'Standard'}
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Movement Direction</span>
                  <span className="tech-detail-val">
                    {(resolution.decision_evidence?.conflict?.direction_relation || resolution.direction_relation || 'same_direction').replace('_', ' ')}
                    {Object.entries(resolution.decision_evidence?.conflict?.train_movements || resolution.train_movements || {}).map(([tNo, m]) => (
                      <span key={tNo} style={{ marginLeft: 6 }}>
                        ({tNo}: {m.movement_from} → {m.movement_to})
                      </span>
                    ))}
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Projected Timing</span>
                  <span className="tech-detail-val">
                    {resolution.expected_overlap_minutes != null
                      ? `${resolution.expected_overlap_minutes} min overlap window`
                      : 'Active section contention'}
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Logical Section</span>
                  <span className="tech-detail-val">
                    {sectionRoute(resolution.section)} (Single logical movement authority)
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Operating Policy</span>
                  <span className="tech-detail-val">
                    {resolution.decision_evidence?.selection_rule === 'starvation_safeguard'
                      ? 'Starvation safeguard (wait threshold exceeded)'
                      : 'Class-first prioritization (Express > Passenger > Freight)'}
                  </span>
                </div>
                <div className="tech-detail-row">
                  <span className="tech-detail-label">Model Evidence</span>
                  <span className="tech-detail-val">
                    Pre-event section occupancy and platform pressure context
                  </span>
                </div>
              </div>
            </details>
          </div>
        )
      })}

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
