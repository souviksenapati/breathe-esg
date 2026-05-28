import { useState, useEffect, useRef } from 'react'
import client from '../api/client'

const SOURCE_TYPES = [
  {
    key: 'sap',
    label: 'SAP Export',
    icon: '🏭',
    desc: 'Fuel movements and procurement documents exported from SAP (SE16N flat-file CSV).',
    columns: 'record_type, doc_date, plant_code, quantity, unit, amount, currency, vendor, material_description, sap_doc',
    sample: 'sap_sample.csv',
  },
  {
    key: 'utility',
    label: 'Utility Data',
    icon: '⚡',
    desc: 'Electricity meter readings from utility portal CSV export.',
    columns: 'meter_id, facility_name, period_start, period_end, usage, unit, tariff',
    sample: 'utility_sample.csv',
  },
  {
    key: 'travel',
    label: 'Corporate Travel',
    icon: '✈️',
    desc: 'Business travel records (flights, hotels, ground transport) from Concur/Navan CSV export.',
    columns: 'trip_id, trip_type, booked_date, origin, destination, distance, distance_unit, cost_amount, currency, vendor, ticket_class',
    sample: 'travel_sample.csv',
  },
]

function Toast({ msg, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000)
    return () => clearTimeout(t)
  }, [onClose])
  return (
    <div className={`toast toast-${type}`}>
      <span>{type === 'success' ? '✅' : '❌'}</span>
      <span style={{ flex: 1 }}>{msg}</span>
      <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>✕</button>
    </div>
  )
}

export default function Ingestion() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [selectedType, setSelectedType] = useState('sap')
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [toasts, setToasts] = useState([])
  const fileRef = useRef()

  function addToast(msg, type = 'success') {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
  }

  function removeToast(id) {
    setToasts(t => t.filter(x => x.id !== id))
  }

  async function fetchJobs() {
    const res = await client.get('/ingestions/')
    setJobs(res.data.results || res.data)
    setLoading(false)
  }

  useEffect(() => { fetchJobs() }, [])

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) return addToast('Please select a file first.', 'error')
    setUploading(true)
    const form = new FormData()
    form.append('source_type', selectedType)
    form.append('file', file)
    try {
      const res = await client.post('/ingestions/upload/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const job = res.data
      addToast(`Ingested ${job.parsed_rows}/${job.total_rows} rows (${job.failed_rows} failed, ${job.suspicious_rows} suspicious)`)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      fetchJobs()
    } catch (err) {
      addToast(err.response?.data?.error || 'Upload failed.', 'error')
    } finally {
      setUploading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const currentSource = SOURCE_TYPES.find(s => s.key === selectedType)

  function jobStatusBadge(status) {
    const map = { parsed: 'badge-parsed', failed: 'badge-failed', received: 'badge-received' }
    return <span className={`badge ${map[status] || ''}`}>{status}</span>
  }

  function sourceTypeBadge(type) {
    const map = { sap: 'badge-sap', utility: 'badge-utility', travel: 'badge-travel' }
    return <span className={`badge ${map[type] || ''}`}>{type}</span>
  }

  return (
    <div className="page-container fade-in">
      <div className="toast-container">
        {toasts.map(t => (
          <Toast key={t.id} msg={t.msg} type={t.type} onClose={() => removeToast(t.id)} />
        ))}
      </div>

      <div className="page-header">
        <h1 className="page-title">Ingest Data</h1>
        <p className="page-subtitle">Upload CSV files from your SAP system, utility portal, or travel platform.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)', marginBottom: 'var(--space-8)' }}>
        {/* Upload form */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Upload CSV</h2>
          </div>
          <div className="card-body">
            {/* Source selector */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
              {SOURCE_TYPES.map(src => (
                <button
                  key={src.key}
                  id={`source-type-${src.key}`}
                  className="btn btn-secondary"
                  style={{
                    flexDirection: 'column',
                    alignItems: 'center',
                    padding: 'var(--space-4)',
                    gap: 'var(--space-2)',
                    background: selectedType === src.key ? 'var(--accent-dim)' : '',
                    borderColor: selectedType === src.key ? 'var(--border-active)' : '',
                    color: selectedType === src.key ? 'var(--accent)' : '',
                  }}
                  onClick={() => setSelectedType(src.key)}
                >
                  <span style={{ fontSize: '1.5rem' }}>{src.icon}</span>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>{src.label}</span>
                </button>
              ))}
            </div>

            {/* Source info */}
            <div style={{
              background: 'var(--bg-glass)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-4)',
              marginBottom: 'var(--space-6)',
              fontSize: 'var(--text-sm)',
            }}>
              <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>{currentSource.desc}</p>
              <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                <strong>Expected columns:</strong> <code style={{ color: 'var(--text-secondary)' }}>{currentSource.columns}</code>
              </p>
            </div>

            <form onSubmit={handleUpload}>
              <div
                className={`upload-zone${dragOver ? ' drag-over' : ''}`}
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                style={{ marginBottom: 'var(--space-4)' }}
              >
                <input
                  type="file"
                  ref={fileRef}
                  accept=".csv,.txt"
                  onChange={e => setFile(e.target.files[0])}
                  id="file-upload-input"
                />
                <div className="upload-icon">📁</div>
                <div className="upload-title">
                  {file ? file.name : 'Drop your CSV here or click to browse'}
                </div>
                <div className="upload-hint">
                  {file
                    ? `${(file.size / 1024).toFixed(1)} KB — ready to upload`
                    : 'Accepts .csv files up to 10MB'}
                </div>
              </div>

              <button
                type="submit"
                id="upload-submit-btn"
                className="btn btn-primary btn-lg w-full"
                disabled={uploading || !file}
              >
                {uploading ? '⏳ Processing…' : `⬆️ Upload ${currentSource.label}`}
              </button>
            </form>
          </div>
        </div>

        {/* Sample data info */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Sample Data Reference</h2>
          </div>
          <div className="card-body">
            <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-6)' }}>
              Sample CSV files are included in the <code>sample_data/</code> directory of this repository. Use them to test the ingestion pipeline.
            </p>
            {SOURCE_TYPES.map(src => (
              <div key={src.key} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-4)',
                padding: 'var(--space-4)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border)',
                marginBottom: 'var(--space-3)',
                background: 'var(--bg-glass)',
              }}>
                <span style={{ fontSize: '1.5rem' }}>{src.icon}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: 'var(--space-1)' }}>{src.label}</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{src.sample}</div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>{src.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Jobs history */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Ingestion History</h2>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{jobs.length} job{jobs.length !== 1 ? 's' : ''}</span>
        </div>
        {loading ? (
          <div className="loader"><div className="spinner" /></div>
        ) : jobs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📂</div>
            <div className="empty-title">No jobs yet</div>
            <div className="empty-desc">Upload a CSV to start ingesting data.</div>
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Source Type</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Parsed</th>
                  <th>Failed</th>
                  <th>Suspicious</th>
                  <th>Approved</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.id}>
                    <td className="text-mono">#{job.id}</td>
                    <td>{sourceTypeBadge(job.source_type)}</td>
                    <td>{jobStatusBadge(job.status)}</td>
                    <td>{job.total_rows}</td>
                    <td style={{ color: 'var(--accent)' }}>{job.parsed_rows}</td>
                    <td style={{ color: job.failed_rows > 0 ? 'var(--red)' : 'var(--text-muted)' }}>{job.failed_rows}</td>
                    <td style={{ color: job.suspicious_rows > 0 ? 'var(--amber)' : 'var(--text-muted)' }}>{job.suspicious_rows}</td>
                    <td style={{ color: 'var(--accent)' }}>{job.approved_rows}</td>
                    <td className="text-mono">{new Date(job.created_at).toLocaleString()}</td>
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
