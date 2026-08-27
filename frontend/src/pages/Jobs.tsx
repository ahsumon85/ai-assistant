import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatApiError, Job } from '../api'

const STATUS_FILTERS = [
  { value: '', label: 'All', css: 'filter-all' },
  { value: 'new', label: 'New', css: 'filter-new' },
  { value: 'matched', label: 'Matched', css: 'filter-matched' },
  { value: 'awaiting_approval', label: 'Awaiting approval', css: 'filter-awaiting_approval' },
  { value: 'rejected', label: 'Rejected', css: 'filter-rejected' },
  { value: 'sent', label: 'Sent', css: 'filter-sent' },
] as const

const EMAIL_LIMITS = [10, 25, 50, 100, 250, 500] as const

function statusBadge(status: string) {
  return <span className={`badge badge-${status}`}>{status.replace(/_/g, ' ')}</span>
}

function scoreClass(score: number | null) {
  if (score === null) return ''
  return score >= 70 ? 'score-high' : 'score-low'
}

export default function Jobs() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('status') || ''

  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [syncError, setSyncError] = useState(false)
  const [emailConfigured, setEmailConfigured] = useState(false)
  const [syncLimit, setSyncLimit] = useState<number>(50)
  const [syncUnseenOnly, setSyncUnseenOnly] = useState(true)
  const [syncSource, setSyncSource] = useState<'all' | 'linkedin' | 'indeed'>('linkedin')
  const [syncDateFrom, setSyncDateFrom] = useState('')
  const [syncDateTo, setSyncDateTo] = useState('')

  const load = () => {
    setLoading(true)
    api.jobs(filter || undefined).then(setJobs).finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    api.emailStatus().then((s) => setEmailConfigured(s.configured)).catch(() => {})
  }, [filter])

  const setFilter = (status: string) => {
    if (status) {
      setSearchParams({ status })
    } else {
      setSearchParams({})
    }
  }

  const syncFromEmail = async () => {
    setSyncing(true)
    setSyncMsg('')
    setSyncError(false)
    try {
      const result = await api.syncEmail({
        limit: syncLimit,
        unseen_only: syncUnseenOnly,
        source: syncSource,
        mark_read: false,
        date_from: syncDateFrom || undefined,
        date_to: syncDateTo || syncDateFrom || undefined,
      })
      if (result.status === 'error') {
        setSyncError(true)
        setSyncMsg(formatApiError(result))
        return
      }
      setSyncMsg(
        result.jobs_inserted > 0
          ? `Imported ${result.jobs_inserted} job(s) from ${result.emails_fetched} email(s)`
          : result.detail || `Checked ${result.emails_fetched} email(s), no new jobs`,
      )
      load()
    } catch (err) {
      setSyncError(true)
      setSyncMsg(err instanceof Error ? err.message : 'Email sync failed')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 className="page-title" style={{ margin: 0 }}>Jobs</h1>
      </div>

      {emailConfigured ? (
        <div className="sync-panel">
          <div className="sync-panel-header">
            <span className="sync-panel-title">Email sync</span>
            <span className="sync-panel-hint">Choose how many emails to fetch and optionally filter by date</span>
          </div>
          <div className="sync-panel-fields">
            <div className="sync-field">
              <label htmlFor="sync-date-from">From date</label>
              <input
                id="sync-date-from"
                type="date"
                value={syncDateFrom}
                onChange={(e) => setSyncDateFrom(e.target.value)}
                disabled={syncing}
              />
            </div>
            <div className="sync-field">
              <label htmlFor="sync-date-to">To date</label>
              <input
                id="sync-date-to"
                type="date"
                value={syncDateTo}
                min={syncDateFrom || undefined}
                onChange={(e) => setSyncDateTo(e.target.value)}
                disabled={syncing}
                placeholder="Same day if empty"
              />
            </div>
            <div className="sync-field">
              <label htmlFor="sync-limit">Emails to sync</label>
              <select
                id="sync-limit"
                value={syncLimit}
                onChange={(e) => setSyncLimit(Number(e.target.value))}
                disabled={syncing}
              >
                {EMAIL_LIMITS.map((n) => (
                  <option key={n} value={n}>{n} emails</option>
                ))}
              </select>
            </div>
            <div className="sync-field">
              <label htmlFor="sync-source">Source</label>
              <select
                id="sync-source"
                value={syncSource}
                onChange={(e) => setSyncSource(e.target.value as typeof syncSource)}
                disabled={syncing}
              >
                <option value="linkedin">LinkedIn</option>
                <option value="indeed">Indeed</option>
                <option value="all">All sources</option>
              </select>
            </div>
            <div className="sync-field sync-field-check">
              <input
                id="sync-unseen"
                type="checkbox"
                checked={syncUnseenOnly}
                onChange={(e) => setSyncUnseenOnly(e.target.checked)}
                disabled={syncing}
              />
              <label htmlFor="sync-unseen">New emails only</label>
            </div>
            <button
              className="btn btn-primary"
              onClick={syncFromEmail}
              disabled={syncing}
            >
              {syncing ? 'Syncing...' : 'Sync emails'}
            </button>
          </div>
        </div>
      ) : (
        <p style={{ color: 'var(--warning)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          Email sync not configured — set IMAP_USER and IMAP_PASSWORD in .env (see README).
        </p>
      )}

      {syncMsg && (
        <p
          style={{
            color: syncError ? 'var(--danger)' : 'var(--muted)',
            marginBottom: '1rem',
            fontSize: '0.9rem',
            whiteSpace: 'pre-wrap',
          }}
        >
          {syncMsg}
        </p>
      )}

      <div className="filter-bar" style={{ marginBottom: '1.25rem' }}>
        {STATUS_FILTERS.map(({ value, label, css }) => (
          <button
            key={value || 'all'}
            type="button"
            className={`filter-pill ${css}${filter === value ? ' active' : ''}`}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? <p>Loading...</p> : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Company</th>
                <th>Source</th>
                <th>Score</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.title}</td>
                  <td>{job.company_name || '—'}</td>
                  <td>{job.source}</td>
                  <td className={`score ${scoreClass(job.match_score)}`}>
                    {job.match_score != null ? `${job.match_score.toFixed(0)}%` : '—'}
                  </td>
                  <td>{statusBadge(job.status)}</td>
                  <td><Link to={`/jobs/${job.id}`}>View</Link></td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--muted)' }}>No jobs yet. Sync from email to import LinkedIn alerts.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
