# HydroGuard - Pipeline Protection & Water Network Operations

[![TypeScript Check](https://img.shields.io/badge/TypeScript-Strict_Checked-blue.svg)](https://www.typescriptlang.org/)
[![Python Tests](https://img.shields.io/badge/Pytest-6_Passed-brightgreen.svg)](https://docs.pytest.org/)
[![Bilingual i18n](https://img.shields.io/badge/Languages-English_%7C_%E0%A4%B9%E0%A4%BF%E0%A4%82%E0%A4%A6%E0%A5%80-teal.svg)](#bilingual-support-english--hindi)

**HydroGuard** is an eco-engineered, community-first rural water network monitoring, leak detection, and incident response platform designed for 9 village zones. It combines real-time edge telemetry monitoring, rule-based leak classification, automated incident triage, Water Champion field dispatch, environmental Life Cycle Assessment (LCA) tracking, and bilingual (English & Hindi) accessibility.

---

## Table of Contents
- [Project Overview & Objectives](#project-overview--objectives)
- [Tech Stack](#tech-stack)
- [Main Features & Modules](#main-features--modules)
- [Prerequisites & System Requirements](#prerequisites--system-requirements)
- [Environment Variables](#environment-variables)
- [Quick Start Guide](#quick-start-guide)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup](#2-frontend-setup)
- [Ports & Access URLs](#ports--access-urls)
- [Running Tests & Typechecks](#running-tests--typechecks)
- [Hardware Demonstrator (Simulator)](#hardware-demonstrator-simulator)
- [Project Structure](#project-structure)
- [Handover Documentation](#handover-documentation)

---

## Project Overview & Objectives

Rural water distribution networks suffer from high water loss (Non-Revenue Water) due to undetected leaks, pressure surges, and delayed dispatch of repair crews. HydroGuard solves this by providing:
1. **Continuous Telemetry Monitoring**: Real-time flow rate ($L/min$), pressure ($bar$), and tank capacity ($\%$) across 9 monitored pipeline zones.
2. **Automated Leak Detection**: Rule-based threshold processing categorizing readings into `NORMAL`, `LOW`, `MEDIUM`, or `HIGH` risk.
3. **Field Team Coordination**: Direct dispatch of local **Water Champions** with live status sync (`AVAILABLE` $\leftrightarrow$ `ON_SITE`).
4. **Environmental Impact Tracking**: ISO 14040/44 Life Cycle Assessment (LCA) tracking carbon abatement ($42.6\text{ kg CO}_2\text{e/yr}$), energy efficiency, and water conserved.
5. **Community Accessibility**: Dual-language UI in **English** and **Hindi (`हिंदी`)** selectable directly at the login screen.

---

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Server**: Uvicorn
- **Database**: SQLite (`backend/hydroguard.db`) via SQLAlchemy 2.0
- **Authentication**: JWT tokens (PyJWT) with Argon2/Passlib password hashing (`pwdlib`)
- **Validation**: Pydantic v2
- **Testing**: pytest

### Frontend
- **Framework**: React 19 & TypeScript 5.9
- **Build Tool**: Vite
- **Routing**: React Router DOM v7
- **State & Data Fetching**: TanStack React Query v5
- **Icons & Styling**: Lucide React, Vanilla CSS, Tailwind CSS v4
- **Charts & Maps**: Recharts, Leaflet / React-Leaflet
- **Localization**: Custom context-based i18n (`src/lib/i18n.tsx`)

---

## Main Features & Modules

1. **Network Overview (Dashboard)**: System condition status, active flow meters, online sensors, live risk ribbon, and estimated vs. simulated water loss.
2. **Incident Response (Alerts)**: Live feed, risk filters (Low/Med/High), mock SMS recipient log, triage modals, assignment, and resolution actions.
3. **Pipeline Map**: Interactive Leaflet geography map showing 9 village pipeline routes & sensor node status indicators.
4. **Analytics**: Reporting window trends (24h / 7d / 30d) for flow, pressure, tank capacity, leak events, sensor uptime, and mean response latency.
5. **Maintenance (Field Work Orders)**: Work order register, priority tracking, repair status lifecycle (`Pending` $\rightarrow$ `Assigned` $\rightarrow$ `In Progress` $\rightarrow$ `Completed`).
6. **Water Champions**: On-the-ground team roster, live availability status (`Available`, `On site`, `Off duty`), workload, and response performance tracking.
7. **Environmental LCA & Sustainability**: ISO 14040/44 verified Life Cycle Assessment, carbon footprint, water saved, energy load, "Without vs With HydroGuard" comparison matrix, and circular system benefits.
8. **Reports & System Settings**: Date-bounded CSV export reports, rule-based threshold management (flow rate & pressure limits), and registered ESP32 devices list.
9. **Hardware Demonstrator (Simulator)**: 9-pipe interactive visual demonstrator (`simulator.html`) and `/simulation` dev lab with hammer and fix-it tools.
10. **Bilingual i18n System**: Full English and Hindi (`हिंदी`) language switcher at login and top navigation bar.

---

## Prerequisites & System Requirements

- **Node.js**: v18.0.0 or higher (Node 20+ recommended)
- **Package Manager**: `pnpm` v9+ (or `npm`)
- **Python**: v3.10.0 or higher
- **Operating System**: Windows, macOS, or Linux

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` (or configure system environment variables):

```env
# Database connection string (SQLite default)
HYDROGUARD_DATABASE_URL=sqlite:///./hydroguard.db

# Secret key for JWT token signing (Min 32 characters in production)
JWT_SECRET=hydroguard-dev-secret-key-change-in-production-min-32-chars

# Allowed CORS origins
CORS_ORIGINS=*

# Optional Port Overrides
PORT=8000
```

> **Note**: If `JWT_SECRET` is omitted in development mode, a safe default key is automatically fallback-loaded by `backend/app/config.py`.

---

## Quick Start Guide

### 1. Backend Setup

Open a terminal in the project root:

```bash
# Navigate to backend directory
cd backend

# (Optional) Create and activate a Python virtual environment
python -m venv venv

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
# source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Seed the database with initial 9 zones, sensors, pipelines, and champions
python app/seed.py

# Generate 30 days of historical demo data for Analytics
python scripts/seed_history.py

# Start the FastAPI server
python run.py
```

The FastAPI backend will start running on **`http://localhost:8000`**.

---

### 2. Frontend Setup

Open a second terminal in the project root:

```bash
# Install root dependencies
pnpm install

# Navigate to the HydroGuard React application directory
cd artifacts/hydroguard

# Start the Vite development server
pnpm run dev
```

The React frontend will start running on **`http://localhost:5173`**.

---

## Ports & Access URLs

| Application / Service | Service URL | Description |
| :--- | :--- | :--- |
| **Frontend Web App** | `http://localhost:5173` | React main operational interface |
| **Hardware Simulator** | `http://localhost:5173/simulator.html` | Interactive 9-pipe demonstrator |
| **Backend API Server** | `http://localhost:8000` | FastAPI REST API backend |
| **API Documentation** | `http://localhost:8000/docs` | Interactive Swagger API docs |
| **API Health Check** | `http://localhost:8000/api/healthz` | Backend health check endpoint |

---

## Running Tests & Typechecks

### 1. Run Backend Python Tests

```bash
cd backend
pytest
```
*Expected Result*: `6 passed`

### 2. Run Frontend TypeScript Typecheck

```bash
cd artifacts/hydroguard
npx tsc --noEmit
```
*Expected Result*: `0 errors`

---

## Hardware Demonstrator (Simulator)

HydroGuard includes a standalone interactive hardware demonstrator at **`http://localhost:5173/simulator.html`**:
- **9 Pipeline Zones**: Synchronized with backend zones (Zone 1 through Zone 9).
- **Hammer Tool**: Simulates damage or leaks on any pipe segment, sending telemetry to `POST /api/sensor-data` with `deviceId: "SIMULATION"`.
- **Fix It Mode**: Allows clicking damaged pipes to view active alerts, assign available Water Champions, and mark repairs complete.

---

## Project Structure

```
HydroGuard-Pipeline-Protection/
├── backend/                        # FastAPI Backend Application
│   ├── app/
│   │   ├── main.py                 # FastAPI application entrypoint & middleware
│   │   ├── config.py               # Settings & environment variable loader
│   │   ├── models.py               # SQLAlchemy ORM database models
│   │   ├── schemas.py              # Pydantic request/response schemas
│   │   ├── seed.py                 # Initial database seeder (9 zones)
│   │   ├── routers/                # API routes (auth, alerts, operations, views)
│   │   └── services/               # Core business logic (leak detection algorithms)
│   ├── tests/                      # pytest suite (test_api.py)
│   ├── hydroguard.db               # SQLite database file
│   ├── requirements.txt            # Python dependencies
│   └── run.py                      # Uvicorn launcher script
│
├── artifacts/
│   └── hydroguard/                 # React Frontend Application
│       ├── public/
│       │   └── simulator.html      # Hardware 9-pipe interactive demonstrator
│       ├── src/
│       │   ├── App.tsx             # Main React application & routing
│       │   ├── lib/
│       │   │   └── i18n.tsx        # Bilingual (English/Hindi) translation provider
│       │   ├── index.css           # Global design system & styles
│       │   └── main.tsx            # React root mount
│       ├── package.json            # Frontend dependencies & scripts
│       └── vite.config.ts          # Vite server & proxy configuration
│
├── docs/                           # Handover & Project Status Documentation
│   ├── HANDOVER.md                 # Detailed architecture & workflow handover guide
│   └── PROJECT_STATUS.md           # Implemented features & future roadmap
│
├── package.json                    # Workspace root scripts
└── pyproject.toml                  # Python package configuration
```

---

## Handover Documentation

For a detailed technical architecture overview, workflow breakdowns, authentication details, and developer guidelines, refer to:
- 📖 [**docs/HANDOVER.md**](docs/HANDOVER.md) — Comprehensive Developer Handover Guide
- 📊 [**AUDIT.md**](AUDIT.md) — Current Feature Status & Security Audit

---

## Recent System Modifications (Changelog)
- **Analytics Stability**: The Analytics API endpoint was rewritten to correctly return a structured JSON response (`kpis`, `flowPressure`, `alertsByRisk`, etc.). The frontend `App.tsx` handles old cached responses gracefully without crashing.
- **Simulator Isolation**: Data emitted from the `simulator.html` frontend is now explicitly isolated so it no longer pollutes live Field Telemetry.
- **Champion Seeding & Syncing**: Unused, hard-coded champions were eliminated from `seed.py`. The assignment workflow (`POST /api/alerts/{id}/assign`) now correctly updates the Champion's status to `ON_SITE`.
- **Localization Patches**: Missing Hindi translations (e.g., `simDetail`) and React `useLanguage()` hook dependencies were fixed across UI alert components to prevent runtime crashes.
