# HydroGuard API

FastAPI backend replacing the previous Express service. Start it from the workspace root with `python backend/run.py`. The Replit API workflow binds to port `8080`; local runs use `PORT` if set and otherwise port `8000`.

## Setup

The project uses Python 3.13. Dependencies are declared in the workspace `pyproject.toml` and mirrored in `backend/requirements.txt`.

For local configuration, copy `.env.example` to `.env` inside this directory. Set `JWT_SECRET`, or let the app use Replit's `SESSION_SECRET`. Never commit real secrets. `HYDROGUARD_DATABASE_URL` defaults to a SQLite database in this directory. A workspace-managed non-SQLite `DATABASE_URL` is ignored so HydroGuard stays on the requested SQLite store. On startup, the app creates tables and adds Pune demo data only when the database has no pipelines.

## API

- Health: `GET /api/health`, `GET /api/healthz`
- OpenAPI UI: `/docs`, `/redoc`
- Auth: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `GET /api/auth/session`, `DELETE /api/auth/session`
- Network: `GET /api/dashboard`, `GET /api/map`, pipeline and sensor list/detail/create/update/delete routes under `/api/pipelines` and `/api/sensors`
- Telemetry: `POST /api/sensor-data` accepts device readings without a user JWT; the registered sensor/device identity is validated
- Alerts: `GET /api/alerts`, acknowledge, assign, resolve, and create-maintenance routes under `/api/alerts/{id}`
- Operations: `/api/tanks`, `/api/water-champions`, `/api/maintenance`, `/api/profile`, `/api/settings`
- Analytics: `GET /api/analytics?range=24h|7d|30d`, series under `/api/analytics/{kind}`, and date-bounded `GET /api/reports`
- Simulation: `POST /api/simulation/normal`, `/warning`, or `/leak`; authenticated and processed by the same rules as telemetry

Protected routes accept `Authorization: Bearer <access_token>`. No OTP, SMS, WhatsApp, email-notification, or external notification endpoints are implemented.

## Checks

From the workspace root (the test uses a temporary SQLite database):

```sh
pytest
```

The test suite uses `TestClient` and a temporary SQLite URL supplied by the test command; it does not seed a real user account or alter the development database.