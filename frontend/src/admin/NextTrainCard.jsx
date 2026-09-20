import React from 'react'

function TrainIcon() {
  return (
    <svg
      className="ntc-icon"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2h3.54l2 2H18v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-4-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z" />
    </svg>
  )
}

function parseSimTime(value) {
  if (!value) return null
  const parsed = new Date(String(value).replace(' ', 'T'))
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatEta(etaValue, simValue) {
  const eta = parseSimTime(etaValue)
  const sim = parseSimTime(simValue)
  if (!eta) return '—'
  if (!sim) {
    return eta.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  }

  const diffMinutes = Math.round((eta.getTime() - sim.getTime()) / 60000)
  const sameDay = eta.toDateString() === sim.toDateString()
  if (diffMinutes < 0) {
    return `DEPARTED ${Math.abs(diffMinutes)}m AGO`
  }
  if (sameDay) {
    return eta.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  }
  const dayDelta = Math.round((Date.UTC(eta.getFullYear(), eta.getMonth(), eta.getDate()) - Date.UTC(sim.getFullYear(), sim.getMonth(), sim.getDate())) / 86400000)
  if (dayDelta === 1) {
    return `${eta.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} TOMORROW`
  }
  return eta.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export default function NextTrainCard({ liveState, network }) {
  const train = liveState?.next_train

  let trainType = null
  if (train && network?.trains) {
    const baseTrainNo = train.base_train_no || train.train_no?.split('-')[0]
    const base = network.trains.find((item) => item.train_no === baseTrainNo)
    trainType = base?.type ? base.type.toUpperCase() : null
  }

  return (
    <div className="next-train-card">
      <div className="ntc-label">
        <span className="ntc-label-dot" />
        NEXT ARRIVAL
      </div>
      {train ? (
        <>
          <div className="ntc-train">
            <TrainIcon />
            <span className="ntc-no">{train.train_no}</span>
            {trainType && <span className="ntc-type-badge">{trainType}</span>}
          </div>
          <div className="ntc-route">
            <span className="ntc-station">{train.origin}</span>
            <span className="ntc-arrow" aria-hidden="true">↓</span>
            <span className="ntc-station">{train.destination}</span>
          </div>
          <div className="ntc-meta">
            <div className="ntc-meta-cell">
              <span className="ntc-meta-label">ETA</span>
              <span className="ntc-meta-value">{formatEta(train.eta_at, liveState?.sim_time)}</span>
            </div>
            <div className="ntc-meta-cell">
              <span className="ntc-meta-label">STATUS</span>
              <span className="ntc-meta-value ntc-status">● {String(train.status || '').replace('_', ' ').toUpperCase()}</span>
            </div>
          </div>
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            Rule: {train.selection_rule === 'scheduled_departure' ? 'next scheduled departure (no eligible arrival)' : 'earliest predicted arrival'}
          </div>
        </>
      ) : (
        <div className="ntc-empty">No upcoming trains</div>
      )}
    </div>
  )
}
