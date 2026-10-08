# HydroGuard

Water-network monitoring for pipeline telemetry, leak response, tank levels, maintenance, and operational analytics.

## Run & Operate

- The Replit API workflow runs `python backend/run.py` on port `8080`.
- The HydroGuard web workflow runs from `artifacts/hydroguard`.
- Local API: `python backend/run.py`; local frontend: `pnpm --filter @workspace/hydroguard run dev`.
- Python dependencies are declared in `pyproject.toml` and mirrored in `backend/requirements.txt`.
- `pnpm install` then `pnpm run typecheck` checks the TypeScript workspace.
- `cd backend && pytest` runs backend tests.
- On first API startup, SQLite tables and Pune demo data are created in `backend/hydroguard.db`.
- API reference: `/docs` and `/redoc`; API routes are under `/api`.

### Environment

- `HYDROGUARD_DATABASE_URL` (optional): SQLite URL; defaults to `backend/hydroguard.db`. A workspace-provided non-SQLite `DATABASE_URL` is intentionally ignored.
- `JWT_SECRET` (recommended): signing key. If omitted, the app uses the Replit-provided `SESSION_SECRET`; the app fails explicitly if neither is available.
- `CORS_ORIGINS` (optional): comma-separated origins; defaults to `*` for bearer-token development.
- Copy `backend/.env.example` to `backend/.env` only for local overrides. Do not commit local secrets.

## Stack

- Frontend: React, Vite, TypeScript, generated API hooks, and Recharts.
- Backend: Python 3.13, FastAPI, SQLAlchemy, SQLite, Pydantic, PyJWT, python-dotenv, and Uvicorn.
- API calls use bearer JWTs. Password sign-in supports email or mobile as the account identifier.
- Leak thresholds are configurable and stored in the database; both simulations and incoming telemetry use the same evaluator.
- SMS, WhatsApp, email notifications, and OTP delivery are not enabled.

## Repository map

- `backend/app/models.py` — SQLAlchemy tables.
- `backend/app/schemas.py` — API request validation.
- `backend/app/routers/` — auth, monitoring, alerts, operations, analytics, and simulation routes.
- `backend/app/services/sensor_processing.py` — shared telemetry classification, persistence, alerting, and pipeline state updates.
- `backend/app/seed.py` — idempotent sample network data.
- `backend/.env.example` — local environment template.
- `artifacts/hydroguard/src/App.tsx` — existing HydroGuard interface, now connected to JWT-authenticated APIs.
- `lib/api-spec/openapi.yaml` and `lib/api-client-react/` — existing TypeScript client contract.

## Product scope

The demo includes sign-up/sign-in, a monitored Pune network, telemetry intake, threshold alerts, pipelines, tanks, maps, maintenance, Water Champions, analytics, reports, and scenario simulations. No external notification provider is called.
