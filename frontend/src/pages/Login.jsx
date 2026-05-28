import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await client.post('/auth/login/', { username, password })
      localStorage.setItem('token', res.data.token)
      localStorage.setItem('user', JSON.stringify(res.data.user))
      navigate('/dashboard')
    } catch (err) {
      setError(
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.detail ||
        'Login failed. Please check your credentials.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      {/* Left panel */}
      <div className="login-left">
        <div className="login-left-content">
          <div className="login-brand">
            <div className="login-brand-icon">🌿</div>
            <div className="login-brand-name">Breathe<span>ESG</span></div>
          </div>
          <div className="login-tagline">
            Emissions data,<br /><span>done right</span>.
          </div>
          <p className="login-desc">
            Ingest, normalize, and review your Scope 1, 2 &amp; 3 activity data from SAP, utilities, and travel platforms — all in one analyst dashboard.
          </p>
          <div className="login-features">
            {[
              'Multi-source ingestion: SAP, Utility, Travel',
              'Automatic suspicious-record detection',
              'Analyst review & approve workflow',
              'Full audit trail for sign-off',
            ].map(f => (
              <div className="login-feature" key={f}>
                <div className="login-feature-dot" />
                <span>{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className="login-right">
        <div className="login-form-card fade-in">
          <h1 className="login-form-title">Welcome back</h1>
          <p className="login-form-subtitle">Sign in to access your analyst dashboard</p>

          {error && <div className="error-msg">⚠️ {error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="username">Username</label>
              <input
                id="username"
                className="form-input"
                type="text"
                placeholder="analyst"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="password">Password</label>
              <input
                id="password"
                className="form-input"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>
            <button
              type="submit"
              id="login-submit-btn"
              className="btn btn-primary btn-lg w-full mt-4"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Sign in →'}
            </button>
          </form>

          <div className="demo-hint">
            Demo credentials: <strong>analyst</strong> / <strong>demo1234</strong>
          </div>
        </div>
      </div>
    </div>
  )
}
