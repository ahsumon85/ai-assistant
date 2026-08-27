import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Dashboard() {
  const [stats, setStats] = useState<Awaited<ReturnType<typeof api.stats>> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.stats().then(setStats).finally(() => setLoading(false))
  }, [])

  if (loading) return <p>Loading dashboard...</p>

  return (
    <div>
      <h1 className="page-title">Dashboard</h1>
      <div className="stats-grid">
        <div className="stat-card"><div className="label">Total Jobs</div><div className="value">{stats?.total_jobs ?? 0}</div></div>
        <div className="stat-card"><div className="label">New</div><div className="value">{stats?.new_jobs ?? 0}</div></div>
        <div className="stat-card"><div className="label">Matched</div><div className="value">{stats?.matched_jobs ?? 0}</div></div>
        <div className="stat-card"><div className="label">Rejected</div><div className="value">{stats?.rejected_jobs ?? 0}</div></div>
        <div className="stat-card"><div className="label">Awaiting Approval</div><div className="value">{stats?.awaiting_approval ?? 0}</div></div>
        <div className="stat-card"><div className="label">Sent</div><div className="value">{stats?.sent_applications ?? 0}</div></div>
      </div>
      <div className="card">
        <h3 style={{ marginBottom: '1rem' }}>Quick actions</h3>
        <div className="actions">
          <Link to="/jobs" className="btn btn-primary">View jobs</Link>
          <Link to="/applications?status=awaiting_approval" className="btn btn-ghost">Review applications</Link>
          <Link to="/candidate" className="btn btn-ghost">Edit profile</Link>
        </div>
      </div>
    </div>
  )
}
