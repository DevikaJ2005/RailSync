import React from 'react'

function formatEta(value) {
  if (!value) return '—'
  const parsed = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

export default function NextTrainCard({ liveState }) {
  const service = liveState?.next_departure_service

  return (
    <div className="next-train-card">
      <div className="ntc-label">NEXT TRAIN</div>
      {service ? (
        <>
          <div className="ntc-train">
            <span className="ntc-icon" aria-hidden="true">🚆</span>
            <span className="ntc-no">{service.train_no}</span>
          </div>
          <div className="ntc-route">
            {service.origin} → {service.destination}
          </div>
          <div className="ntc-eta">
            <span className="ntc-eta-label">ETA</span>
            <span className="ntc-eta-value">{formatEta(liveState?.next_departure_time)}</span>
          </div>
        </>
      ) : (
        <div className="ntc-empty">No upcoming trains</div>
      )}
    </div>
  )
}
