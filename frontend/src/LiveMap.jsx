import React, { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, Popup, Polyline, CircleMarker, Marker, Tooltip, useMap, useMapEvents, ZoomControl } from 'react-leaflet'
import L from 'leaflet'

const TN_CENTER = [11.3, 78.6]

function interpolate(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}

function calculateBearing(a, b) {
  if (!a || !b) return 0
  const lat1 = (a[0] * Math.PI) / 180
  const lat2 = (b[0] * Math.PI) / 180
  const dLng = ((b[1] - a[1]) * Math.PI) / 180

  const y = Math.sin(dLng) * Math.cos(lat2)
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng)
  const brng = (Math.atan2(y, x) * 180) / Math.PI
  return (brng + 360) % 360
}

function interpolatePathWithBearing(path, progress) {
  if (!path || path.length < 2) return { pos: null, bearing: 0 }
  const segmentCount = path.length - 1
  const segmentLength = 1 / segmentCount
  const rawSegment = Math.floor(progress / segmentLength)
  const segment = Math.min(segmentCount - 1, Math.max(0, rawSegment))
  const localProgress = (progress - segment * segmentLength) / segmentLength
  const clampedProgress = Math.max(0, Math.min(1, localProgress))
  const pos = interpolate(path[segment], path[segment + 1], clampedProgress)

  let bearing = calculateBearing(path[segment], path[segment + 1])
  if (isNaN(bearing) || (path[segment][0] === path[segment + 1][0] && path[segment][1] === path[segment + 1][1])) {
    bearing = calculateBearing(path[0], path[path.length - 1]) || 0
  }
  return { pos, bearing }
}

function getContinuousBearing(prevBearing, newBearing) {
  if (prevBearing === undefined || isNaN(prevBearing)) return newBearing
  let diff = (newBearing - prevBearing) % 360
  if (diff > 180) diff -= 360
  if (diff < -180) diff += 360
  return prevBearing + diff
}

function getTrainSprite(type = '') {
  const t = (type || '').toLowerCase()
  if (t.includes('freight') || t.includes('goods') || t.includes('cargo')) {
    return '/trains/freight_train.svg'
  }
  if (t.includes('passenger') || t.includes('commuter') || t.includes('local')) {
    return '/trains/passenger_train.svg'
  }
  return '/trains/express_train.svg'
}

function getTrackDimensions(zoom) {
  const z = Math.max(5, Math.min(15, zoom || 7))
  const scale = Math.pow(1.38, z - 7)

  const ballastWeight = Math.round(Math.max(2.2, 3.5 * scale) * 10) / 10
  const railWeight = Math.round(Math.max(1.1, 1.5 * scale) * 10) / 10
  const conflictBallastWeight = Math.round((ballastWeight + 3 * scale) * 10) / 10
  const conflictRailWeight = Math.round((railWeight + 1.2 * scale) * 10) / 10
  const dashPattern = `${Math.round(Math.max(2, 2.5 * scale))}, ${Math.round(Math.max(4, 5 * scale))}`
  const stationRadius = Math.round(Math.max(4.5, Math.min(14, 5.5 * Math.pow(1.2, z - 7))) * 10) / 10
  const stationBorder = Math.max(1.5, Math.min(4, Math.round(2 * Math.pow(1.15, z - 7) * 10) / 10))

  return {
    ballastWeight,
    railWeight,
    conflictBallastWeight,
    conflictRailWeight,
    dashPattern,
    stationRadius,
    stationBorder,
  }
}

function getTrainDimensions(zoom) {
  const z = Math.max(5, Math.min(15, zoom || 7))
  const scale = Math.pow(1.38, z - 7)

  // Zoom 7 base height is 26px (sleek, non-cluttered overview)
  const height = Math.round(26 * scale)
  // SVG aspect ratio 24:90 -> 0.2667
  const width = Math.max(5, Math.round(height * 0.267))
  const boxW = Math.max(28, Math.round(width * 2.8))
  const boxH = Math.max(34, Math.round(height * 1.35))
  const anchorX = Math.round(boxW / 2)
  const anchorY = Math.round(boxH / 2)
  const fontSize = Math.max(8.5, Math.min(13, Math.round((8.8 + (z - 7) * 0.8) * 10) / 10))
  const dotSize = Math.max(4.5, Math.min(8.5, Math.round((5 + (z - 7) * 0.65) * 10) / 10))

  return {
    width,
    height,
    boxW,
    boxH,
    anchorX,
    anchorY,
    fontSize,
    dotSize,
  }
}

function createTrainIcon({
  trainNo,
  type,
  status,
  bearing,
  isInSelectedConflict,
  isNextArrival,
  isSelected,
  zoom,
}) {
  const spriteUrl = getTrainSprite(type)
  const dims = getTrainDimensions(zoom)

  const classes = [
    'train-marker-wrap',
    `status-${status}`,
    isInSelectedConflict ? 'in-selected-conflict' : '',
    isSelected ? 'is-selected' : '',
    isNextArrival && !isInSelectedConflict ? 'is-next-arrival' : '',
    'show-label',
  ].filter(Boolean).join(' ')

  const roundedBearing = Math.round(bearing * 10) / 10
  const labelOffset = Math.round(dims.height / 2 + 3)

  const html = `
    <div class="${classes}" style="width: ${dims.boxW}px; height: ${dims.boxH}px;" title="${trainNo} (${type}) — ${status}">
      <div class="train-sprite-box" style="width: ${dims.width}px; height: ${dims.height}px; margin-top: -${Math.round(dims.height / 2)}px; margin-left: -${Math.round(dims.width / 2)}px; transform: rotate(${roundedBearing}deg);">
        <img src="${spriteUrl}" class="train-sprite-img" alt="${trainNo}" draggable="false" />
      </div>
      <div class="train-label-pill" style="top: calc(50% + ${labelOffset}px); font-size: ${dims.fontSize}px;">
        <span class="train-label-dot ${status}" style="width: ${dims.dotSize}px; height: ${dims.dotSize}px;"></span>
        <span class="train-label-id">${trainNo}</span>
      </div>
    </div>
  `

  return L.divIcon({
    className: 'leaflet-train-marker-root',
    html,
    iconSize: [dims.boxW, dims.boxH],
    iconAnchor: [dims.anchorX, dims.anchorY],
    popupAnchor: [0, -Math.round(dims.height / 2 + 6)],
  })
}

function FitNetwork({ stations }) {
  const map = useMap()
  const hasFittedRef = useRef(false)

  useEffect(() => {
    if (!hasFittedRef.current && stations && stations.length > 0) {
      map.fitBounds(stations.map((station) => [station.lat, station.lng]), {
        padding: [36, 36],
        maxZoom: 8,
      })
      hasFittedRef.current = true
    }
  }, [map, stations])

  return null
}

function MapResizeHandler({ width }) {
  const map = useMap()

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      map.invalidateSize({ animate: false })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [map, width])

  return null
}

function ZoomTracker({ onZoomChange }) {
  const map = useMap()

  useEffect(() => {
    const update = () => onZoomChange(map.getZoom())
    map.on('zoom zoomend', update)
    update()
    return () => {
      map.off('zoom zoomend', update)
    }
  }, [map, onZoomChange])

  return null
}

function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click: () => onMapClick?.(),
  })
  return null
}

export default function LiveMap({
  network,
  networkError,
  liveState,
  onStationClick,
  conflicts = [],
  resolutions = [],
  selectedConflictId = null,
  interactive = true,
  panelWidth = null,
}) {
  const prevBearingsRef = useRef({})
  const [mapZoom, setMapZoom] = useState(7)
  const [selectedTrainNo, setSelectedTrainNo] = useState(null)

  const trackDims = useMemo(() => getTrackDimensions(mapZoom), [mapZoom])

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

  const selectedResolution = resolutions.find((item) => (item.conflict_id || item.decision_id) === selectedConflictId)
  const selectedConflict = conflicts.find((item) => (item.conflict_id || item.decision_id) === selectedConflictId)
    || (selectedResolution && { ...selectedResolution, trains_involved: [selectedResolution.winner_train, ...selectedResolution.held_trains] })
  const selectedTrainNumbers = useMemo(() => new Set(selectedConflict?.trains_involved || []), [selectedConflict])
  const nextTrainNo = liveState?.next_train?.train_no

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
      const { pos, bearing: rawBearing } = interpolatePathWithBearing(path, t.progress)
      if (!pos) return null

      const prevBearing = prevBearingsRef.current[t.train_no]
      const continuousBearing = getContinuousBearing(prevBearing, rawBearing)
      prevBearingsRef.current[t.train_no] = continuousBearing

      return { ...t, pos, bearing: continuousBearing }
    })
    .filter(Boolean)

  return (
    <MapContainer center={TN_CENTER} zoom={7} zoomControl={false} style={{ height: '100%', width: '100%', minHeight: 420 }}>
      <ZoomControl position="topright" />
      <FitNetwork stations={network.stations} />
      <MapResizeHandler width={panelWidth} />
      <ZoomTracker onZoomChange={setMapZoom} />
      <MapClickHandler onMapClick={() => setSelectedTrainNo(null)} />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />

      {/* Railway Alignment Layer: Track ballast bed and rail centerline dynamically scaled with zoom */}
      {network.sections.map((sec) => {
        const from = stationsByName[sec.from]
        const to = stationsByName[sec.to]
        if (!from || !to) return null
        const positions = sec.path || [[from.lat, from.lng], [to.lat, to.lng]]
        return (
          <React.Fragment key={sec.id}>
            {/* Ballast bed */}
            <Polyline
              key={`${sec.id}-ballast-z${Math.round(mapZoom)}`}
              positions={positions}
              pathOptions={{
                color: '#334155',
                weight: trackDims.ballastWeight,
                opacity: 0.85,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {/* Railway track centerline & ties */}
            <Polyline
              key={`${sec.id}-rail-z${Math.round(mapZoom)}`}
              positions={positions}
              pathOptions={{
                color: '#94A3B8',
                weight: trackDims.railWeight,
                opacity: 0.9,
                dashArray: trackDims.dashPattern,
                lineCap: 'butt',
                lineJoin: 'round',
              }}
            />
          </React.Fragment>
        )
      })}

      {selectedConflict && (() => {
        const [fromName, toName] = selectedConflict.section.split(' <-> ')
        const section = sectionsByKey[[fromName, toName].sort().join('|')]
        const from = stationsByName[fromName]
        const to = stationsByName[toName]
        if (!from || !to) return null
        const positions = section?.path || [[from.lat, from.lng], [to.lat, to.lng]]
        return (
          <React.Fragment key={`selected-conflict:${selectedConflictId}`}>
            {/* Selected conflict corridor: caution ballast */}
            <Polyline
              key={`selected-conflict-ballast-z${Math.round(mapZoom)}`}
              positions={positions}
              pathOptions={{
                color: '#7F1D1D',
                weight: trackDims.conflictBallastWeight,
                opacity: 0.85,
                lineCap: 'round',
                lineJoin: 'round',
              }}
              eventHandlers={interactive ? { click: () => {} } : {}}
            />
            {/* Selected conflict corridor: caution track */}
            <Polyline
              key={`selected-conflict-track-z${Math.round(mapZoom)}`}
              positions={positions}
              pathOptions={{
                color: '#EF4444',
                weight: trackDims.conflictRailWeight,
                opacity: 0.95,
                dashArray: '5, 5',
                lineCap: 'butt',
                lineJoin: 'round',
              }}
              eventHandlers={interactive ? { click: () => {} } : {}}
            />
          </React.Fragment>
        )
      })()}

      {network.stations.map((s) => (
        <CircleMarker
          key={s.name}
          center={[s.lat, s.lng]}
          radius={trackDims.stationRadius}
          pathOptions={{
            color: '#F59E0B',
            fillColor: '#0F172A',
            fillOpacity: 1,
            weight: trackDims.stationBorder,
          }}
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

      {trainPositions.map((t) => {
        const isInSelectedConflict = selectedTrainNumbers.has(t.train_no)
        const isNextArrival = Boolean(nextTrainNo && t.train_no === nextTrainNo)
        const isSelected = selectedTrainNo === t.train_no

        const icon = createTrainIcon({
          trainNo: t.train_no,
          type: t.type,
          status: t.status,
          bearing: t.bearing,
          isInSelectedConflict,
          isNextArrival,
          isSelected,
          zoom: mapZoom,
        })

        return (
          <Marker
            key={t.train_no}
            position={t.pos}
            icon={icon}
            zIndexOffset={isInSelectedConflict ? 600 : isSelected ? 500 : isNextArrival ? 400 : 100}
            eventHandlers={{
              click: () => setSelectedTrainNo(t.train_no),
              popupclose: () => {
                if (selectedTrainNo === t.train_no) {
                  setSelectedTrainNo(null)
                }
              },
            }}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace' }}>
                <strong>{t.train_no}</strong> — {t.name}
                <br />
                {t.type} · {t.location_state} · {t.operational_status?.replace('_', ' ') || t.status}
                <br />
                Current delay: {t.current_delay_min} min
                <br />
                Predicted delay: {t.predicted_delay_min} min
                {t.assigned_platform && <><br />Platform {t.assigned_platform}</>}
              </div>
            </Popup>
          </Marker>
        )
      })}
    </MapContainer>
  )
}
