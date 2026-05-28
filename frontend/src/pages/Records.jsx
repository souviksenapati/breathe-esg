import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import client from '../api/client'

function Badge({ value, type }) {
  const map = {
    pending: 'badge-pending',
    suspicious: 'badge-suspicious',
    approved: 'badge-approved',
    failed: 'badge-failed',
    scope1: 'badge-scope1',
    scope2: 'badge-scope2',
    scope3: 'badge-scope3',
    sap: 'badge-sap',
    utility: 'badge-utility',
    travel: 'badge-travel',
    fuel: 'badge-fuel',
    procurement: 'badge-procurement',
    electricity: 'badge-electricity',
    flight: 'badge-flight',
    hotel: 'badge-hotel',
    ground: 'badge-ground',
  }
  return <span className={`badge ${map[value] || ''}`}>{value?.replace('_', ' ')}</span>
}

function RawPayloadModal({ record, onClose }) {
  if (!record) return null
  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div className="modal-title">Raw Payload — Row #{record.raw_record?.row_number ?? '?'}</div>
          <button className="btn btn-icon" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)' }}>
            The original row as received from the source file. This is the immutable source-of-truth record.
          </p>
          <pre className="json-viewer">{JSON.stringify(record.raw_record?.payload ?? {}, null, 2)}</pre>
          {record.suspicious_reasons?.length > 0 && (
            <>
              <div style={{ marginTop: 'var(--space-4)', fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--amber)', marginBottom: 'var(--space-2)' }}>
                ⚠️ Suspicious Reasons
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                {record.suspicious_reasons.map(r => (
                  <span key={r} className="badge badge-suspicious">{r.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

function EditModal({ record, onClose, onSave }) {
  const [description, setDescription] = useState(record.description || '')
  const [location, setLocation] = useState(record.location || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const res = await client.patch(`/records/${record.id}/`, { description, location })
      onSave(res.data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.non_field_errors?.[0] || 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div className="modal-title">Edit Record #{record.id}</div>
          <button className="btn btn-icon" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {record.is_locked && (
            <div style={{ padding: 'var(--space-3)', background: 'var(--amber-dim)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--amber)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
              🔒 This record is locked for audit and cannot be edited.
            </div>
          )}
          {error && <div className="error-msg">{error}</div>}
          <div className="form-group">
            <label className="form-label">Description</label>
            <input className="form-input" value={description} onChange={e => setDescription(e.target.value)} disabled={record.is_locked} />
          </div>
          <div className="form-group">
            <label className="form-label">Location / Plant / Facility</label>
            <input className="form-input" value={location} onChange={e => setLocation(e.target.value)} disabled={record.is_locked} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginTop: 'var(--space-4)' }}>
            {[
              ['Scope', <Badge value={record.scope} />],
              ['Activity', <Badge value={record.activity_type} />],
              ['Status', <Badge value={record.review_status} />],
              ['Source', <Badge value={record.source_type} />],
              ['Quantity', `${record.quantity ?? '—'} ${record.unit}`],
              ['Normalised', `${record.quantity_normalized ?? '—'} ${record.unit_normalized}`],
            ].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 'var(--text-sm)' }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          {!record.is_locked && (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Records() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [viewRecord, setViewRecord] = useState(null)
  const [editRecord, setEditRecord] = useState(null)
  const [toast, setToast] = useState(null)
  const [bulkLoading, setBulkLoading] = useState(false)

  const reviewStatus = searchParams.get('status') || ''
  const jobId = searchParams.get('job') || ''
  const activityType = searchParams.get('activity_type') || ''

  const fetchRecords = useCallback(async () => {
    setLoading(true)
    const params = {}
    if (reviewStatus) params.review_status = reviewStatus
    if (jobId) params.job = jobId
    if (activityType) params.activity_type = activityType
    try {
      const res = await client.get('/records/', { params })
      // Also fetch raw records for payload viewing
      const normalizedList = res.data.results || res.data

      // Enrich with raw record payload via separate calls (batch by job)
      const rawRes = await client.get('/raw-records/', {
        params: { ...(jobId ? { job: jobId } : {}) }
      })
      const rawMap = {}
      ;(rawRes.data.results || rawRes.data).forEach(r => { rawMap[r.id] = r })

      // We'd need to join by raw_record FK — stored on normalized record as raw_record id
      // For simplicity, fetch individual raw records on demand in modal
      setRecords(normalizedList)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [reviewStatus, jobId, activityType])

  useEffect(() => { fetchRecords() }, [fetchRecords])

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  async function handleApprove(id) {
    try {
      const res = await client.post(`/records/${id}/approve/`)
      setRecords(prev => prev.map(r => r.id === id ? res.data : r))
      showToast('Record approved and locked.')
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to approve.', 'error')
    }
  }

  async function handleBulkApprove() {
    if (selected.size === 0) return
    setBulkLoading(true)
    try {
      const res = await client.post('/records/bulk_approve/', { ids: [...selected] })
      showToast(`${res.data.approved} records approved.`)
      setSelected(new Set())
      fetchRecords()
    } catch (err) {
      showToast('Bulk approve failed.', 'error')
    } finally {
      setBulkLoading(false)
    }
  }

  function toggleSelect(id) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    if (selected.size === records.length) setSelected(new Set())
    else setSelected(new Set(records.map(r => r.id)))
  }

  async function openView(record) {
    // Fetch raw record for payload
    try {
      const rawId = record.raw_record ?? null
      if (rawId) {
        // Try to get from raw endpoint
        const res = await client.get(`/raw-records/${rawId}/`)
        setViewRecord({ ...record, raw_record: res.data })
      } else {
        setViewRecord(record)
      }
    } catch {
      setViewRecord(record)
    }
  }

  function handleSaveEdit(updated) {
    setRecords(prev => prev.map(r => r.id === updated.id ? updated : r))
    showToast('Record updated.')
  }

  const pendingSelected = records.filter(r => selected.has(r.id) && !r.locked_at)

  return (
    <div className="page-container fade-in">
      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>
            <span>{toast.type === 'success' ? '✅' : '❌'}</span>
            <span>{toast.msg}</span>
          </div>
        </div>
      )}

      {viewRecord && (
        <RawPayloadModal record={viewRecord} onClose={() => setViewRecord(null)} />
      )}
      {editRecord && (
        <EditModal record={editRecord} onClose={() => setEditRecord(null)} onSave={handleSaveEdit} />
      )}

      <div className="page-header">
        <h1 className="page-title">Records Review</h1>
        <p className="page-subtitle">
          Review ingested activity records, inspect suspicious rows, and approve them for audit.
        </p>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <select
          id="filter-status"
          className="form-select"
          value={reviewStatus}
          onChange={e => setSearchParams(p => { p.set('status', e.target.value); if (!e.target.value) p.delete('status'); return p })}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="suspicious">Suspicious</option>
          <option value="approved">Approved</option>
        </select>
        <select
          id="filter-activity"
          className="form-select"
          value={activityType}
          onChange={e => setSearchParams(p => { p.set('activity_type', e.target.value); if (!e.target.value) p.delete('activity_type'); return p })}
        >
          <option value="">All activities</option>
          <option value="fuel">Fuel</option>
          <option value="procurement">Procurement</option>
          <option value="electricity">Electricity</option>
          <option value="flight">Flight</option>
          <option value="hotel">Hotel</option>
          <option value="ground">Ground</option>
        </select>
        {jobId && (
          <div className="tag">
            Job #{jobId}
            <button
              onClick={() => setSearchParams(p => { p.delete('job'); return p })}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', marginLeft: 2 }}
            >✕</button>
          </div>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
          {selected.size > 0 && (
            <>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{selected.size} selected</span>
              <button
                id="bulk-approve-btn"
                className="btn btn-primary btn-sm"
                onClick={handleBulkApprove}
                disabled={bulkLoading || pendingSelected.length === 0}
              >
                {bulkLoading ? 'Approving…' : `✅ Approve ${pendingSelected.length}`}
              </button>
            </>
          )}
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
            {records.length} record{records.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div className="loader"><div className="spinner" /></div>
        ) : records.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <div className="empty-title">No records found</div>
            <div className="empty-desc">Try adjusting your filters, or upload a CSV file to ingest data.</div>
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      id="select-all-checkbox"
                      checked={selected.size === records.length && records.length > 0}
                      onChange={toggleAll}
                      style={{ cursor: 'pointer' }}
                    />
                  </th>
                  <th>ID</th>
                  <th>Source</th>
                  <th>Scope</th>
                  <th>Activity</th>
                  <th>Date / Period</th>
                  <th>Quantity</th>
                  <th>Normalised</th>
                  <th>Cost</th>
                  <th>Location</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map(record => (
                  <tr
                    key={record.id}
                    className={
                      record.review_status === 'suspicious' ? 'row-suspicious' :
                      record.review_status === 'approved' ? 'row-approved' : ''
                    }
                  >
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(record.id)}
                        onChange={() => toggleSelect(record.id)}
                        style={{ cursor: 'pointer' }}
                      />
                    </td>
                    <td className="text-mono">#{record.id}</td>
                    <td><Badge value={record.source_type} /></td>
                    <td><Badge value={record.scope} /></td>
                    <td><Badge value={record.activity_type} /></td>
                    <td className="text-mono" style={{ fontSize: 'var(--text-xs)' }}>
                      {record.occurred_on || (record.period_start && record.period_end
                        ? `${record.period_start} → ${record.period_end}`
                        : '—')}
                    </td>
                    <td style={{ fontSize: 'var(--text-sm)' }}>
                      {record.quantity != null
                        ? `${Number(record.quantity).toLocaleString()} ${record.unit}`
                        : '—'}
                    </td>
                    <td style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                      {record.quantity_normalized != null
                        ? `${Number(record.quantity_normalized).toLocaleString()} ${record.unit_normalized}`
                        : '—'}
                    </td>
                    <td style={{ fontSize: 'var(--text-sm)' }}>
                      {record.cost_amount
                        ? `${Number(record.cost_amount).toLocaleString()} ${record.currency}`
                        : '—'}
                    </td>
                    <td style={{ fontSize: 'var(--text-sm)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {record.location || record.origin
                        ? (record.origin ? `${record.origin} → ${record.destination}` : record.location)
                        : '—'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                        {record.suspicious && <span className="suspicious-dot" title="Suspicious" />}
                        <Badge value={record.review_status} />
                        {record.locked_at && <span title="Locked for audit" style={{ fontSize: '0.8rem' }}>🔒</span>}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => openView(record)}
                          title="View raw payload"
                        >
                          👁
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => setEditRecord(record)}
                          title="Edit record"
                        >
                          ✏️
                        </button>
                        {!record.locked_at && (
                          <button
                            id={`approve-btn-${record.id}`}
                            className="btn btn-sm btn-primary"
                            onClick={() => handleApprove(record.id)}
                            title="Approve & lock"
                          >
                            ✅
                          </button>
                        )}
                      </div>
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
