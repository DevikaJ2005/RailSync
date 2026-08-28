import React from 'react'

function TrainIcon() {
  return (
    <svg
      className="ntc-icon"
      viewBox="0 0 24 24"
      width="15"
      height="15"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2h3.54l2 2H18v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-4-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z" />
    </svg>
  )
}

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
            <TrainIcon />
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
