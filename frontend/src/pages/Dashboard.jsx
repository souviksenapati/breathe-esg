import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'

function StatCard({ icon, value, label, color, to }) {
  return (
    <div className="stat-card" style={{ '--stat-color': color }}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {to && <Link to={to} style={{ position: 'absolute', inset: 0 }} />}
    </div>
  )
}

export default function Dashboard() {
  const [jobs, setJobs] = useState([])
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  useEffect(() => {
    Promise.all([
      client.get('/ingestions/'),
      client.get('/records/'),
    ]).then(([jobsRes, recordsRes]) => {
      setJobs(jobsRes.data.results || jobsRes.data)
      setRecords(recordsRes.data.results || recordsRes.data)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const pending = records.filter(r => r.review_status === 'pending').length
  const suspicious = records.filter(r => r.review_status === 'suspicious').length
  const approved = records.filter(r => r.review_status === 'approved').length
  const totalRecords = records.length

  const recentJobs = [...jobs].slice(0, 6)

  function jobStatusBadge(status) {
    const map = { parsed: 'badge-parsed', failed: 'badge-failed', received: 'badge-received' }
    return <span className={`badge ${map[status] || 'badge-received'}`}>{status}</span>
  }

  function sourceTypeBadge(type) {
    const map = { sap: 'badge-sap', utility: 'badge-utility', travel: 'badge-travel' }
    return <span className={`badge ${map[type] || ''}`}>{type}</span>
  }

  if (loading) return <div className="loader"><div className="spinner" /></div>

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <h1 className="page-title">Overview</h1>
        <p className="page-subtitle">
          Welcome back, <strong>{user.username}</strong>. Here's what needs your attention.
        </p>
      </div>

      <div className="stats-grid">
        <StatCard icon="📋" value={totalRecords} label="Total Records" color="var(--blue)" to="/records" />
        <StatCard icon="⏳" value={pending} label="Pending Review" color="var(--blue)" to="/records?status=pending" />
        <StatCard icon="⚠️" value={suspicious} label="Suspicious" color="var(--amber)" to="/records?status=suspicious" />
        <StatCard icon="✅" value={approved} label="Approved" color="var(--accent)" to="/records?status=approved" />
        <StatCard icon="📤" value={jobs.length} label="Ingestion Jobs" color="var(--purple)" to="/ingestion" />
      </div>

      {/* Scope breakdown */}
      <div className="card mb-6">
        <div className="card-header">
          <h2 className="card-title">Records by Scope</h2>
          <Link to="/records" className="btn btn-secondary btn-sm">View all →</Link>
        </div>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)' }}>
            {['scope1', 'scope2', 'scope3'].map(scope => {
              const count = records.filter(r => r.scope === scope).length
              const label = { scope1: 'Scope 1 — Direct', scope2: 'Scope 2 — Energy', scope3: 'Scope 3 — Value Chain' }[scope]
              return (
                <div key={scope} style={{ textAlign: 'center', padding: 'var(--space-4)' }}>
                  <span className={`badge badge-${scope}`} style={{ fontSize: 'var(--text-sm)', padding: '6px 16px', marginBottom: 'var(--space-3)', display: 'inline-flex' }}>{label}</span>
                  <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, marginTop: 'var(--space-2)' }}>{count}</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>records</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Recent ingestion jobs */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Recent Ingestion Jobs</h2>
          <Link to="/ingestion" className="btn btn-secondary btn-sm">Upload new →</Link>
        </div>
        {recentJobs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📂</div>
            <div className="empty-title">No ingestion jobs yet</div>
            <div className="empty-desc">Upload your first CSV file to get started.</div>
            <Link to="/ingestion" className="btn btn-primary mt-4">Upload data →</Link>
          </div>
        ) : (
          <div className="table-wrapper" style={{ borderRadius: 0, border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Parsed</th>
                  <th>Failed</th>
                  <th>Suspicious</th>
                  <th>Approved</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map(job => (
                  <tr key={job.id}>
                    <td className="text-mono">#{job.id}</td>
                    <td>{sourceTypeBadge(job.source_type)}</td>
                    <td>{jobStatusBadge(job.status)}</td>
                    <td>{job.total_rows}</td>
                    <td style={{ color: 'var(--accent)' }}>{job.parsed_rows}</td>
                    <td style={{ color: job.failed_rows > 0 ? 'var(--red)' : 'var(--text-muted)' }}>{job.failed_rows}</td>
                    <td style={{ color: job.suspicious_rows > 0 ? 'var(--amber)' : 'var(--text-muted)' }}>{job.suspicious_rows}</td>
                    <td style={{ color: 'var(--accent)' }}>{job.approved_rows}</td>
                    <td className="text-mono">{new Date(job.created_at).toLocaleDateString()}</td>
                    <td>
                      <Link to={`/records?job=${job.id}`} className="btn btn-sm btn-secondary">Review →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
