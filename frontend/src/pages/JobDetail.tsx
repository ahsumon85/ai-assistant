import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api, Job } from '../api'

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [hasProfile, setHasProfile] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (id) api.job(id).then(setJob)
    api.candidate().then((c) => setHasProfile(Boolean(c))).catch(() => setHasProfile(false))
  }, [id])

  const process = async () => {
    if (!id) return
    setProcessing(true)
    setMessage('Running match and preparing application — this may take a minute...')
    try {
      const result = await api.processJob(id, false)
      if (result.application_id) {
        navigate(`/applications/${result.application_id}`)
        return
      }
      if (result.task_id) {
        setMessage('Processing in background...')
        await new Promise<void>((resolve, reject) => {
          const poll = setInterval(async () => {
            try {
              const task = await api.task(result.task_id!)
              if (task.status === 'succeeded' && task.result?.application_id) {
                clearInterval(poll)
                navigate(`/applications/${task.result.application_id}`)
                resolve()
              } else if (task.status === 'failed') {
                clearInterval(poll)
                setMessage(task.error || 'Processing failed')
                reject(new Error(task.error || 'Processing failed'))
              }
            } catch (err) {
              clearInterval(poll)
              reject(err)
            }
          }, 2000)
        })
        return
      }
      setMessage(`Decision: ${result.decision}`)
      if (id) api.job(id).then(setJob)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed')
    } finally {
      setProcessing(false)
    }
  }

  if (!job) return <p>Loading...</p>

  return (
    <div>
      <Link to="/jobs" style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>← Back to jobs</Link>
      <h1 className="page-title">{job.title}</h1>
      <div className="card">
        <p><strong>Company:</strong> {job.company_name || '—'}</p>
        <p><strong>Location:</strong> {job.location || '—'}</p>
        <p><strong>Source:</strong> {job.source}</p>
        <p><strong>Status:</strong> {job.status}</p>
        {job.match_score != null && (
          <p><strong>Match score:</strong> <span className={job.match_score >= 70 ? 'score-high' : 'score-low'}>{job.match_score.toFixed(0)}%</span></p>
        )}
        {job.url && <p><a href={job.url} target="_blank" rel="noreferrer">View posting</a></p>}
      </div>
      {job.description && (
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>Description</h3>
          <p style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>{job.description}</p>
        </div>
      )}
      {job.match_reasons && job.match_reasons.length > 0 && (
        <div className="card">
          <h3>Match reasons</h3>
          <ul>{job.match_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}
      {job.status === 'new' && !hasProfile && (
        <div className="card" style={{ marginBottom: '1rem', borderColor: 'var(--warning)' }}>
          <p style={{ margin: 0 }}>
            Add your candidate profile (resume and skills) before running match.
            <Link to="/candidate" style={{ marginLeft: '0.5rem' }}>Go to My Profile</Link>
          </p>
        </div>
      )}
      {job.status === 'new' && (
        <button className="btn btn-primary" onClick={process} disabled={processing || !hasProfile}>
          {processing ? 'Processing...' : 'Run match & prepare application'}
        </button>
      )}
      {message && (
        <p style={{ marginTop: '1rem', color: message.includes('profile') ? 'var(--danger)' : 'var(--muted)', whiteSpace: 'pre-wrap' }}>
          {message}
        </p>
      )}
    </div>
  )
}
