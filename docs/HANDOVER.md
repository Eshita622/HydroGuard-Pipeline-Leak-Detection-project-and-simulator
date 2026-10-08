# HydroGuard Handover Document

## Overview
HydroGuard is a complete system for rural water network monitoring. This document serves to explain the core workflow, codebase architecture, and authentication mechanisms for the next maintainer.

## 1. Core Workflow
The HydroGuard ecosystem follows a structured incident lifecycle:

1. **Sensor (Telemetry Generation):** ESP32 flow, pressure, and tank level sensors submit telemetry every minute to the backend via `POST /api/sensor-data`. Simulator interactions also invoke this endpoint with `deviceId: "SIMULATION"`.
2. **Detection (Risk Assessment):** The backend evaluates the telemetry against predefined threshold settings. Readings exceeding thresholds receive classifications (`WARNING`, `LEAK`) and risk severity levels (`LOW`, `MEDIUM`, `HIGH`).
3. **Alert (Notification):** A classified `LEAK` or `WARNING` generates or updates an `Alert` in the database. SMS notifications are simulated for critical thresholds.
4. **Water Champion (Dispatch):** A local Water Champion is assigned to the `Alert` through the Dashboard (`POST /api/alerts/{id}/assign`). Their status shifts from `AVAILABLE` to `ON_SITE`. A `MaintenanceLog` work order is generated to track repair steps.
5. **Resolution (Restoration):** Once the repair is complete, the Champion or Operator resolves the alert (`POST /api/alerts/{id}/resolve`). The Champion is marked `AVAILABLE` again, metrics update, and the alert is closed.

## 2. Important Files & Folders

### Backend (Python/FastAPI)
- `backend/app/main.py`: Entrypoint for FastAPI server and CORS setup.
- `backend/app/models.py`: SQLAlchemy schemas representing the Database structure (Pipelines, Sensors, Alerts, Champions, etc.).
- `backend/app/routers/`: Individual routers mapping to specific business logic:
  - `analytics.py`: Real-time aggregations for the Analytics dashboard and date-range bucketing.
  - `alerts.py`: Assignment and resolution workflows.
  - `monitoring.py`: Telemetry ingestion.
- `backend/app/services/leak_detection.py`: Mathematical rules determining `WARNING`/`LEAK` risk classifications based on sensor values.
- `backend/app/seed.py`: Database populator script for default pipeline network.
- `backend/scripts/seed_history.py`: Populates historical demo telemetry for Analytics charts.
- `backend/tests/test_api.py`: Pytest suite exercising the end-to-end telemetry, alerting, simulation, and analytic flows.

### Frontend (React/TypeScript)
- `artifacts/hydroguard/src/App.tsx`: Main React component housing routing, layout shell, and top-level pages (Dashboard, Alerts, Analytics).
- `artifacts/hydroguard/src/lib/api-client.ts`: Shared API client configured to automatically include the `Authorization` Bearer token.
- `artifacts/hydroguard/src/lib/i18n.tsx`: Custom Context Provider managing English and Hindi (`हिंदी`) translation keys.
- `artifacts/hydroguard/public/simulator.html`: A standalone HTML/JS visualization allowing interactive pipeline leak simulations by clicking SVGs.

## 3. Authentication Overview
HydroGuard employs standard JWT (JSON Web Token) authentication.
- **Login/Register:** `POST /api/auth/register` and `POST /api/auth/login`.
- **Token Generation:** Handled in `backend/app/auth.py` via `PyJWT`. Secrets are loaded from `.env` `JWT_SECRET`. 
- **Storage:** Frontend persists the JWT token in `localStorage` under the key `hydroguard_token`.
- **Protected Routes:** Both React and FastAPI restrict critical operations to authenticated operators. The `get_current_user` FastAPI dependency intercepts incoming requests, verifying the Bearer token and ensuring user role authorization.

## 4. Bilingual Implementation (English/Hindi)
HydroGuard implements a custom, zero-dependency `i18n` context (`src/lib/i18n.tsx`) for user accessibility.
- **Provider:** The `<LanguageProvider>` wraps the React app, persisting user selection in `localStorage`.
- **Hook:** Functional components utilize `const { t } = useLanguage()` to access localized strings.
- **Keys:** Translation mappings are defined in the `translations` object inside `i18n.tsx`. 
- **Guideline:** Always use `t("key")` for static user-facing text, ensuring both English and Hindi users experience full accessibility.

## 5. Recent System Modifications (Changelog)
- **Analytics Stability**: The Analytics API endpoint was rewritten to correctly return a structured JSON response (`kpis`, `flowPressure`, `alertsByRisk`, etc.). The frontend `App.tsx` handles old cached responses gracefully without crashing.
- **Simulator Isolation**: Data emitted from the `simulator.html` frontend is now explicitly isolated so it no longer pollutes live Field Telemetry.
- **Champion Seeding & Syncing**: Unused, hard-coded champions were eliminated from `seed.py`. The assignment workflow (`POST /api/alerts/{id}/assign`) now correctly updates the Champion's status to `ON_SITE`.
- **Localization Patches**: Missing Hindi translations (e.g., `simDetail`) and React `useLanguage()` hook dependencies were fixed across UI alert components to prevent runtime crashes.
