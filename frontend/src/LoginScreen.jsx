import React, { useState } from 'react'
import logo from './assets/logo.png'
import { SAMPLE_CREDENTIALS } from './auth.js'

export default function LoginScreen({ onLogin, error: serverError }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      await onLogin(username.trim(), password)
    } finally {
      setSubmitting(false)
    }
  }

  const fill = (cred) => {
    setUsername(cred.username)
    setPassword(cred.password)
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-header">
          <img src={logo} alt="RailSync Logo" className="login-logo" />
          <h1 className="login-title">RailSync Sign-In</h1>
          <p className="login-subtitle">
            Role-based access to the simulated control room and passenger views.
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>Username</span>
            <input
              className="filter-input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="controller or passenger"
              autoComplete="username"
              autoFocus
            />
          </label>
          <label className="login-field">
            <span>Password</span>
            <input
              className="filter-input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </label>

          {serverError && <div className="login-error">{serverError}</div>}

          <button
            className="btn btn-primary login-submit"
            type="submit"
            disabled={submitting || !username || !password}
          >
            {submitting ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="login-creds">
          <div className="login-creds-title">Sample accounts</div>
          {SAMPLE_CREDENTIALS.map((cred) => (
            <button key={cred.role} type="button" className="cred-card" onClick={() => fill(cred)}>
              <div className="cred-role">
                <span className={`role-pill role-${cred.role}`}>{cred.role}</span>
                <span className="cred-label">{cred.label}</span>
              </div>
              <div className="cred-creds">
                <code>{cred.username}</code>
                <span className="cred-sep">/</span>
                <code>{cred.password}</code>
              </div>
              <div className="cred-hint">{cred.hint}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}