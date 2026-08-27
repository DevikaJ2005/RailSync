import React, { useState } from 'react'
import LiveMap from '../LiveMap.jsx'
import StationDetail from './StationDetail.jsx'
import ConflictPanel from './ConflictPanel.jsx'
import DecisionLog from './DecisionLog.jsx'
import WhatIfSimulator from './WhatIfSimulator.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'
import SimulationControls from './SimulationControls.jsx'

const TABS = ['Station', 'Conflicts', 'Log', 'Analytics']

export default function AdminPanel({ liveState, network, networkError, connected, modelInfo }) {
  const [activeTab, setActiveTab] = useState('Conflicts')
  const [selectedStation, setSelectedStation] = useState(null)

  const handleStationClick = (name) => {
    setSelectedStation(name)
    setActiveTab('Station')
  }

  const activeConflictCount = liveState?.resolutions?.length || 0

  return (
    <>
      <div className="map-column">
        <LiveMap network={network} networkError={networkError} liveState={liveState} onStationClick={handleStationClick} interactive />
        <div className="legend">
          <span className="legend-item"><span className="legend-dot" style={{ background: '#4F8FE8' }} />Moving</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#E8A23D' }} />Waiting</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#D64545' }} />Held</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#3FA66B' }} />At platform</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#6B7787' }} />Completed</span>
        </div>
        <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 1000, background: 'var(--bg-panel-raised)', border: '1px solid var(--line-steel)', borderRadius: 8, padding: '8px 12px' }}>
          <SimulationControls liveState={liveState} />
        </div>
      </div>

      <div className="side-column">
        <div className="tab-strip">
          {TABS.map((tab) => (
            <button
              key={tab}
              className={activeTab === tab ? 'active' : ''}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
              {tab === 'Conflicts' && activeConflictCount > 0 && (
                <span style={{
                  marginLeft: 5, background: 'var(--signal-red)', color: 'white',
                  borderRadius: 8, fontSize: 10, padding: '1px 5px',
                }}>
                  {activeConflictCount}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="scroll-area">
          {activeTab === 'Station' && <StationDetail station={selectedStation} liveState={liveState} network={network} />}
          {activeTab === 'Conflicts' && <ConflictPanel liveState={liveState} />}
          {activeTab === 'Log' && <DecisionLog />}
          {activeTab === 'Analytics' && (
            <>
              <AnalyticsDashboard modelInfo={modelInfo} />
              <div style={{ marginTop: 14 }}>
                <WhatIfSimulator liveState={liveState} />
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
