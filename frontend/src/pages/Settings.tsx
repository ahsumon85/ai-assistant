import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'

export default function Settings() {
  const [status, setStatus] = useState<{ gmail_connected: boolean; outlook_connected: boolean; gmail_email: string | null } | null>(null)
  const [searchParams] = useSearchParams()
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.integrationStatus().then(setStatus)
    if (searchParams.get('gmail') === 'connected') setMessage('Gmail connected successfully!')
    if (searchParams.get('outlook') === 'connected') setMessage('Outlook connected successfully!')
  }, [searchParams])

  const connectGmail = async () => {
    try {
      const { auth_url } = await api.gmailConnect()
      window.location.href = auth_url
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Gmail not configured on server')
    }
  }

  return (
    <div>
      <h1 className="page-title">Settings</h1>
      {message && <div className="card" style={{ borderColor: 'var(--success)' }}>{message}</div>}
      <div className="card">
        <h3 style={{ marginBottom: '1rem' }}>Email integrations</h3>
        <p style={{ color: 'var(--muted)', marginBottom: '1rem' }}>
          Connect Gmail to send real application emails after approval. Without this, emails run in dry-run mode.
        </p>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div>
            <strong>Gmail</strong>
            <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
              {status?.gmail_connected ? `Connected (${status.gmail_email || 'account'})` : 'Not connected'}
            </p>
          </div>
          {!status?.gmail_connected && (
            <button className="btn btn-primary" onClick={connectGmail}>Connect Gmail</button>
          )}
        </div>
      </div>
      <div className="card">
        <h3 style={{ marginBottom: '0.75rem' }}>Webhook endpoints</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
          Configure these in your ATS dashboards:
        </p>
        <ul style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
          <li>Greenhouse: <code>POST /api/integrations/webhooks/greenhouse</code></li>
          <li>Lever: <code>POST /api/integrations/webhooks/lever</code></li>
          <li>Generic: <code>POST /api/ingest/webhook</code> (requires auth + API key)</li>
        </ul>
      </div>
    </div>
  )
}
