import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function SimulationControls({ liveState }) {
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(1)

  useEffect(() => {
    if (!liveState) return
    setPaused(Boolean(liveState.paused))
    setSpeed(Number(liveState.speed_multiplier || 1))
  }, [liveState?.paused, liveState?.speed_multiplier])

  const togglePause = async () => {
    if (paused) {
      await api.resumeSimulation()
      setPaused(false)
    } else {
      await api.pauseSimulation()
      setPaused(true)
    }
  }

  const changeSpeed = async (multiplier) => {
    setSpeed(multiplier)
    await api.setSpeed(multiplier)
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <button className="btn" onClick={togglePause}>
        {paused ? 'Resume' : 'Pause'}
      </button>
      {[1, 2, 5].map((multiplier) => (
        <button
          key={multiplier}
          className={`btn btn-sm ${speed === multiplier ? 'btn-primary' : ''}`}
          onClick={() => changeSpeed(multiplier)}
        >
          {multiplier}x
        </button>
      ))}
      {liveState?.next_departure_service && (
        <span className="next-service-chip">
          Next {liveState.next_departure_service.train_no} from {liveState.next_departure_service.origin}
        </span>
      )}
    </div>
  )
}
