import { useState, useEffect } from 'react'
import client from '../api/client'

const ACTION_LABELS = {
  ingestion_created: { label: 'Ingestion Created', icon: '📤', color: 'var(--blue)' },
  record_created: { label: 'Record Created', icon: '➕', color: 'var(--accent)' },
  record_edited: { label: 'Record Edited', icon: '✏️', color: 'var(--amber)' },
  record_approved: { label: 'Record Approved', icon: '✅', color: 'var(--accent)' },
}

export default function AuditLog() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    client.get('/audit-events/')
      .then(res => setEvents(res.data.results || res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <h1 className="page-title">Audit Log</h1>
        <p className="page-subtitle">
          Immutable record of every ingestion, edit, and approval action. Read-only.
        </p>
      </div>

      <div className="card">
        {loading ? (
          <div className="loader"><div className="spinner" /></div>
        ) : events.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <div className="empty-title">No audit events yet</div>
            <div className="empty-desc">Events appear as you ingest data, edit, and approve records.</div>
          </div>
        ) : (
          <div style={{ padding: 'var(--space-6)' }}>
            {events.map((event, i) => {
              const meta = ACTION_LABELS[event.action] || { label: event.action, icon: '•', color: 'var(--text-secondary)' }
              const isExpanded = expandedId === event.id
              const hasChanges = event.before || event.after

              return (
                <div
                  key={event.id}
                  style={{
                    display: 'flex',
                    gap: 'var(--space-4)',
                    marginBottom: i < events.length - 1 ? 'var(--space-4)' : 0,
                    position: 'relative',
                  }}
                >
                  {/* Timeline line */}
                  {i < events.length - 1 && (
                    <div style={{
                      position: 'absolute',
                      left: 20,
                      top: 44,
                      bottom: -16,
                      width: 1,
                      background: 'var(--border)',
                    }} />
                  )}

                  {/* Icon */}
                  <div style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    background: `${meta.color}20`,
                    border: `1px solid ${meta.color}40`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1rem',
                    flexShrink: 0,
                    zIndex: 1,
                  }}>
                    {meta.icon}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, paddingBottom: 'var(--space-4)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: meta.color }}>
                        {meta.label}
                      </span>
                      <span className="tag">{event.entity_type} #{event.entity_id}</span>
                      {event.actor && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                          by {event.actor}
                        </span>
                      )}
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                        {new Date(event.created_at).toLocaleString()}
                      </span>
                    </div>

                    {hasChanges && (
                      <button
                        className="btn btn-sm btn-secondary"
                        style={{ marginTop: 'var(--space-2)' }}
                        onClick={() => setExpandedId(isExpanded ? null : event.id)}
                      >
                        {isExpanded ? '▲ Hide details' : '▼ Show details'}
                      </button>
                    )}

                    {isExpanded && (
                      <div style={{ marginTop: 'var(--space-3)', display: 'grid', gridTemplateColumns: event.before ? '1fr 1fr' : '1fr', gap: 'var(--space-4)' }}>
                        {event.before && (
                          <div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--red)', fontWeight: 600, marginBottom: 'var(--space-2)' }}>Before</div>
                            <pre className="json-viewer">{JSON.stringify(event.before, null, 2)}</pre>
                          </div>
                        )}
                        {event.after && (
                          <div>
                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', fontWeight: 600, marginBottom: 'var(--space-2)' }}>After</div>
                            <pre className="json-viewer">{JSON.stringify(event.after, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
