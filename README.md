# JobFlow — Production Setup

AI-powered job matching and application assistant with React dashboard, JWT auth, PostgreSQL, Redis workers, and Gmail/ATS integrations.

## Architecture

```
React UI → FastAPI (JWT) → PostgreSQL
                ↓
         Redis + ARQ Worker → AI Agents → Match Engine → Human Approval → Email
                ↑
    Greenhouse / Lever / Email / Webhook ingest
```

## Quick start (Docker — recommended)

```bash
cp .env.example .env
docker compose up -d
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Postgres | localhost:5432 |
| Redis    | localhost:6379 |

**Default login:** `admin@jobflow.example` / `admin123`

## Local development (without Docker)

### Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Start Postgres + Redis (or use docker compose up -d db redis)
export DATABASE_URL=postgresql+psycopg://jobflow:jobflow@localhost:5432/jobflow
export REDIS_URL=redis://localhost:6379/0

uvicorn jobflow.api.main:app --reload
jobflow-worker   # separate terminal for background jobs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Features implemented

### Phase 1 — Product foundation
- React dashboard (jobs, applications, approval, candidate profile)
- PostgreSQL as default database
- FastAPI REST API with OpenAPI docs

### Phase 2 — Real integrations
- Greenhouse & Lever webhook endpoints with signature verification
- Gmail OAuth connect flow + send via Gmail API
- Outlook OAuth + Microsoft Graph sendMail
- Background job processing via ARQ + Redis
- Email / generic webhook ingest

### Phase 3 — Production readiness
- JWT authentication (register, login, protected routes)
- Rate limiting (slowapi)
- Structured logging
- Default admin bootstrap
- Docker Compose full stack (db, redis, api, worker, frontend)
- API integration tests

## Key API endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/login` | Get JWT token |
| `GET /api/dashboard/stats` | Dashboard metrics |
| `GET /api/jobs` | List jobs |
| `POST /api/jobs/{id}/process` | Run match pipeline |
| `GET /api/applications/{id}/approval-queue` | Review draft |
| `POST /api/applications/{id}/approve` | Human approval + send |
| `POST /api/integrations/webhooks/greenhouse` | ATS webhook |
| `GET /api/integrations/gmail/connect` | Start Gmail OAuth |

## Get jobs from email

JobFlow can pull job alerts from your inbox via **IMAP** (Gmail, Outlook, etc.).

### 1. Configure IMAP in `.env`

```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your.email@gmail.com
IMAP_PASSWORD=your-gmail-app-password
IMAP_FOLDER=INBOX
```

**Gmail:** use an [App Password](https://support.google.com/accounts/answer/185833) (requires 2FA).

**Outlook:** `IMAP_HOST=outlook.office365.com`, use your Microsoft account password or app password.

### 2. Sync jobs

**UI:** Jobs page → **Sync from email**

**CLI:**
```bash
jobflow sync-email
```

**API:**
```bash
curl -X POST http://localhost:8000/api/ingest/email/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "unseen_only": true}'
```

### Supported email sources

| Source | Detected by |
|--------|-------------|
| LinkedIn job alerts | Sender / subject |
| Indeed job alerts | Sender / subject |
| Other alerts | Generic parser (Job/Company/Location fields) |

Emails are filtered by sender (`IMAP_JOB_SENDERS`) and subject keywords (`IMAP_SUBJECT_KEYWORDS`). Parsed jobs are deduplicated and saved to the database.

---

## Configuration

See `.env.example` for all settings. Important:

- `JWT_SECRET_KEY` — change in production
- `LLM_PROVIDER` — `ollama` (local, default) or `openai`
- `OLLAMA_MODEL` — e.g. `qwen3:8b` (requires `ollama serve` running)
- `OPENAI_API_KEY` — optional; use with `LLM_PROVIDER=openai`
- `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` — for real email send
- `GREENHOUSE_WEBHOOK_SECRET` / `LEVER_WEBHOOK_SECRET` — webhook HMAC validation

## Tests

```bash
pytest
```

## CLI (still available)

```bash
jobflow init-db
jobflow sync-email --linkedin
jobflow list-jobs
```
