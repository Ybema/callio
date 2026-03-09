# Callio Monorepo

Callio is organized as one repository with three components:

- `watch/` - Tender discovery and alerting platform (FastAPI + Next.js)
- `framework/` - Prepare + Review engine for proposal workflows (Python)
- `website/` - Landing page and waitlist endpoint (HTML + PHP)
- `shared/` - Cross-component contracts and integration notes

## Quickstart

### 1) Environment

Create or update the shared root environment file:

```bash
cp .env .env.local.backup
```

All components read from `/.env` in this monorepo. Call-level `.env` in
`framework/calls/<call>/` still overrides root values where present.

### 2) Watch (backend + frontend)

Backend:

```bash
cd watch/backend
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd watch/frontend
npm install
npm run dev
```

Or run db + backend from root:

```bash
docker compose up db backend
```

### 3) Framework (Prepare + Review)

```bash
cd framework
source .venv/bin/activate
python3 launch.py A --call esa-responsible-fishing
```

### 4) Website (landing page)

```bash
cd website
python3 -m http.server 8080
```

## Notes

- `watch/` and `framework/` keep separate Python environments by design.
- Website deployment remains independent from Watch/Framework runtime.
- Watch -> Prepare handoff format is defined in `shared/data_contracts.md`.
