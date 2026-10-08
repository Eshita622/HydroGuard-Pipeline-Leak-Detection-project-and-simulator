from datetime import datetime, timezone

from fastapi.testclient import TestClient


def test_backend_core_flows(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDROGUARD_DATABASE_URL", f"sqlite:///{tmp_path / 'hydroguard-test.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32-chars-long-xxx")
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "healthy"
        assert client.get("/api/healthz").json()["status"] == "ok"
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200

        registered = client.post("/api/auth/register", json={
            "fullName": "HydroGuard Test Operator",
            "email": "operator@hydroguard-demo.dev",
            "mobile": "+919900000001",
            "password": "local-test-password",
            "role": "administrator",
        })
        assert registered.status_code == 201, registered.text
        body = registered.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/auth/session", headers=headers).json()["user"]["role"] == "administrator"

        champ_reg = client.post("/api/auth/register", json={
            "fullName": "Test Champion",
            "email": "champion@hydroguard-demo.dev",
            "mobile": "+919900000002",
            "password": "local-test-password",
            "role": "water-champion",
            "assigned_zone": "Zone 5",
        })
        assert champ_reg.status_code == 201, champ_reg.text
        
        champs = client.get("/api/water-champions", headers=headers).json()
        assert len(champs) == 1
        assert champs[0]["name"] == "Test Champion"
        assert champs[0]["assigned_zone"] == "Zone 5"

        dashboard = client.get("/api/dashboard", headers=headers)
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["metrics"]["totalSensors"] == 26

        map_data = client.get("/api/map", headers=headers).json()
        assert len(map_data["pipelines"]) == 29
        assert len(map_data["sensors"]) == 26
        assert 18.4 < map_data["pipelines"][0]["latitude"] < 18.7

        # Both the normal hardware ingestion route and simulations use the
        # same classification, persistence, and alert-processing service.
        leak = client.post("/api/sensor-data", json={
            "sensor_id": "S4", "flow_rate": 19, "pressure": 1.8,
            "tank_level": 23, "device_id": "HG-ESP32-004",
        })
        assert leak.status_code == 201, leak.text
        assert leak.json()["classification"] == "LEAK"
        assert leak.json()["alert"]["severity"] == "critical"

        normal = client.post("/api/sensor-data", json={
            "sensor_id": "S4", "flow_rate": 8, "pressure": 3.1, "tank_level": 55,
        })
        assert normal.status_code == 201, normal.text
        assert normal.json()["classification"] == "NORMAL"
        assert normal.json()["notificationsStatus"] == "disabled"

        simulated = client.post("/api/simulation/warning", headers=headers, json={"sensor_id": "S5"})
        assert simulated.status_code == 200, simulated.text
        assert simulated.json()["classification"] == "WARNING"
        assert simulated.json()["notificationsStatus"] == "disabled"

        analytics = client.get("/api/analytics?range=24h", headers=headers)
        assert analytics.status_code == 200, analytics.text
        assert analytics.json()["range"] == "24h"
        assert "flowPressure" in analytics.json()
        assert "kpis" in analytics.json()

        report = client.get(
            "/api/reports",
            params={
                "type": "water-usage",
                "from": datetime.now(timezone.utc).date().isoformat(),
                "to": datetime.now(timezone.utc).date().isoformat(),
            },
            headers=headers,
        )
        assert report.status_code == 200, report.text
        assert report.json()["columns"]

        assert client.post("/api/auth/login", json={
            "identifier": "operator@hydroguard-demo.dev", "password": "local-test-password",
        }).status_code == 200

        # The browser simulator is an overlay, not a write path for seeded
        # sensors, pipelines, tanks, champions, or field alerts.
        from app.services.sms_service import clear_sms_log

        clear_sms_log()
        registered_sensors = client.get("/api/sensors", headers=headers).json()
        sensor = next(item for item in registered_sensors if item["sensor_id"] == "S5")
        distinct_pipelines = {item["pipeline_id"] for item in registered_sensors}
        assert len(distinct_pipelines) >= 9
        pipeline_id = sensor["pipeline_id"]
        map_before = client.get("/api/map", headers=headers).json()
        sensor_status_before = sensor["status_code"]
        pipeline_status_before = next(
            item["status_code"] for item in map_before["pipelines"] if item["pipeline_id"] == pipeline_id
        )
        tanks_before = client.get("/api/tanks", headers=headers).json()
        field_alerts_before = [
            (item["id"], item["status"], item["severity"])
            for item in client.get("/api/alerts", headers=headers).json()
            if not item["simulated"]
        ]

        def simulated_reading(session_id, flow, pressure):
            response = client.post("/api/sensor-data", json={
                "sensorId": "S5",
                "flowLpm": flow,
                "pressureBar": pressure,
                "tankLevelPercent": 62,
                "deviceId": "SIMULATION",
                "simulatorId": session_id,
            })
            assert response.status_code == 201, response.text
            return response.json()

        first = simulated_reading("browser-A", 13.5, 2.4)
        assert first["source"] in ("simulated", "simulator")
        assert first["simulated"] is True
        assert first["riskLevel"] == "low"
        alert_a_id = first["alert"]["id"]
        repeat = simulated_reading("browser-A", 13.5, 2.4)
        assert repeat["alert"]["id"] == alert_a_id
        medium = simulated_reading("browser-A", 15.5, 2.2)
        assert medium["alert"]["riskLevel"] == "medium"
        high = simulated_reading("browser-A", 20, 1.8)
        assert high["alert"]["riskLevel"] == "high"
        assert high["notificationsStatus"] == "mock_sent"
        assert high["mockSms"]["simulated"] is True
        assert high["mockSms"]["source"] in ("simulated", "simulator")
        assert len([
            item for item in client.get("/api/sms-log", headers=headers).json()
            if item["alertId"] == alert_a_id
        ]) == 1
        simulated_reading("browser-A", 20, 1.8)
        assert len([
            item for item in client.get("/api/sms-log", headers=headers).json()
            if item["alertId"] == alert_a_id
        ]) == 1

        # A second browser session gets its own alert; resetting A cannot close B.
        high_b = simulated_reading("browser-B", 20, 1.8)
        assert high_b["alert"]["id"] != alert_a_id
        normal_a = simulated_reading("browser-A", 8.6, 3.0)
        assert normal_a["alertStatus"] is None
        open_simulated = {
            item["id"]: item
            for item in client.get("/api/alerts", headers=headers).json()
            if item["source"] in ("simulated", "simulator") and item["status"] != "resolved"
        }
        assert alert_a_id not in open_simulated
        assert high_b["alert"]["id"] in open_simulated

        # A fresh A incident can be assigned and repaired through the real API.
        repair_alert = simulated_reading("browser-A", 20, 1.8)["alert"]
        champion = client.get("/api/water-champions", headers=headers).json()[0]
        assigned = client.post(
            f"/api/alerts/{repair_alert['id']}/assign",
            headers=headers,
            json={"championId": champion["id"]},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["championId"] == champion["id"]

        champ_metrics_1 = client.get("/api/water-champions", headers=headers).json()[0]
        assert champ_metrics_1["activeAlerts"] == 1
        assert champ_metrics_1["status"] == "on-site"

        work_order = client.post(
            f"/api/alerts/{repair_alert['id']}/maintenance",
            headers=headers,
            json={"championId": champion["id"], "priority": "critical"},
        )
        assert work_order.status_code == 201, work_order.text
        assert work_order.json()["status"] == "in-progress"
        simulated_reading("browser-A", 8.6, 3.0)
        completed = client.patch(
            f"/api/maintenance/{work_order.json()['id']}",
            headers=headers,
            json={"status": "completed", "issue": "Simulator repair completed."},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"
        
        resolved_alert = client.post(f"/api/alerts/{repair_alert['id']}/resolve", headers=headers)
        assert resolved_alert.status_code == 200, resolved_alert.text
        
        champ_metrics_2 = client.get("/api/water-champions", headers=headers).json()[0]
        assert champ_metrics_2["activeAlerts"] == 0
        assert champ_metrics_2["completedRepairs"] >= 1
        assert champ_metrics_2["status"] == "available"
        assert isinstance(champ_metrics_2["averageResponseMinutes"], int)

        # Resetting browser B is also session-scoped and leaves field records intact.
        simulated_reading("browser-B", 8.6, 3.0)
        final_alerts = client.get("/api/alerts", headers=headers).json()
        assert [
            (item["id"], item["status"], item["severity"])
            for item in final_alerts
            if not item["simulated"]
        ] == field_alerts_before
        final_sensor = next(
            item for item in client.get("/api/sensors", headers=headers).json()
            if item["sensor_id"] == "S5"
        )
        assert final_sensor["status_code"] == sensor_status_before
        final_map = client.get("/api/map", headers=headers).json()
        assert next(
            item["status_code"] for item in final_map["pipelines"] if item["pipeline_id"] == pipeline_id
        ) == pipeline_status_before
        assert client.get("/api/tanks", headers=headers).json() == tanks_before
        mock_entries = client.get("/api/sms-log", headers=headers).json()
        assert len([item for item in mock_entries if item["source"] in ("simulated", "simulator")]) == 3


def test_threshold_boundary_classifications():
    from app.services.leak_detection import Thresholds, classify_reading, classify_risk_level

    thresholds = Thresholds(
        flow_warning=12.0,
        flow_leak=18.0,
        pressure_warning=2.5,
        pressure_leak=2.0,
    )

    # Below warning thresholds -> NORMAL
    assert classify_reading(8.0, 3.0, thresholds) == "NORMAL"
    assert classify_reading(12.0, 2.5, thresholds) == "NORMAL"
    assert classify_risk_level("NORMAL", 12.0, 2.5, thresholds) is None

    # Low sits just past warning limits -> WARNING (LOW)
    assert classify_reading(13.5, 2.4, thresholds) == "WARNING"
    assert classify_risk_level("WARNING", 13.5, 2.4, thresholds) == "LOW"

    # Medium sits between warning and leak limits -> WARNING (MEDIUM)
    assert classify_reading(16.5, 2.15, thresholds) == "WARNING"
    assert classify_risk_level("WARNING", 16.5, 2.15, thresholds) == "MEDIUM"

    # High at or past leak/critical limits -> LEAK (HIGH)
    assert classify_reading(18.0, 2.4, thresholds) == "LEAK"
    assert classify_risk_level("LEAK", 18.0, 2.4, thresholds) == "HIGH"
    assert classify_reading(10.0, 2.0, thresholds) == "LEAK"
    assert classify_risk_level("LEAK", 10.0, 2.0, thresholds) == "HIGH"
    assert classify_reading(22.0, 1.4, thresholds) == "LEAK"
    assert classify_risk_level("LEAK", 22.0, 1.4, thresholds) == "HIGH"


def test_no_duplicate_alerts_on_escalation_and_auto_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDROGUARD_DATABASE_URL", f"sqlite:///{tmp_path / 'hydroguard-escalation.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32-chars-long-xxx")
    from app.main import app

    with TestClient(app) as client:
        # Register user to get headers
        registered = client.post("/api/auth/register", json={
            "fullName": "Escalation Test Operator",
            "email": "escalation@hydroguard-demo.dev",
            "mobile": "+919900000099",
            "password": "local-test-password",
            "role": "administrator",
        })
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

        # Step 1: Ingest WARNING reading for S4 (field)
        r1 = client.post("/api/sensor-data", json={
            "sensorId": "S4",
            "flowLpm": 13.5,
            "pressureBar": 2.4,
            "tankLevelPercent": 70,
        })
        assert r1.status_code == 201
        assert r1.json()["classification"] == "WARNING"
        assert r1.json()["riskLevel"] == "low"
        alert_id = r1.json()["alert"]["id"]

        # Step 2: Escalate to LEAK for S4 -> must UPDATE existing alert, NOT create a second open alert
        r2 = client.post("/api/sensor-data", json={
            "sensorId": "S4",
            "flowLpm": 20.0,
            "pressureBar": 1.5,
            "tankLevelPercent": 65,
        })
        assert r2.status_code == 201
        assert r2.json()["classification"] == "LEAK"
        assert r2.json()["riskLevel"] == "high"
        assert r2.json()["alert"]["id"] == alert_id
        assert r2.json()["alert"]["severity"] == "critical"

        # Verify only 1 active alert for S4 in database
        s4_alerts = [
            a for a in client.get("/api/alerts", headers=headers).json()
            if a["sensorId"] == "S4" and a["status"] != "resolved"
        ]
        assert len(s4_alerts) == 1

        # Step 3: Test normal reading creates no new alert
        r_normal = client.post("/api/sensor-data", json={
            "sensorId": "S6",
            "flowLpm": 8.0,
            "pressureBar": 3.0,
            "tankLevelPercent": 80,
        })
        assert r_normal.status_code == 201
        assert r_normal.json()["classification"] == "NORMAL"
        assert r_normal.json()["alert"] is None

        # Step 4: Simulated alert auto-clear on returning to normal
        sim_alert = client.post("/api/sensor-data", json={
            "sensorId": "S6",
            "flowLpm": 16.5,
            "pressureBar": 2.1,
            "tankLevelPercent": 50,
            "deviceId": "SIMULATION",
            "simulatorId": "test-auto-clear",
        })
        assert sim_alert.status_code == 201
        assert sim_alert.json()["classification"] == "WARNING"
        assert sim_alert.json()["simulated"] is True
        sim_alert_id = sim_alert.json()["alert"]["id"]

        # Return simulation to normal
        sim_clear = client.post("/api/sensor-data", json={
            "sensorId": "S6",
            "flowLpm": 8.0,
            "pressureBar": 3.0,
            "tankLevelPercent": 80,
            "deviceId": "SIMULATION",
            "simulatorId": "test-auto-clear",
        })
        assert sim_clear.status_code == 201
        assert sim_clear.json()["classification"] == "NORMAL"

        # Check that simulated alert was auto-resolved with note
        resolved_alert = client.get(f"/api/alerts/{sim_alert_id}", headers=headers).json()
        assert resolved_alert["status"] == "resolved"
        assert "auto-resolved: readings normal" in resolved_alert["message"]


def test_simulation_profile_and_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDROGUARD_DATABASE_URL", f"sqlite:///{tmp_path / 'hydroguard-profile.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32-chars-long-xxx")
    from app.main import app

    with TestClient(app) as client:
        registered = client.post("/api/auth/register", json={
            "fullName": "Profile Test Operator",
            "email": "profile@hydroguard-demo.dev",
            "mobile": "+919900000088",
            "password": "local-test-password",
            "role": "administrator",
        })
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

        # GET /api/simulation/profile returns computed examples for all 4 states
        profile = client.get("/api/simulation/profile", headers=headers)
        assert profile.status_code == 200
        p = profile.json()
        assert "normal" in p and "low" in p and "medium" in p and "high" in p
        assert p["normal"]["flow"] < p["low"]["flow"] < p["medium"]["flow"] < p["high"]["flow"]

        # Create a simulated alert
        client.post("/api/sensor-data", json={
            "sensorId": "S7",
            "flowLpm": p["high"]["flow"],
            "pressureBar": p["high"]["pressure"],
            "tankLevelPercent": 40,
            "deviceId": "SIMULATION",
            "simulatorId": "test-reset-session",
        })

        # Pre-reset: field alerts count
        field_alerts_before = [
            a for a in client.get("/api/alerts", headers=headers).json()
            if not a["simulated"]
        ]

        # POST /api/simulation/reset
        reset_res = client.post(
            "/api/simulation/reset",
            headers=headers,
            json={"simulatorId": "test-reset-session"},
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "ok"

        # Field alerts remain intact
        field_alerts_after = [
            a for a in client.get("/api/alerts", headers=headers).json()
            if not a["simulated"]
        ]
        assert [a["id"] for a in field_alerts_after] == [a["id"] for a in field_alerts_before]

        # Simulated alert for this session is resolved
        open_sim = [
            a for a in client.get("/api/alerts", headers=headers).json()
            if a["simulated"] and a.get("simulatorId") == "test-reset-session" and a["status"] != "resolved"
        ]
        assert len(open_sim) == 0


def test_all_nine_zones_alerts_and_simulation(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDROGUARD_DATABASE_URL", f"sqlite:///{tmp_path / 'hydroguard-nine-zones.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32-chars-long-xxx")
    from app.main import app

    with TestClient(app) as client:
        registered = client.post("/api/auth/register", json={
            "fullName": "Nine Zones Operator",
            "email": "ninezones@hydroguard-demo.dev",
            "mobile": "+919900000077",
            "password": "local-test-password",
            "role": "administrator",
        })
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

        # Fetch profile
        profile = client.get("/api/simulation/profile", headers=headers).json()
        pipelines = client.get("/api/pipelines", headers=headers).json()
        sensors = client.get("/api/sensors", headers=headers).json()

        # Test each of the 9 zones
        for zone_idx in range(1, 10):
            zone_name = f"Zone {zone_idx}"
            pipe = next((p for p in pipelines if p["zone"] == zone_name), None)
            assert pipe is not None, f"Missing pipeline for {zone_name}"

            pipe_sensors = [s for s in sensors if str(s.get("pipelineId") or s.get("pipeline_id")) == str(pipe["id"])]
            flow_sensor = next((s for s in pipe_sensors if s.get("sensor_type") == "FLOW"), pipe_sensors[0] if pipe_sensors else None)
            assert flow_sensor is not None, f"Missing sensor for {zone_name}"

            sensor_code = flow_sensor["sensor_id"]

            # Test LOW risk alert for this zone
            low_res = client.post("/api/sensor-data", json={
                "sensorId": sensor_code,
                "pipelineId": pipe["id"],
                "flowLpm": profile["low"]["flow"],
                "pressureBar": profile["low"]["pressure"],
                "tankLevelPercent": 70,
                "deviceId": "SIMULATION",
                "simulatorId": f"session-zone-{zone_idx}",
            })
            assert low_res.status_code == 201
            assert low_res.json()["classification"] == "WARNING"
            assert low_res.json()["riskLevel"] == "low"
            assert low_res.json()["alert"]["zone"] == zone_name

            # Test HIGH risk escalation for this zone
            high_res = client.post("/api/sensor-data", json={
                "sensorId": sensor_code,
                "pipelineId": pipe["id"],
                "flowLpm": profile["high"]["flow"],
                "pressureBar": profile["high"]["pressure"],
                "tankLevelPercent": 70,
                "deviceId": "SIMULATION",
                "simulatorId": f"session-zone-{zone_idx}",
            })
            assert high_res.status_code == 201
            assert high_res.json()["classification"] == "LEAK"
            assert high_res.json()["riskLevel"] == "high"
            assert high_res.json()["alert"]["zone"] == zone_name
            assert high_res.json()["alert"]["simulated"] is True

        # Clean reset for all simulator sessions
        reset_res = client.post("/api/simulation/reset", headers=headers, json={})
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "ok"


def test_champion_status_sync_and_water_loss_maths(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDROGUARD_DATABASE_URL", f"sqlite:///{tmp_path / 'hydroguard-champ-sync.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32-chars-long-xxx")
    monkeypatch.setenv("ASSUMED_MANUAL_DELAY_MINUTES", "360")
    from app.database import SessionLocal
    from app.main import app
    from app.models import Alert

    with TestClient(app) as client:
        # Register user
        registered = client.post("/api/auth/register", json={
            "fullName": "Sync Test Operator",
            "email": "sync@hydroguard-demo.dev",
            "mobile": "+919900000066",
            "password": "local-test-password",
            "role": "administrator",
        })
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

        # 1. Verify champion is initially AVAILABLE
        champions = client.get("/api/water-champions", headers=headers).json()
        assert len(champions) > 0
        champ = champions[0]
        champ_id = champ["id"]
        assert champ["availability_status"] == "AVAILABLE"
        assert champ["status"] == "available"

        # 2. Trigger simulated alert
        reading_res = client.post("/api/sensor-data", json={
            "sensorId": "S1",
            "flowLpm": 18.6,
            "pressureBar": 1.8,
            "tankLevelPercent": 50,
            "deviceId": "SIMULATION",
            "simulatorId": "test-sync-session",
        })
        assert reading_res.status_code == 201
        alert = reading_res.json()["alert"]
        alert_id = alert["id"]

        # 3. Assign champion -> champion becomes ON_SITE, alert becomes ASSIGNED
        assign_res = client.post(
            f"/api/alerts/{alert_id}/assign",
            headers=headers,
            json={"championId": champ_id},
        )
        assert assign_res.status_code == 200
        assert assign_res.json()["status"] == "assigned"

        champ_after_assign = client.get(f"/api/water-champions/{champ_id}", headers=headers).json()
        assert champ_after_assign["availability_status"] == "ON_SITE"
        assert champ_after_assign["status"] == "on-site"

        # 4. Resolve alert -> champion returns to AVAILABLE
        resolve_res = client.post(f"/api/alerts/{alert_id}/resolve", headers=headers)
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "resolved"

        champ_after_resolve = client.get(f"/api/water-champions/{champ_id}", headers=headers).json()
        assert champ_after_resolve["availability_status"] == "AVAILABLE"
        assert champ_after_resolve["status"] == "available"

        # 5. Maintenance completion resolves linked alert and resets champion
        reading_res_2 = client.post("/api/sensor-data", json={
            "sensorId": "S2",
            "flowLpm": 20.0,
            "pressureBar": 1.7,
            "tankLevelPercent": 45,
            "deviceId": "SIMULATION",
            "simulatorId": "test-maint-session",
        })
        alert_2_id = reading_res_2.json()["alert"]["id"]

        maint_res = client.post(
            f"/api/alerts/{alert_2_id}/maintenance",
            headers=headers,
            json={"championId": champ_id, "description": "Emergency pipe patching"},
        )
        assert maint_res.status_code == 201
        maint_record_id = maint_res.json()["id"]

        # Assign alert
        client.post(
            f"/api/alerts/{alert_2_id}/assign",
            headers=headers,
            json={"championId": champ_id},
        )
        assert client.get(f"/api/water-champions/{champ_id}", headers=headers).json()["availability_status"] == "ON_SITE"

        # Complete maintenance order
        patch_res = client.patch(
            f"/api/maintenance/{maint_record_id}",
            headers=headers,
            json={"status": "completed", "action_taken": "Replaced valve clamp"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "completed"

        # Linked alert should now be RESOLVED
        linked_alert = client.get(f"/api/alerts/{alert_2_id}", headers=headers).json()
        assert linked_alert["status"] == "resolved"

        # Champion should now be AVAILABLE
        assert client.get(f"/api/water-champions/{champ_id}", headers=headers).json()["availability_status"] == "AVAILABLE"

        # 6. Water loss calculations for known duration
        # Insert a controlled alert with 10 minutes duration and flow 18.6 (delta = 10.0 L/min vs normal 8.6)
        from datetime import timedelta
        with SessionLocal() as db:
            db.query(Alert).filter(Alert.source.in_(["SIMULATED", "SIMULATOR"])).delete()
            past_start = datetime.now(timezone.utc) - timedelta(minutes=10)
            past_resolved = datetime.now(timezone.utc)
            test_loss_alert = Alert(
                pipeline_id=1,
                sensor_id=1,
                alert_type="LEAK",
                severity="CRITICAL",
                message="Controlled water loss test alert",
                flow_rate=18.6,
                pressure=1.8,
                status="RESOLVED",
                source="SIMULATED",
                simulator_id="math-test-session",
                created_at=past_start,
                resolved_at=past_resolved,
            )
            db.add(test_loss_alert)
            db.commit()

        profile = client.get("/api/simulation/profile", headers=headers).json()
        normal_flow = profile["normal"]["flow"]
        alert_flow = 18.6
        expected_delta = max(0.0, alert_flow - normal_flow)
        expected_loss = expected_delta * 10.0
        expected_saving = max(0.0, (expected_delta * 360) - expected_loss)

        loss_res = client.get("/api/simulation/water-loss", headers=headers)
        assert loss_res.status_code == 200
        loss_data = loss_res.json()
        assert loss_data["is_simulated_estimate"] is True
        assert loss_data["label"] == "Simulated estimate"
        assert loss_data["assumed_manual_delay_minutes"] == 360

        assert abs(loss_data["total_litres_lost"] - expected_loss) < 1.0
        assert abs(loss_data["total_projected_saving_litres"] - expected_saving) < 10.0
        assert len(loss_data["zones"]) > 0