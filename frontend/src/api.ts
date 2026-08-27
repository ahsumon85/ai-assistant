const API_BASE = import.meta.env.VITE_API_URL || ''

function getToken(): string | null {
  return localStorage.getItem('jobflow_token')
}

export function setToken(token: string) {
  localStorage.setItem('jobflow_token', token)
}

export function clearToken() {
  localStorage.removeItem('jobflow_token')
}

export function formatApiError(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const d = detail as { detail?: unknown; hint?: string; message?: string }
    const main =
      typeof d.detail === 'string'
        ? d.detail
        : d.detail && typeof d.detail === 'object'
          ? formatApiError(d.detail)
          : d.message
    if (main && d.hint) return `${main}\n\n${d.hint}`
    if (main) return String(main)
  }
  return 'Request failed'
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(formatApiError(err.detail))
  }
  return res.json()
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, full_name?: string) =>
    request<{ access_token: string }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    }),
  me: () => request<{ id: string; email: string; full_name: string | null }>('/api/auth/me'),

  stats: () =>
    request<{
      total_jobs: number
      new_jobs: number
      matched_jobs: number
      rejected_jobs: number
      awaiting_approval: number
      sent_applications: number
      pending_tasks: number
    }>('/api/dashboard/stats'),

  jobs: (status?: string) =>
    request<Job[]>(`/api/jobs${status ? `?status=${status}` : ''}`),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  processJob: (id: string, async_mode = false) =>
    request<{ status?: string; task_id?: string; decision?: string; application_id?: string }>(
      `/api/jobs/${id}/process`,
      { method: 'POST', body: JSON.stringify({ async_mode }) },
    ),

  applications: (status?: string) =>
    request<Application[]>(`/api/applications${status ? `?status=${status}` : ''}`),
  applicationDetail: (id: string) => request<ApplicationDetail>(`/api/applications/${id}/approval-queue`),
  approve: (id: string, notes?: string) =>
    request(`/api/applications/${id}/approve`, { method: 'POST', body: JSON.stringify({ notes }) }),
  reject: (id: string, notes?: string) =>
    request(`/api/applications/${id}/reject`, { method: 'POST', body: JSON.stringify({ notes }) }),

  candidate: () => request<Candidate | null>('/api/candidates/me'),
  updateCandidate: (data: Partial<Candidate>) =>
    request<Candidate>('/api/candidates/me', { method: 'PUT', body: JSON.stringify(data) }),
  createCandidate: (data: Partial<Candidate>) =>
    request<Candidate>('/api/candidates', { method: 'POST', body: JSON.stringify(data) }),

  integrationStatus: () =>
    request<{ gmail_connected: boolean; outlook_connected: boolean; gmail_email: string | null }>(
      '/api/integrations/status',
    ),
  gmailConnect: () => request<{ auth_url: string }>('/api/integrations/gmail/connect'),

  syncEmail: (opts?: {
    limit?: number
    unseen_only?: boolean
    source?: 'all' | 'linkedin' | 'indeed'
    mark_read?: boolean
    date_from?: string
    date_to?: string
  }) =>
    request<{
      status: string
      emails_fetched: number
      jobs_inserted: number
      jobs_parsed?: number
      skipped_duplicates?: number
      detail?: string
      hint?: string
    }>('/api/ingest/email/sync', {
      method: 'POST',
      body: JSON.stringify({
        limit: opts?.limit ?? 50,
        unseen_only: opts?.unseen_only ?? true,
        source: opts?.source ?? 'all',
        mark_read: opts?.mark_read ?? false,
        ...(opts?.date_from ? { date_from: opts.date_from } : {}),
        ...(opts?.date_to ? { date_to: opts.date_to } : {}),
      }),
    }),

  emailStatus: () =>
    request<{ configured: boolean; host: string; user: string | null; folder: string }>(
      '/api/ingest/email/status',
    ),

  task: (id: string) =>
    request<{ id: string; status: string; result?: Record<string, unknown>; error?: string }>(
      `/api/tasks/${id}`,
    ),
}

export interface Job {
  id: string
  title: string
  source: string
  location: string | null
  status: string
  match_score: number | null
  company_name: string | null
  description?: string
  match_reasons?: string[]
  missing_skills?: string[]
  url?: string
}

export interface Application {
  id: string
  job_id: string
  status: string
  match_score: number | null
  job_title: string | null
  company_name: string | null
  email_subject: string | null
  created_at: string
}

export interface ApplicationDetail {
  id: string
  status: string
  job_title: string | null
  company: string | null
  match_score: number | null
  match_reasons: string[] | null
  missing_skills: string[] | null
  email_to: string | null
  email_subject: string | null
  email_body: string | null
  cover_letter: string | null
  tailored_resume: string | null
  recruiter_notes: string | null
}

export interface Candidate {
  id: string
  full_name: string
  email: string
  phone?: string
  headline?: string
  location?: string
  resume_text?: string
  skills?: string[]
  preferences?: Record<string, unknown>
}
