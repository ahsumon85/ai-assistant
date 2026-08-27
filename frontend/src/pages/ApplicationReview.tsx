import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api, ApplicationDetail } from '../api'

export default function ApplicationReview() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [app, setApp] = useState<ApplicationDetail | null>(null)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (id) api.applicationDetail(id).then(setApp)
  }, [id])

  const approve = async () => {
    if (!id) return
    setLoading(true)
    setError('')
    try {
      await api.approve(id, notes)
      navigate('/applications?status=sent')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  const reject = async () => {
    if (!id) return
    setLoading(true)
    try {
      await api.reject(id, notes)
      navigate('/applications')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  if (!app) return <p>Loading...</p>

  return (
    <div>
      <Link to="/applications" style={{ color: 'var(--muted)' }}>← Back</Link>
      <h1 className="page-title">Review application</h1>
      <div className="card">
        <h2>{app.job_title} at {app.company}</h2>
        <p>Match score: <strong className={app.match_score && app.match_score >= 70 ? 'score-high' : 'score-low'}>{app.match_score?.toFixed(0)}%</strong></p>
        <p>Status: {app.status}</p>
        {app.missing_skills && app.missing_skills.length > 0 && (
          <p>Missing skills: {app.missing_skills.join(', ')}</p>
        )}
      </div>
      <div className="card">
        <h3>Email draft</h3>
        <p><strong>To:</strong> {app.email_to}</p>
        <p><strong>Subject:</strong> {app.email_subject}</p>
        <div className="preview-box">{app.email_body}</div>
      </div>
      {app.cover_letter && (
        <div className="card">
          <h3>Cover letter</h3>
          <div className="preview-box">{app.cover_letter}</div>
        </div>
      )}
      {app.tailored_resume && (
        <div className="card">
          <h3>Tailored resume</h3>
          <div className="preview-box">{app.tailored_resume}</div>
        </div>
      )}
      {app.status === 'awaiting_approval' && (
        <>
          <div className="form-group">
            <label>Notes (optional)</label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button className="btn btn-success" onClick={approve} disabled={loading}>Approve & send</button>
            <button className="btn btn-danger" onClick={reject} disabled={loading}>Reject</button>
          </div>
        </>
      )}
    </div>
  )
}
