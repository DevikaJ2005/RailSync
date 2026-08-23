import React, { useState } from 'react'
import LiveMap from '../LiveMap.jsx'
import PlatformView from './PlatformView.jsx'
import TrainSearch from './TrainSearch.jsx'

export default function UserPanel({ liveState, network, networkError, connected }) {
  const [selectedStation, setSelectedStation] = useState(null)
  const [tab, setTab] = useState('platform')

  return (
    <>
      <div className="map-column">
        <LiveMap network={network} networkError={networkError} liveState={liveState} onStationClick={setSelectedStation} interactive />
        <div className="legend">
          <span className="legend-item"><span className="legend-dot" style={{ background: '#4F8FE8' }} />Moving</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#E8A23D' }} />Waiting</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#3FA66B' }} />Boarding</span>
        </div>
      </div>

      <div className="side-column">
        <div className="tab-strip">
          <button className={tab === 'platform' ? 'active' : ''} onClick={() => setTab('platform')}>
            Platform Board
          </button>
          <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>
            Find Train
          </button>
        </div>
        <div className="scroll-area">
          {tab === 'platform' && <PlatformView station={selectedStation} liveState={liveState} network={network} />}
          {tab === 'search' && <TrainSearch liveState={liveState} />}
        </div>
      </div>
    </>
  )
}
