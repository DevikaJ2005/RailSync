import React from 'react'

function distanceKm(a, b) {
  const earthRadius = 6371
  const lat = (b.lat - a.lat) * Math.PI / 180
  const lng = (b.lng - a.lng) * Math.PI / 180
  const value = Math.sin(lat / 2) ** 2 + Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * Math.sin(lng / 2) ** 2
  return earthRadius * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value))
}

function getArrivalMinutes(train, station, stationsByName) {
  const stationIndex = train.route.indexOf(station)
  let minutes = 0
  for (let index = train.route_index; index < stationIndex; index += 1) {
    const from = stationsByName[train.route[index]]
    const to = stationsByName[train.route[index + 1]]
    if (from && to) minutes += distanceKm(from, to) / train.speed_kmph * 60
  }
  if (stationIndex === train.route_index + 1) minutes *= Math.max(0, 1 - train.progress)
  return Math.max(0, Math.round(minutes))
}

export default function PlatformView({ station, liveState, network }) {
  if (!station) return <div className="empty-state">Tap a station on the map to see arrivals.</div>
  if (!liveState) return <div className="empty-state">Loading…</div>

  const platformData = liveState.platforms?.[station]
  if (!platformData) return <div className="empty-state">No data for {station}.</div>

  const trainsByNo = {}
  liveState.trains.forEach((t) => { trainsByNo[t.train_no] = t })
  const stationsByName = Object.fromEntries((network?.stations || []).map((item) => [item.name, item]))
  const arrivals = liveState.trains.filter((train) => {
    const stationIndex = train.route?.indexOf(station) ?? -1
    return train.status !== 'completed' && stationIndex > train.route_index
  })

  return (
    <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--line-steel)' }}>
        <div className="panel-title" style={{ margin: 0 }}>{station}</div>
      </div>
      <div className="split-flap" style={{ padding: '8px 0' }}>
        {Object.entries(platformData.platforms).map(([plat, trainNo]) => {
          const t = trainNo ? trainsByNo[trainNo] : null
          return (
            <div key={plat} className="board-row">
              <span className="split-flap-cell">PL{plat}</span>
              <span>{t ? `${t.train_no} ${t.name}` : '— no train —'}</span>
              <span>{t ? t.type.slice(0, 3).toUpperCase() : ''}</span>
              <span>
                {t?.status === 'waiting' && <span style={{ color: 'var(--signal-amber)' }}>● WAITING</span>}
                {t?.status === 'at_platform' && <span style={{ color: 'var(--signal-green)' }}>● BOARDING</span>}
                {!t && <span style={{ color: 'var(--text-muted)' }}>—</span>}
              </span>
            </div>
          )
        })}
        {platformData.waiting_queue.length > 0 && platformData.waiting_queue.map((tn) => {
          const t = trainsByNo[tn]
          return (
            <div key={tn} className="board-row" style={{ opacity: 0.75 }}>
              <span className="split-flap-cell">—</span>
              <span>{tn} {t?.name}</span>
              <span>{t?.type.slice(0, 3).toUpperCase()}</span>
              <span style={{ color: 'var(--signal-amber)' }}>● HOLDING</span>
            </div>
          )
        })}
      </div>
      <div style={{ padding: '12px 16px 6px' }}>
        <div className="panel-title" style={{ margin: 0 }}>Upcoming Trains</div>
      </div>
      {arrivals.length === 0 ? (
        <div className="empty-state">No active trains scheduled for this station.</div>
      ) : arrivals.map((train) => {
        const isAtStation = train.to === station && train.status !== 'moving'
        const eta = getArrivalMinutes(train, station, stationsByName)
        return (
          <div className="board-row" key={train.train_no}>
            <span className="split-flap-cell">{train.train_no}</span>
            <span>{train.name}</span>
            <span style={{ color: isAtStation ? 'var(--signal-green)' : 'var(--text-muted)' }}>
              {isAtStation ? 'At station' : `${eta} min`}
            </span>
            <span className={`status-chip status-${train.status}`}>
              <span className="dot" />{train.status.replace('_', ' ')}
            </span>
          </div>
        )
      })}
    </div>
  )
}
