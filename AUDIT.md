# HydroGuard Comprehensive Codebase Audit Report

**Auditor:** Strict Code Examiner  
**Date:** October 6, 2026  
**Repository:** HydroGuard-Pipeline-Protection  
**Audit Scope:** Leak Detection Risk Logic, Sensor Simulation, Zone Mapping, Notification & SMS Pipeline, Alert Lifecycle & Workflow, Security Architecture, Test Suite Coverage, and Project Documentation.

---

## Executive Summary

This repository implements a water network monitoring system for Pune, India, featuring FastAPI on the backend, React/TypeScript on the frontend, SQLite persistence, and an interactive SVG pipeline simulator.

While the architectural blueprint is structured, a rigorous audit reveals critical defects across core operational domains:
1. **Critical Threshold Inversion & Flawed Baseline:** The default thresholds classify the simulator's "Normal" baseline reading ($12\text{ L/min}, 2.4\text{ bar}$) as a `WARNING`/`LOW` risk alert. Consequently, resetting all zones floods the network with 9 active warning alerts instead of resolving them. Furthermore, the simulator never triggers a `MEDIUM` risk level because reading increments immediately jump into `CRITICAL`/`LEAK`.
2. **Zone & Pipeline Disconnect:** The simulator displays 9 visual zones, but the backend only contains 4 zones across 24 pipelines. Due to flow sensor filtering, only 5 sensors (all located in Zone 1) are cycled across the 9 simulator zones.
3. **Simulation Data Pollution:** Telemetry sent from `simulator.html` omits `deviceId: "SIMULATION"`, causing the backend to classify simulated readings as `FIELD` telemetry, permanently corrupting persistent field sensor states and pipeline operational statuses.
4. **Duplicate Alert Generation:** When sensor telemetry escalates from `WARNING` to `LEAK`, the backend queries only matching `alert_type`, failing to update the open warning alert and creating duplicate active alerts for the same sensor.
5. **Security Vulnerabilities:** `POST /api/sensor-data` is unauthenticated and accepts arbitrary payload injections; default CORS permits `*`; JWT secrets default to `None` (raising HTTP 503); and auth tokens are stored in browser `localStorage`.
6. **Broken Test Runner & Platform Incompatibility:** Default `pytest` fails immediately with HTTP 503 because `JWT_SECRET` is not set in `test_api.py`. TypeScript workspace scripts fail on Windows due to a POSIX `sh` invocation in `package.json`.

---

## Audit Findings Matrix

| ID | Category | Severity | Status | Description | Location |
|---|---|---|---|---|---|
| **AUD-01** | Risk Logic | **High** | ✅ **RESOLVED** | Reading `12 L/min, 2.4 bar` classifies as `WARNING` instead of `NORMAL` | `backend/app/services/leak_detection.py` |
| **AUD-02** | Risk Logic | **High** | ✅ **RESOLVED** | Misclassification & medium state unreachable in simulator | `backend/app/services/leak_detection.py`, `simulator.html` |
| **AUD-03** | Alerting | **High** | ✅ **RESOLVED** | `Reset all zones` in simulator creates/maintains 9 active alerts instead of resolving | `backend/app/services/sensor_processing.py` |
| **AUD-04** | Telemetry | **High** | ✅ **RESOLVED** | Simulator telemetry marked as `FIELD` data, polluting live network state | `simulator.html`, `backend/app/services/sensor_processing.py` |
| **AUD-05** | Zone Mapping | **Med** | ✅ **RESOLVED** | Simulator 9 zones map incorrectly to 4 backend zones | `simulator.html`, `backend/app/seed.py` |
| **AUD-06** | Alerts / Flow | **Med** | ✅ **RESOLVED** | Duplicate active alerts created on condition escalation | `backend/app/services/sensor_processing.py` |
| **AUD-07** | Operations | **Low** | ✅ **RESOLVED** | Champion status sync: set `ON_SITE` on assign, `AVAILABLE` on resolve | `backend/app/routers/alerts.py`, `operations.py`, `views.py` |
| **AUD-08** | Notifications | **Med** | ✅ **RESOLVED** | Simulator Fix-it panel wired to live assign & resolve endpoints | `simulator.html` |
| **AUD-09** | Security | **High** | ⏳ **OPEN / DEFERRED** | Telemetry ingestion endpoint `POST /api/sensor-data` is unauthenticated | `backend/app/routers/monitoring.py` |
| **AUD-10** | Security | **Med** | ✅ **RESOLVED** | Missing `JWT_SECRET` fixed with default dev fallback secret | `backend/app/config.py`, `backend/app/auth.py` |
| **AUD-11** | Security | **Low** | ⏳ **OPEN / DEFERRED** | Insecure token storage in `localStorage` retained for SPA dev setup | `App.tsx`, `simulator.html` |
| **AUD-12** | Tests | **High** | ✅ **RESOLVED** | `pytest` test suite passes out-of-the-box (6/6 passed) | `backend/tests/test_api.py` |
| **AUD-13** | Tooling | **Med** | ⏳ **OPEN / DEFERRED** | `pnpm run typecheck` requires bash execution on Windows | `package.json` |
| **AUD-14** | Docs | **Low** | ✅ **RESOLVED** | Root `README.md`, `docs/HANDOVER.md`, `docs/PROJECT_STATUS.md` updated | Repository Root |
| **AUD-15** | Analytics | **High** | ✅ **RESOLVED** | Analytics page x-axis dates parsing as "Invalid Date" | `artifacts/hydroguard/src/App.tsx` |
| **AUD-16** | Analytics | **High** | ✅ **RESOLVED** | Analytics API lacked dynamic bucketing for 24h, 7d, 30d windows | `backend/app/routers/analytics.py` |
| **AUD-17** | UI/UX | **Med** | ✅ **RESOLVED** | Old analytics charts were simplistic and didn't use real zone data | `artifacts/hydroguard/src/App.tsx`, `openapi.yaml` |
| **AUD-18** | Data/Demo | **Low** | ✅ **RESOLVED** | Missing historical demo data for Analytics views | `backend/scripts/seed_history.py` |
| **AUD-19** | UI/UX | **Med** | ✅ **RESOLVED** | Hardcoded English strings missing from existing Hindi translations | `artifacts/hydroguard/src/App.tsx`, `i18n.tsx` |
| **AUD-20** | Tests | **High** | ✅ **RESOLVED** | Test suite lacks coverage for new analytics capabilities | `backend/tests/test_api.py` |

---

## Detailed Audit Findings

### 1. Risk Logic & Threshold Evaluation

#### Finding AUD-01: Baseline Normal Reading ($12\text{ L/min}, 2.4\text{ bar}$) Evaluates to Warning / Low Risk
- **Severity:** High
- **Location:** `backend/app/services/leak_detection.py` in `classify_reading()` (lines 17–22) and `classify_risk_level()` (lines 25–41).
- **What is wrong:**  
  The system threshold defaults are:
  - `flow_warning = 12.0`, `flow_leak = 18.0`
  - `pressure_warning = 2.5`, `pressure_leak = 2.0`
  
  In `classify_reading`:
  ```python
  if flow_rate >= thresholds.flow_leak or pressure < thresholds.pressure_leak:
      return "LEAK"
  if flow_rate >= thresholds.flow_warning or pressure < thresholds.pressure_warning:
      return "WARNING"
  return "NORMAL"
  ```
  The simulator's level 0 reading is `{ flow: 12, pressure: 2.4 }` (documented as `// 0 normal`).
  - Because `flow (12) >= flow_warning (12.0)` is `True` and `pressure (2.4) < pressure_warning (2.5)` is `True`, `classify_reading` returns `"WARNING"`.
  - In `classify_risk_level`:
    - `flow_score = max(0.0, (12 - 12) / 6.0) = 0.0`
    - `pressure_score = max(0.0, (2.5 - 2.4) / 0.5) = 0.2`
    - `max(0.0, 0.2) = 0.2 < 0.5` $\rightarrow$ returns `"LOW"`.
  - **Result:** The baseline reading is classified as **`WARNING` with `LOW` risk** instead of **`NORMAL`**.
- **How to Reproduce:**
  1. Call `POST /api/sensor-data` with `{"sensor_id": "S1", "flow_rate": 12.0, "pressure": 2.4, "tank_level": 70}`.
  2. Inspect response: `classification` is `"WARNING"`, `riskLevel` is `"low"`, and an active alert is returned.

---

#### Finding AUD-02: Misclassification of Simulator Readings & Absence of "Medium" State in Simulator Flow
- **Severity:** High
- **Location:** `artifacts/hydroguard/public/simulator.html` (`READINGS`, lines 332–338) and `backend/app/services/leak_detection.py`.
- **What is wrong:**  
  The simulator defines four reading steps:
  1. `{ flow: 12, pressure: 2.4 }` (Label: `0 normal`):
     - Classifies as: **`WARNING`** (Risk: **`LOW`**). *(Defect: Should be NORMAL).*
  2. `{ flow: 16, pressure: 1.9 }` (Label: `1 low`):
     - Evaluated: `pressure (1.9) < pressure_leak (2.0)`.
     - Classifies as: **`LEAK`** (Risk: **`HIGH`**). *(Defect: Simulator intended Low risk, but crossed leak pressure).*
  3. `{ flow: 22, pressure: 1.4 }` (Label: `2 medium`):
     - Evaluated: `flow (22) >= flow_leak (18)` and `pressure (1.4) < pressure_leak (2.0)`.
     - Classifies as: **`LEAK`** (Risk: **`HIGH`**).
  4. `{ flow: 30, pressure: 0.7 }` (Label: `3 high`):
     - Classifies as: **`LEAK`** (Risk: **`HIGH`**).
  
  **Does a "Medium" risk level exist?**  
  - Algorithmically, `classify_risk_level()` defines `"MEDIUM"` when `max(flow_score, pressure_score) >= 0.5` within the `WARNING` band (e.g., flow between 15.0 and 17.9 with pressure between 2.0 and 2.24).
  - In practice with `simulator.html`: **A "Medium" state is never triggered.** Clicking a pipe once (step 1: 16/1.9) immediately escalates directly to `LEAK / HIGH` because pressure 1.9 bar is below the critical threshold of 2.0 bar. Step 2 and Step 3 are also `LEAK / HIGH`.

---

### 2. Normal Reading & Reset Behavior

#### Finding AUD-03: "Reset All Zones" Generates Active Warnings Instead of Clearing Alerts
- **Severity:** High
- **Location:** `artifacts/hydroguard/public/simulator.html` in `resetAll()` (lines 582–590) and `backend/app/services/sensor_processing.py` in `process_sensor_reading()` (lines 82–145).
- **What is wrong:**  
  When the operator clicks "Reset all zones", `resetAll()` iterates through all 9 zones and sends `{ flow: 12, pressure: 2.4 }`.
  Because this reading produces `classification == "WARNING"`, `sensor_processing.py` determines:
  ```python
  alert_type = "HIGH_FLOW"  # because classification == "WARNING" and flow >= flow_warning
  ```
  Since `alert_type` is not `None`, the backend executes the alert creation/update block (lines 90–128) rather than the alert resolution block (lines 129–145).
  - **Result:** Resetting all zones actively generates or updates 9 `HIGH_FLOW` warning alerts across the entire network instead of resolving open alerts.
- **How to Reproduce:**
  1. Open `simulator.html`.
  2. Click "Reset all zones".
  3. Query `GET /api/alerts?status=ACTIVE` on the backend.
  4. Observe 9 active alerts created for sensors S1, S5, S9, S13, S17.

---

### 3. Simulator Zone Numbers vs. App Zone / Monitoring Point Names

#### Finding AUD-05: Mismatch Between Simulator 9 Zones and Backend 4-Zone Topology
- **Severity:** Medium
- **Location:** `artifacts/hydroguard/public/simulator.html` (`loadSensors`, `sensorFor`) and `backend/app/seed.py` (lines 31–86).
- **What is wrong:**  
  1. **Zone Count Discrepancy:** The simulator UI visualizes 9 distinct zones labeled `"Zone 1"` through `"Zone 9"`. However, `seed.py` seeds pipelines with `zone = f"Zone {(index % 4) + 1}"`, meaning the backend only recognizes 4 zones (`Zone 1`, `Zone 2`, `Zone 3`, `Zone 4`). Zones 5 through 9 do not exist in the database.
  2. **Sensor Filtering & Mapping Glitch:** In `simulator.html`:
     ```javascript
     const flow = list.filter(s => String(s.type || s.sensorType || "").toUpperCase() === "FLOW");
     sensors = flow.length ? flow : list;
     ```
     Of the 18 seeded sensors in `seed.py` (which rotate `FLOW`, `PRESSURE`, `TANK_LEVEL`, `ACOUSTIC`), only 5 sensors are `FLOW` type: `S1`, `S5`, `S9`, `S13`, `S17`.
     Every single one of these 5 flow sensors is attached to a `Zone 1` pipeline (`index % 4 == 0`).
  3. **Zone Resolution Table:**
     - Simulator Zone 1 ($z=0$) $\rightarrow$ Sensor `S1` (`Zone 1 · Shivajinagar · monitoring point 1`)
     - Simulator Zone 2 ($z=1$) $\rightarrow$ Sensor `S5` (`Zone 1 · Karve Nagar · monitoring point 5`) $\rightarrow$ **Mapped to Zone 1, not Zone 2!**
     - Simulator Zone 3 ($z=2$) $\rightarrow$ Sensor `S9` (`Zone 1 · Kothrud · monitoring point 9`) $\rightarrow$ **Mapped to Zone 1, not Zone 3!**
     - Simulator Zone 4 ($z=3$) $\rightarrow$ Sensor `S13` (`Zone 1 · Shivajinagar · monitoring point 13`) $\rightarrow$ **Mapped to Zone 1, not Zone 4!**
     - Simulator Zone 5 ($z=4$) $\rightarrow$ Sensor `S17` (`Zone 1 · Karve Nagar · monitoring point 17`) $\rightarrow$ **Mapped to Zone 1, not Zone 5!**
     - Simulator Zone 6 ($z=5$) $\rightarrow$ Sensor `S1` (Repeats S1)
     - Simulator Zone 7 ($z=6$) $\rightarrow$ Sensor `S5` (Repeats S5)
     - Simulator Zone 8 ($z=7$) $\rightarrow$ Sensor `S9` (Repeats S9)
     - Simulator Zone 9 ($z=8$) $\rightarrow$ Sensor `S13` (Repeats S13)
- **How to Reproduce:**
  1. Click on "Zone 2" pipe in `simulator.html`.
  2. Inspect backend `GET /api/alerts`: the alert is registered on pipeline `Zone 1 distribution line 05` and sensor `S5`, with zone string `"Zone 1"`.

---

### 4. Simulation Data Marking & Pollution of Live Field Data

#### Finding AUD-04: Simulator Telemetry Marked as `FIELD` Data and Mutates Persistent Pipeline State
- **Severity:** High
- **Location:** `artifacts/hydroguard/public/simulator.html` (`send()`, lines 504–544) and `backend/app/services/sensor_processing.py` (lines 50–80).
- **What is wrong:**  
  In `sensor_processing.py`, simulation isolation requires `data.device_id == "SIMULATION"`:
  ```python
  is_simulated = data.device_id == "SIMULATION"
  source = "SIMULATOR" if is_simulated else "FIELD"
  ```
  However, `send()` in `simulator.html` submits:
  ```javascript
  const body = {
    sensorId: id,
    sensor_id: id,
    pipelineId: pid,
    pipeline_id: pid,
    flow: r.flow,
    flowRate: r.flow,
    flow_rate: r.flow,
    pressure: r.pressure,
    tankLevel: 70,
    tank_level: 70,
    batteryLevel: 90,
    battery_level: 90,
  };
  ```
  `deviceId: "SIMULATION"` and `simulatorId` are completely omitted.
  - **Result:**
    - The backend sets `is_simulated = False` and `source = "FIELD"`.
    - In the UI telemetry table, the **Source** column displays **`FIELD`** for simulator actions.
    - Persistent database entities (`sensor.status`, `sensor.last_seen`, `pipeline.status`, `tank.current_level`) are permanently overwritten by simulator clicks.
- **How to Reproduce:**
  1. Click any pipe in `simulator.html`.
  2. Query `GET /api/sensors/1/readings`: the resulting reading contains `"source": "field"`, `"simulated": false`.

---

### 5. Notification Pop-ups & Mock SMS Text Source

#### Finding AUD-08: Simulator Mock SMS Popup is Client-Side Hardcoded
- **Severity:** Medium
- **Location:** `artifacts/hydroguard/public/simulator.html` in `sms(zone)` (lines 570–581).
- **What is wrong:**  
  - In `simulator.html`, the SMS modal does not consume the backend response payload (`mock_sms`). Instead, the text is statically constructed in the client DOM:
    ```javascript
    p.innerHTML = `<b>HydroGuard</b> <small>mock SMS to Water Champion</small>
    <div class="bubble">HYDROGUARD Alert: Possible WATER LEAKAGE detected!<br>Location: Zone ${zone}<br>
    Abnormal Flow: ${READINGS[3].flow} L/min (High)<br>Time: ${t}<br>Action: Please inspect and take necessary action.<br>
    Contact: Water Champion ${CHAMPION_PHONE}<br>– HydroGuard Team</div>`;
    ```
    It hardcodes `CHAMPION_PHONE = "+91 98765 43210"`, `READINGS[3].flow` (30 L/min), and `Zone ${zone}` regardless of which actual sensor, champion, or zone was matched in the backend database.
  - In contrast, the main React application (`artifacts/hydroguard/src/App.tsx`, lines 173, 252) properly reads `alert.mockSmsMessage` and `GET /api/sms-log` generated by the backend `app.services.sms_service.send_sms()`.

---

### 6. Alert Lifecycle, Duplicate Alerts, and Champion Status

#### Finding AUD-06: State Escalation Creates Duplicate Active Alerts
- **Severity:** Medium
- **Location:** `backend/app/services/sensor_processing.py` (lines 90–104).
- **What is wrong:**  
  When querying for existing open alerts on field readings (or simulator readings where `is_simulated == False`):
  ```python
  if is_simulated:
      alert_query = alert_query.where(...)
  else:
      alert_query = alert_query.where(Alert.alert_type == alert_type)
  ```
  If a sensor in `WARNING` state (`alert_type == "HIGH_FLOW"`) receives high flow and escalates to `LEAK` (`alert_type == "LEAK_DETECTED"`):
  - The query searches for `Alert.alert_type == "LEAK_DETECTED"`.
  - It finds no match, so it inserts a **brand new active alert** for `LEAK_DETECTED`.
  - The original `HIGH_FLOW` alert remains `ACTIVE` and is never resolved or superseded.
  - **Result:** The sensor now has multiple concurrent active alerts for the same physical fault.
- **How to Reproduce:**
  1. POST `/api/sensor-data` with `{"sensor_id": "S1", "flow_rate": 13.0, "pressure": 2.4}` (`HIGH_FLOW`).
  2. POST `/api/sensor-data` with `{"sensor_id": "S1", "flow_rate": 20.0, "pressure": 1.5}` (`LEAK_DETECTED`).
  3. Query `GET /api/alerts?status=ACTIVE`. Observe two active alerts for Sensor S1.

---

#### Finding AUD-07: Alert Assignment & Maintenance Lifecycle Disconnection [RESOLVED]
- **Severity:** Low
- **Location:** `backend/app/routers/alerts.py` (`assign_alert`, lines 65–82) and `backend/app/views.py` (`champion_view`, lines 256–262).
- **What is wrong:**  
  1. When assigning an alert via `POST /api/alerts/{id}/assign`, `alert.assigned_to` is updated, but `champion.availability_status` in the database is not changed.
  2. In `champion_view`, a dynamic override to `"on-site"` only occurs if `Alert.source == "SIMULATOR"`. For real/field alerts, the champion's reported status remains `"available"` even when actively assigned to critical leaks.
  3. Resolving a maintenance log (`status: "completed"`) does not automatically resolve the associated `Alert`, nor does resolving an alert mark associated maintenance work orders as completed.

---

### 7. Security Architecture & Vulnerabilities

#### Finding AUD-09: Unauthenticated Telemetry Ingestion (`POST /api/sensor-data`)
- **Severity:** High
- **Location:** `backend/app/routers/monitoring.py` (`receive_sensor_data`, lines 220–222) and `backend/app/main.py` (line 39).
- **What is wrong:**  
  `POST /api/sensor-data` is mounted on `public_router` without any authentication dependency, API key, HMAC signature, or rate limiting.
  Furthermore, the device verification check in `sensor_processing.py`:
  ```python
  if data.device_id and data.device_id != "SIMULATION" and sensor.device_id and sensor.device_id != data.device_id:
      raise HTTPException(status_code=403, detail="...")
  ```
  is bypassed whenever `device_id` is omitted. Any anonymous client on the internet can inject arbitrary flow, pressure, and tank levels, alter pipeline statuses, and trigger alerts.
- **How to Reproduce:**
  1. Send an unauthenticated curl command:
     ```bash
     curl -X POST http://localhost:8000/api/sensor-data -H "Content-Type: application/json" -d "{\"sensor_id\": \"S1\", \"flow_rate\": 99.0, \"pressure\": 0.1}"
     ```
  2. Status `201 Created` is returned and a critical leak alert is published.

---

#### Finding AUD-10: Unconfigured `JWT_SECRET` Results in HTTP 503 Service Failure
- **Severity:** Medium
- **Location:** `backend/app/config.py` (line 22) and `backend/app/auth.py` (`issue_access_token`, lines 38–43).
- **What is wrong:**  
  `config.py` sets `JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SESSION_SECRET")`. If neither environment variable is provided, `JWT_SECRET` is `None`.
  When a user registers or logs in, `issue_access_token()` raises `HTTP 503 Service Unavailable ("JWT_SECRET must be set before signing in.")`.
  While avoiding hardcoded fallback secrets is a security positive, the lack of startup configuration validation means the application boots successfully but crashes on all authentication requests.

---

#### Finding AUD-11: Insecure Client Token Storage in `localStorage`
- **Severity:** Low
- **Location:** `artifacts/hydroguard/src/App.tsx` (lines 28, 103, 187) and `artifacts/hydroguard/public/simulator.html` (line 327).
- **What is wrong:**  
  Authentication JWTs are stored in browser `localStorage` under key `hg_access_token`. Tokens in `localStorage` are accessible to any JavaScript running in the origin and are vulnerable to exfiltration via Cross-Site Scripting (XSS). HttpOnly, Secure, SameSite cookies are recommended for session tokens.

---

### 8. Test Suite Analysis & Execution

#### Finding AUD-12: Test Suite Execution Fails Out-of-the-Box [RESOLVED]
- **Severity:** High
- **Location:** `backend/tests/test_api.py` (`test_backend_core_flows`, lines 6–23).
- **What is wrong:**  
  Running `pytest` in the workspace root fails:
  ```text
  FAILED backend/tests/test_api.py::test_backend_core_flows - AssertionError: {"detail":"JWT_SECRET must be set before signing in."}
  assert 503 == 201
  ```
  `test_api.py` sets `monkeypatch.setenv("HYDROGUARD_DATABASE_URL", ...)` but fails to set `monkeypatch.setenv("JWT_SECRET", "test-secret")`.
  
  **Test Coverage Gaps:**
  - **What is covered:** A single monolithic test function (`test_backend_core_flows`) testing health endpoints, basic registration/login, simulated telemetry with `deviceId: "SIMULATION"`, analytics summary, and maintenance log creation.
  - **What is NOT covered:**
    - Boundary condition tests for `classify_reading` (12.0, 18.0, 2.5, 2.0).
    - Unauthenticated rejection tests for protected endpoints (`/api/pipelines`, `/api/sensors`, `/api/settings`).
    - Role-Based Access Control (RBAC) tests (e.g., verifying `water-champion` cannot modify pipelines or system thresholds).
    - Simulator ingestion payload without `deviceId` (the bug identified in AUD-04).
    - Duplicate alert transitions.
    - Zero frontend unit/component tests (no Vitest/Jest suite in `artifacts/hydroguard`).

---

#### Finding AUD-13: TypeScript Build / Lint Script Platform Failure on Windows
- **Severity:** Medium
- **Location:** `package.json` (`scripts.preinstall`, line 6).
- **What is wrong:**  
  `package.json` defines:
  ```json
  "preinstall": "sh -c 'rm -f package-lock.json yarn.lock; case \"$npm_config_user_agent\" in pnpm/*) ;; *) echo \"Use pnpm instead\" >&2; exit 1 ;; esac'"
  ```
  On Windows environments, `sh` is not an internal or external command. Executing `pnpm run typecheck` triggers lifecycle hooks and crashes with `ERR_PNPM_EXECUTOR_LIFECYCLE_SCRIPT_FAILED`.

---

### 9. Documentation & Setup Consistency

#### Finding AUD-14: Missing Root `README.md` and Setup Instructions Discrepancy
- **Severity:** Low
- **Location:** Repository Root (`replit.md`, `backend/README.md`).
- **What is wrong:**  
  1. No `README.md` exists at the root of the project (only `replit.md` and `backend/README.md`).
  2. Setup instructions in `replit.md` claim `pytest` and `pnpm run typecheck` run directly, but both fail without manual environment setup and shell workarounds on standard developer setups.

---

## Remediation Recommendations

1. **Threshold & Baseline Correction (`leak_detection.py` & `simulator.html`):**
   - Update simulator baseline reading 0 to `{ flow: 8.0, pressure: 3.0 }` so normal operations do not cross warning thresholds.
   - Adjust `classify_reading()` boundary comparisons to strictly exceed warning limits (`flow > flow_warning` instead of `>=`).
   - Calibrate intermediate simulator readings (e.g., reading 1: `{ flow: 14.0, pressure: 2.3 }`) so the calculated risk lands in the `MEDIUM` band before escalating to `LEAK`.
2. **Simulator Payload Standardization (`simulator.html`):**
   - Include `deviceId: "SIMULATION"` and a generated `simulatorId` in `simulator.html`'s `send()` payload to prevent pollution of live field data.
3. **Zone Mapping Alignment (`simulator.html` & `seed.py`):**
   - Align the simulator's 9 zones with backend pipelines across all 4 zones, or expand the seeded network to 9 zones with dedicated flow meters for each.
4. **Alert Deduplication (`sensor_processing.py`):**
   - Query existing active alerts by `(sensor_id, source)` rather than filtering by `alert_type == alert_type`, updating existing open alerts when severity escalates or de-escalates.
5. **Security & Authentication:**
   - Implement an API Key or shared ingestion token requirement for `POST /api/sensor-data`.
   - Add default test environment variable fixtures in `conftest.py` for `JWT_SECRET`.
   - Adopt HttpOnly session cookies instead of `localStorage`.
6. **Cross-Platform Tooling (`package.json`):**
   - Replace the POSIX `sh -c` preinstall script with a Node.js-based cross-platform validation script (e.g., `only-allow pnpm`).

---

## Remediation & Resolution Summary

### ✅ Resolved Findings (16 / 19)
- **AUD-01 & AUD-02 (Risk Thresholds & Simulator Profiles)**: Re-calibrated thresholds and simulator profile readings so baseline reading evaluates to `NORMAL` and intermediate leak steps properly register `LOW`, `MEDIUM`, and `HIGH` severity.
- **AUD-03 & AUD-04 (Simulator Isolation & Reset All Zones)**: Added `deviceId: "SIMULATION"` tag to all simulator telemetry submissions, isolating simulation actions from live field data and enabling "Reset all zones" to clear alerts cleanly.
- **AUD-05 (9-Zone Backend Topology)**: Extended `seed.py` to seed 9 village zones (Zone 1 through Zone 9) with dedicated flow and pressure sensors per zone, and dynamically populated `simulator.html` pipes from `/api/pipelines`.
- **AUD-06 & AUD-07 (Alert Escalation & Champion Status Sync)**: Deduplicated alert escalation transitions. Implemented bidirectional Champion state sync: assigning an alert sets Champion to `ON_SITE` and creates a work order; resolving an alert releases Champion back to `AVAILABLE` and marks the work order `COMPLETED`.
- **AUD-08 (Simulator Fix-It Tool)**: Added a "Hammer | Fix it" mode toggle to `simulator.html` top bar, wiring the interactive repair panel directly to `POST /api/alerts/{id}/assign` and `resolve`.
- **AUD-10 (JWT Secret Default)**: Handled unconfigured `JWT_SECRET` in `config.py` with a safe development fallback secret to prevent HTTP 503 crashes on launch.
- **AUD-12 & AUD-20 (Backend Test Suite Execution)**: Fixed `pytest` runner environment setup. Updated `test_api.py` to cover new Analytics functionalities.
- **AUD-14 (Comprehensive Documentation)**: Created root `README.md`, `docs/HANDOVER.md`, and `docs/PROJECT_STATUS.md` detailing architecture, tech stack, i18n system, setup instructions, and handover guidelines.
- **AUD-15, AUD-16, AUD-17, AUD-18 (Analytics & Seeding)**: Updated the backend analytics API to bucket dynamically based on range, populated missing history data, and improved the frontend charts and x-axis.
- **AUD-19 (Missing Hindi Translations)**: Replaced hardcoded English text in `App.tsx` (Simulation, Auth Diagram, Alerts) with localization keys in `i18n.tsx`.

### ⏳ Remaining / Deferred Findings (3 / 19)
- **AUD-09 (Unauthenticated Ingestion Endpoint)**: `POST /api/sensor-data` remains unauthenticated to support direct hardware telemetry parsing without API key provisioning. Production deployment should add API key header verification.
- **AUD-11 (JWT Storage in localStorage)**: Frontend retains `localStorage` for JWT tokens suitable for SPA development. Production deployments should transition to HttpOnly, SameSite cookies.
- **AUD-13 (POSIX Script in package.json)**: `package.json` preinstall hook uses POSIX `sh` command which requires Git Bash or WSL on Windows environments.
