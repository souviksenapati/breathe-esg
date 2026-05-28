import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/dashboard', icon: '🏠', label: 'Overview' },
  { to: '/ingestion', icon: '📤', label: 'Ingest Data' },
  { to: '/records', icon: '📋', label: 'Records Review' },
  { to: '/audit', icon: '📜', label: 'Audit Log' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const initials = (user.username || 'A').slice(0, 2).toUpperCase()

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-mark">
          <div className="logo-icon">🌿</div>
          <div className="logo-text">Breathe<span>ESG</span></div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-label">Navigation</div>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}

        <div className="nav-label" style={{ marginTop: 'auto' }}>Resources</div>
        <a
          href="/api/"
          target="_blank"
          rel="noreferrer"
          className="nav-link"
        >
          <span className="nav-icon">⚙️</span>
          <span>API Explorer</span>
        </a>
      </nav>

      <div className="sidebar-footer">
        <div className="user-card">
          <div className="user-avatar">{initials}</div>
          <div className="user-info">
            <div className="user-name">{user.username || 'Analyst'}</div>
            <div className="user-tenant">{user.tenant || 'tenant'}</div>
          </div>
          <button className="logout-btn" onClick={logout} title="Sign out">⏏</button>
        </div>
      </div>
    </aside>
  )
}
