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

function formatWaiting(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0))
  return total < 60 ? `${total} min` : `${Math.floor(total / 60)}h ${total % 60}m`
}

function statusLabel(status) {
  return String(status || '').replaceAll('_', ' ')
}

export default function StationDetail({ station, liveState, network }) {
  if (!station) return <div className="empty-state">Click a station on the map to see platform status.</div>
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
  const occupiedPlatforms = Object.values(platformData.platforms).filter(Boolean).length

  return (
    <div>
      <div className="station-summary">
        <div>
          <div className="panel-title">{station}</div>
          <div className="station-summary-note">Station operations</div>
        </div>
        <div className="station-summary-count"><strong>{occupiedPlatforms}</strong>/{Object.keys(platformData.platforms).length}<span>platforms occupied</span></div>
      </div>
      <div className="board-row" style={{ fontWeight: 700, color: 'var(--text-muted)', fontSize: 11 }}>
        <span>PLAT</span><span>TRAIN</span><span>TYPE</span><span>STATUS</span>
      </div>
      {Object.entries(platformData.platforms).map(([plat, trainNo]) => {
        const t = trainNo ? trainsByNo[trainNo] : null
        return (
          <div className="board-row" key={plat}>
            <span className="split-flap-cell">{plat}</span>
            <span>{trainNo || '—'}</span>
            <span style={{ color: 'var(--text-muted)' }}>{t?.type || ''}</span>
              <span>
                {t ? (
                <span className={`status-chip status-${t.operational_status || t.status}`}>
                  <span className="dot" />{(t.operational_status || t.status).replace('_', ' ')}
                </span>
                ) : '—'}
              </span>
          </div>
        )
      })}

      {platformData.waiting_queue.length > 0 && (
        <>
          <div className="panel-title" style={{ marginTop: 14 }}>Waiting trains</div>
          {platformData.waiting_queue.map((trainNo) => {
            const t = trainsByNo[trainNo]
            return (
              <div key={trainNo} className="board-row" style={{ gridTemplateColumns: '1fr 1fr 90px' }}>
                <span>{trainNo}</span>
                <span style={{ color: 'var(--text-muted)' }}>{t?.type}</span>
                <span style={{ color: 'var(--signal-amber)' }}>{t?.minutes_waited}m waited</span>
                              <span style={{ color: 'var(--signal-amber)' }}>{formatWaiting(t?.minutes_waited)} waiting</span>
                <div className="panel-title" style={{ marginTop: 14 }}>Upcoming movements</div>
                            {statusLabel(train.operational_status || train.status)}
              </div>
            )
          })}
        </>
      )}

      <div className="panel-title" style={{ marginTop: 14 }}>Arrivals &amp; Departures</div>
      {arrivals.length === 0 ? (
        <div className="empty-state">No active trains scheduled for this station.</div>
      ) : arrivals.map((train) => {
        const stationIndex = train.route.indexOf(station)
        const isAtStation = train.to === station && train.operational_status !== 'moving'
        const eta = getArrivalMinutes(train, station, stationsByName)
        return (
          <div className="board-row" key={train.train_no}>
            <span className="split-flap-cell">{train.train_no}</span>
            <span>{train.name}</span>
            <span style={{ color: isAtStation ? 'var(--signal-green)' : 'var(--text-muted)' }}>
              {isAtStation ? 'At station' : `In ${eta} min`}
            </span>
            <span className={`status-chip status-${train.operational_status || train.status}`}>
              <span className="dot" />{(train.operational_status || train.status).replace('_', ' ')}
            </span>
          </div>
        )
      })}
    </div>
  )
}
