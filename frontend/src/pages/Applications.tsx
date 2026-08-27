import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, Application } from '../api'

export default function Applications() {
  const [searchParams] = useSearchParams()
  const status = searchParams.get('status') || ''
  const [apps, setApps] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.applications(status || undefined).then(setApps).finally(() => setLoading(false))
  }, [status])

  return (
    <div>
      <h1 className="page-title">Applications</h1>
      <div className="actions" style={{ marginBottom: '1rem' }}>
        <Link to="/applications" className={`btn ${!status ? 'btn-primary' : 'btn-ghost'}`}>All</Link>
        <Link to="/applications?status=awaiting_approval" className={`btn ${status === 'awaiting_approval' ? 'btn-primary' : 'btn-ghost'}`}>Awaiting approval</Link>
        <Link to="/applications?status=sent" className={`btn ${status === 'sent' ? 'btn-primary' : 'btn-ghost'}`}>Sent</Link>
      </div>
      {loading ? <p>Loading...</p> : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Company</th>
                <th>Score</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {apps.map((app) => (
                <tr key={app.id}>
                  <td>{app.job_title || app.job_id}</td>
                  <td>{app.company_name || '—'}</td>
                  <td>{app.match_score != null ? `${app.match_score.toFixed(0)}%` : '—'}</td>
                  <td><span className={`badge badge-${app.status}`}>{app.status.replace(/_/g, ' ')}</span></td>
                  <td><Link to={`/applications/${app.id}`}>Review</Link></td>
                </tr>
              ))}
              {apps.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)' }}>No applications yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
