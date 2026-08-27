import { useEffect, useState } from 'react'
import { api, Candidate } from '../api'

export default function CandidatePage() {
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [form, setForm] = useState<Partial<Candidate>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.candidate().then((c) => {
      setCandidate(c)
      if (c) setForm(c)
    }).finally(() => setLoading(false))
  }, [])

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const skills = typeof form.skills === 'string'
        ? (form.skills as unknown as string).split(',').map((s) => s.trim()).filter(Boolean)
        : form.skills
      const payload = { ...form, skills }
      const result = candidate
        ? await api.updateCandidate(payload)
        : await api.createCandidate(payload as Candidate)
      setCandidate(result)
      setMessage('Profile saved!')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p>Loading...</p>

  return (
    <div>
      <h1 className="page-title">My candidate profile</h1>
      {!candidate && (
        <p style={{ color: 'var(--warning)', marginBottom: '1rem' }}>
          A profile is required to match jobs and prepare applications. Add your resume and skills below.
        </p>
      )}
      <div className="card">
        <form onSubmit={save}>
          <div className="form-group">
            <label>Full name</label>
            <input value={form.full_name || ''} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })} required disabled={!!candidate} />
          </div>
          <div className="form-group">
            <label>Headline</label>
            <input value={form.headline || ''} onChange={(e) => setForm({ ...form, headline: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Location</label>
            <input value={form.location || ''} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Skills (comma-separated)</label>
            <input value={Array.isArray(form.skills) ? form.skills.join(', ') : ''} onChange={(e) => setForm({ ...form, skills: e.target.value.split(',').map((s) => s.trim()) })} />
          </div>
          <div className="form-group">
            <label>Resume text</label>
            <textarea value={form.resume_text || ''} onChange={(e) => setForm({ ...form, resume_text: e.target.value })} rows={12} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Save profile'}
          </button>
          {message && <p style={{ marginTop: '1rem', color: 'var(--success)' }}>{message}</p>}
        </form>
      </div>
    </div>
  )
}
