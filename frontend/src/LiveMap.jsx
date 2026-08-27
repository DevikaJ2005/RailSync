import React, { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Popup, Polyline, CircleMarker, Tooltip, useMap } from 'react-leaflet'

const TN_CENTER = [11.3, 78.6]

function interpolate(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}

function interpolatePath(path, progress) {
  if (!path || path.length < 2) return null
  const segmentLength = 1 / (path.length - 1)
  const segment = Math.min(path.length - 2, Math.floor(progress / segmentLength))
  const localProgress = (progress - segment * segmentLength) / segmentLength
  return interpolate(path[segment], path[segment + 1], Math.max(0, Math.min(1, localProgress)))
}

const STATUS_COLOR = {
  moving: '#4F8FE8',
  waiting: '#E8A23D',
  held: '#D64545',
  checking: '#E8A23D',
  at_platform: '#3FA66B',
  completed: '#6B7787',
}

function FitNetwork({ stations }) {
  const map = useMap()

  useEffect(() => {
    if (stations.length > 0) {
      map.fitBounds(stations.map((station) => [station.lat, station.lng]), {
        padding: [36, 36],
        maxZoom: 8,
      })
    }
  }, [map, stations])

  return null
}

export default function LiveMap({ network, networkError, liveState, onStationClick, interactive = true }) {
  const stationsByName = useMemo(() => {
    if (!network) return {}
    const map = {}
    network.stations.forEach((s) => { map[s.name] = s })
    return map
  }, [network])
  const sectionsByKey = useMemo(() => {
    if (!network) return {}
    return Object.fromEntries(network.sections.map((section) => [
      [section.from, section.to].sort().join('|'), section,
    ]))
  }, [network])

  if (!network) {
    return <div className="map-status">{networkError ? 'Unable to load railway network.' : 'Loading railway network…'}<br /><small>{networkError || 'Make sure the backend is running on port 8000.'}</small></div>
  }

  const trainPositions = (liveState?.trains || [])
    .filter((t) => t.status !== 'completed')
    .map((t) => {
      const from = stationsByName[t.from]
      const to = stationsByName[t.to]
      if (!from || !to) return null
      const section = sectionsByKey[[t.from, t.to].sort().join('|')]
      const sectionPath = section?.path || [[from.lat, from.lng], [to.lat, to.lng]]
      const path = section?.from === t.from ? sectionPath : [...sectionPath].reverse()
      const pos = interpolatePath(path, t.progress)
      return { ...t, pos }
    })
    .filter(Boolean)

  return (
    <MapContainer center={TN_CENTER} zoom={7} style={{ height: '100%', width: '100%', minHeight: 420 }}>
      <FitNetwork stations={network.stations} />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />

      {network.sections.map((sec) => {
        const from = stationsByName[sec.from]
        const to = stationsByName[sec.to]
        if (!from || !to) return null
        return (
          <Polyline
            key={sec.id}
            positions={sec.path || [[from.lat, from.lng], [to.lat, to.lng]]}
            pathOptions={{ color: '#2F3A4A', weight: 2.5 }}
          />
        )
      })}

      {network.stations.map((s) => (
        <CircleMarker
          key={s.name}
          center={[s.lat, s.lng]}
          radius={9}
          pathOptions={{ color: '#F0A94E', fillColor: '#10151D', fillOpacity: 1, weight: 3 }}
          eventHandlers={interactive ? {
            click: (event) => {
              event.originalEvent?.stopPropagation()
              onStationClick?.(s.name)
            },
          } : {}}
        >
          <Tooltip direction="top" offset={[0, -8]} opacity={1}>
            <strong>{s.name}</strong>
          </Tooltip>
          <Popup>
            <strong>{s.name}</strong>
            <br />
            {s.platforms} platform{s.platforms > 1 ? 's' : ''}
          </Popup>
        </CircleMarker>
      ))}

      {trainPositions.map((t) => (
        <CircleMarker
          key={t.train_no}
          center={t.pos}
          radius={7}
          pathOptions={{
            color: STATUS_COLOR[t.status] || '#4F8FE8',
            fillColor: STATUS_COLOR[t.status] || '#4F8FE8',
            fillOpacity: 0.9,
            weight: 2,
          }}
        >
          <Popup>
            <div style={{ fontFamily: 'monospace' }}>
              <strong>{t.train_no}</strong> — {t.name}
              <br />
              {t.type} · {t.status.replace('_', ' ')}
              <br />
              Predicted delay (model): {t.predicted_delay_min} min
              {t.assigned_platform && <><br />Platform {t.assigned_platform}</>}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
