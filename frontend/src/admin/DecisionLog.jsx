import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

function removeExactDuplicates(entries) {
  const seen = new Set()
  return entries.filter((entry) => {
    const fingerprint = JSON.stringify([
      entry.sim_timestamp,
      entry.conflict_type,
      entry.trains_involved || [],
      entry.action_taken,
      entry.reason,
      entry.resolved_by,
    ])
    if (seen.has(fingerprint)) return false
    seen.add(fingerprint)
    return true
  })
}

function logPresentation(log, explanationOverride = '') {
  const action = String(log.action_taken || '').toLowerCase()
  const trains = log.trains_involved?.join(', ')
  const context = log.decision_context || {}
  const trustedExplanation = explanationOverride || context.explanation
  const isApproved = action.includes('approved')
  const isRejected = action.includes('rejected')

  if (trustedExplanation) {
    const title = isApproved
      ? (context.hold_trains?.length > 0 ? 'HOLD APPROVED' : 'RECOMMENDATION APPROVED')
      : isRejected
      ? (context.hold_trains?.length > 0 ? 'HOLD REJECTED' : 'RECOMMENDATION REJECTED')
      : (action === 'held' || context.reason_type === 'platform_unavailable' || context.event_type === 'PLATFORM_UNAVAILABLE')
      ? 'PLATFORM UNAVAILABLE'
      : (action === 'hold_train' || context.event_type === 'HOLD' || context.event_type === 'TRAIN_WAITING')
      ? 'TRAIN WAITING'
      : (action === 'release_manual_hold' || action === 'resume' || context.event_type === 'RESUME' || context.event_type === 'TRAIN_RESUMED')
      ? 'TRAIN RESUMED'
      : 'OPERATIONAL EVENT'
    return {
      title,
      detail: trustedExplanation,
    }
  }

  const selected = context.selected_train
  const held = context.hold_trains || []
  const heldStr = held.join(', ')
  const reasonText = (context.reason_text || log.reason || '').replace(/\.$/, '')
  const reasonClause = reasonText ? ` because ${reasonText}` : ''

  if (isApproved) {
    let detail = selected
      ? `${selected} was recommended to continue${reasonClause}.`
      : 'The controller approved the recommended traffic priority.'
    if (held.length > 0) {
      detail += ` ${heldStr} ${held.length === 1 ? 'was' : 'were'} recommended to wait because ${held.length === 1 ? 'its movement' : 'their movements'} conflicted with ${selected || 'the continuing train'}.`
    }
    detail += ' The controller approved the recommendation and the hold was applied.'
    return { title: held.length > 0 ? 'HOLD APPROVED' : 'RECOMMENDATION APPROVED', detail }
  }

  if (isRejected) {
    let detail = selected
      ? `${selected} was recommended to continue.`
      : 'The recommendation was reviewed.'
    if (held.length > 0) {
      detail += ` ${heldStr} ${held.length === 1 ? 'was' : 'were'} recommended to wait.`
    }
    detail += ' The controller rejected the recommendation, so no hold was applied by this recommendation.'
    return { title: held.length > 0 ? 'HOLD REJECTED' : 'RECOMMENDATION REJECTED', detail }
  }

  if (action === 'held' || context.reason_type === 'platform_unavailable' || context.event_type === 'PLATFORM_UNAVAILABLE') {
    const station = context.station || (log.reason?.includes(' at ') ? log.reason.split(' at ')[1].replace(/\.$/, '') : null)
    const trainName = trains || context.train_no || 'The train'
    const detail = station
      ? `${trainName} was held because no platform was available at ${station}. The train will remain waiting until a platform becomes available.`
      : `${trainName} was held awaiting an available platform.`
    return { title: 'PLATFORM UNAVAILABLE', detail }
  }

  if (action === 'what_if' || action === 'simulated_delay') return { title: 'WHAT-IF RESULT', detail: log.reason }
  if (action === 'resume' && log.conflict_type === 'simulation_control') return { title: 'SIMULATION RESUMED', detail: 'The simulation clock is running again.' }
  if (action === 'pause') return { title: 'SIMULATION PAUSED', detail: 'The simulation clock is paused.' }
  if (action === 'reset') return { title: 'SIMULATION RESET', detail: 'The simulation was returned to its starting timetable.' }
  if (action === 'set_speed') return { title: 'SIMULATION SPEED CHANGED', detail: log.reason }
  if (action === 'resume' || action === 'release_manual_hold' || context.event_type === 'TRAIN_RESUMED') return { title: 'TRAIN RESUMED', detail: log.reason || `${trains || 'The train'} has resumed movement following clearance.` }
  if (action === 'force_proceed') return { title: 'TRAIN ALLOWED TO CONTINUE', detail: `${trains || 'The train'} was allowed to continue by controller override.` }
  if (action === 'hold_train' || context.event_type === 'TRAIN_WAITING') return { title: 'TRAIN WAITING', detail: log.reason || `${trains || 'The train'} was held by controller instruction.` }
  return { title: 'OPERATIONAL EVENT', detail: log.reason || 'A simulation event was recorded.' }
}

function sourceLabel(source) {
  return source === 'controller' ? 'Controller' : 'Automatic'
}

function formatLogTime(value) {
  const parts = String(value || '').split(' ')
  if (parts.length < 2) return value || 'Unknown simulation time'
  return `${parts[0]} · ${parts[1].slice(0, 5)}`
}

export default function DecisionLog() {
  const [logs, setLogs] = useState([])
  const [filter, setFilter] = useState('')
  const [explaining, setExplaining] = useState(null)
  const [explanations, setExplanations] = useState({})

  useEffect(() => {
    const load = () => api.getLogs(filter || undefined).then((entries) => setLogs(removeExactDuplicates(entries))).catch(() => {})
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [filter])

  const explainLog = async (log, index) => {
    setExplaining(index)
    try {
      const result = await api.explainLog({
        sim_timestamp: log.sim_timestamp,
        conflict_type: log.conflict_type,
        trains_involved: log.trains_involved || [],
        action_taken: log.action_taken,
        reason: log.reason,
        resolved_by: log.resolved_by,
        decision_context: log.decision_context || {},
      })
      setExplanations((current) => ({ ...current, [index]: result.explanation }))
    } catch {
      setExplanations((current) => ({ ...current, [index]: log.reason || 'No further explanation is available.' }))
    } finally {
      setExplaining(null)
    }
  }

  return (
    <div>
      <div className="scope-note">
        <strong>What happened</strong>
        <div className="operations-summary-note">Plain-language history of controller actions and automatic train events.</div>
      </div>
      <input
        className="filter-input"
        placeholder="Find a train in the log..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {logs.length > 0 && <div className="log-count">Showing {logs.length} recent event{logs.length === 1 ? '' : 's'}</div>}
      {logs.length === 0 && <div className="empty-state">No decisions logged yet.</div>}
      {logs.map((log, i) => (
        <div key={i} className="decision-card log-card" style={{ borderLeftColor: 'var(--line-steel-bright)' }}>
          {(() => {
            const presentation = logPresentation(log, explanations[i])
            const trains = log.trains_involved?.join(', ')
            return (
              <>
                <div className="log-event-title">{presentation.title}</div>
                <div className="reason-text">{presentation.detail}</div>
                {log.decision_context?.section && <div className="log-context-row"><span>Section</span>{log.decision_context.section.replace(' <-> ', ' → ')}</div>}
                {log.decision_context?.selected_train && <div className="log-context-row"><span>Allowed to continue</span>{log.decision_context.selected_train}</div>}
                {log.decision_context?.hold_trains?.length > 0 && <div className="log-context-row"><span>Recommended to wait</span>{log.decision_context.hold_trains.join(', ')}</div>}
                {trains && <div className="log-trains"><span>Trains</span>{trains}</div>}
                <div className="log-card-footer">
                  <span>{formatLogTime(log.sim_timestamp)}</span>
                  <span>{sourceLabel(log.resolved_by)}</span>
                </div>
                <button
                  className="log-explain-button"
                  disabled={explaining === i}
                  onClick={() => explainLog(log, i)}
                >
                  {explaining === i ? 'Explaining...' : 'Explain simply'}
                </button>
                {explanations[i] && <div className="log-ai-explanation">{explanations[i]}</div>}
              </>
            )
          })()}
        </div>
      ))}
    </div>
  )
}
