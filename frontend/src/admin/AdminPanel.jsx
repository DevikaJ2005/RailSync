import React, { useEffect, useRef, useState } from 'react'
import LiveMap from '../LiveMap.jsx'
import NextTrainCard from './NextTrainCard.jsx'
import StationDetail from './StationDetail.jsx'
import ConflictPanel from './ConflictPanel.jsx'
import DecisionLog from './DecisionLog.jsx'
import WhatIfSimulator from './WhatIfSimulator.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'

const TABS = ['Station', 'Conflicts', 'Log', 'Analytics']
const PANEL_MIN_WIDTH = 300
const PANEL_MAX_WIDTH = 600
const PANEL_DEFAULT_WIDTH = 360

export default function AdminPanel({ liveState, network, networkError, connected, modelInfo }) {
  const [activeTab, setActiveTab] = useState('Conflicts')
  const [selectedStation, setSelectedStation] = useState(null)
  const [panelWidth, setPanelWidth] = useState(PANEL_DEFAULT_WIDTH)
  const [resizing, setResizing] = useState(false)
  const stopResizeRef = useRef(null)

  useEffect(() => () => stopResizeRef.current?.(), [])

  const handleResizeStart = (event) => {
    event.preventDefault()
    setResizing(true)
    document.body.classList.add('panel-resizing')

    let frame = null
    const onMove = (moveEvent) => {
      if (frame !== null) return
      frame = window.requestAnimationFrame(() => {
        frame = null
        const next = window.innerWidth - moveEvent.clientX
        setPanelWidth(Math.min(PANEL_MAX_WIDTH, Math.max(PANEL_MIN_WIDTH, next)))
      })
    }
    const onEnd = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onEnd)
      if (frame !== null) window.cancelAnimationFrame(frame)
      document.body.classList.remove('panel-resizing')
      stopResizeRef.current = null
      setResizing(false)
    }
    stopResizeRef.current = onEnd
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onEnd)
  }

  const handleStationClick = (name) => {
    setSelectedStation(name)
    setActiveTab('Station')
  }

  const activeConflictCount = liveState?.resolutions?.length || 0

  return (
    <>
      <div className="map-column">
        <LiveMap
          network={network}
          networkError={networkError}
          liveState={liveState}
          onStationClick={handleStationClick}
          interactive
          panelWidth={panelWidth}
        />
        <NextTrainCard liveState={liveState} />
        <div className="legend">
          <span className="legend-item"><span className="legend-dot" style={{ background: '#4F8FE8' }} />Moving</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#E8A23D' }} />Waiting</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#D64545' }} />Held</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#3FA66B' }} />At platform</span>
          <span className="legend-item"><span className="legend-dot" style={{ background: '#6B7787' }} />Completed</span>
        </div>
      </div>

      <div
        className={`resize-divider${resizing ? ' active' : ''}`}
        onMouseDown={handleResizeStart}
        onDoubleClick={() => setPanelWidth(PANEL_DEFAULT_WIDTH)}
        role="separator"
        aria-orientation="vertical"
        aria-label="Drag to resize the operations panel"
        title="Drag to resize · double-click to reset"
      />

      <div className="side-column" style={{ width: panelWidth }}>
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
