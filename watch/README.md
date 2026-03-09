# FundWatch

**Funding opportunity monitoring SaaS — by [Sustainovate AS](https://sustainovate.com)**

Users subscribe to monitor funding call sources. FundWatch scrapes or hits APIs on a schedule and emails alerts when new calls appear.

## Stack

- **Backend:** FastAPI + PostgreSQL + SQLAlchemy (async)
- **Scraping:** httpx + Playwright (headless Chromium for JS-heavy sites)
- **Email:** Resend
- **Payments:** Stripe Subscriptions
- **Scheduler:** APScheduler (runs every 6h)
- **Infra:** Docker Compose

## Plans

| Plan | Sources | Alert frequency | Price |
|------|---------|-----------------|-------|
| Free | 3 | Weekly | €0 |
| Pro | Unlimited | Daily | €29/mo |
| Team | Unlimited | Daily + shared lists | €99/mo |

## Getting Started

```bash
cp .env.example .env
# fill in .env values
docker compose up
```

API available at `http://localhost:8000`
Docs at `http://localhost:8000/docs`

## Database Migrations

FundWatch now uses Alembic for schema evolution. Apply migrations before starting the app:

```bash
cd backend
python3 -m alembic upgrade head
```

Optional local bootstrap fallback (not recommended for ongoing schema changes):

```bash
DB_AUTO_CREATE_TABLES=true python3 -m uvicorn app.main:app --reload --port 8000
```

## API Routes

- `POST /auth/register` — create account
- `POST /auth/login` — get token
- `GET /sources/` — list your sources (supports filters + pagination)
- `POST /sources/` — add a source
- `DELETE /sources/{id}` — remove a source
- `POST /billing/checkout/{plan}` — upgrade to pro/team
- `POST /billing/portal` — manage billing
- `POST /billing/webhook` — Stripe webhook endpoint

## Future Data Model: Call Requirements

Call requirements (eligibility, budget constraints, consortium rules, etc.) are intentionally deferred.
When that feature starts, we will run a dedicated design pass to choose the right storage model
(normalized requirement items vs structured JSON) and extraction pipeline.
