import math
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    MaintenanceLog,
    Pipeline,
    Sensor,
    SensorReading,
    SystemSetting,
    Tank,
    WaterChampion,
)
from app.services.leak_detection import DEFAULT_THRESHOLDS

PUNE_CENTER = (18.5204, 73.8567)
SEED_DEMO_CHAMPIONS = os.getenv("HYDROGUARD_SEED_DEMO_CHAMPIONS", "0") == "1"


def seed_demo_champions(db: Session) -> None:
    """Keep the demo field-team roster available for existing databases too."""
    if not SEED_DEMO_CHAMPIONS:
        return
    if db.scalar(select(WaterChampion.id).limit(1)) is not None:
        return
    db.add_all([
        WaterChampion(name="Aarav Kulkarni", phone="+919800000001", assigned_zone="Zone 1", latitude=18.5204, longitude=73.8567),
        WaterChampion(name="Meera Patil", phone="+919800000002", assigned_zone="Zone 2", latitude=18.5261, longitude=73.8622),
        WaterChampion(name="Rohan Jadhav", phone="+919800000003", assigned_zone="Zone 3", latitude=18.5147, longitude=73.8481),
        WaterChampion(name="Sana Shaikh", phone="+919800000004", assigned_zone="Zone 4", latitude=18.5330, longitude=73.8710),
    ])


def seed_demo_data(db: Session) -> None:
    """Insert a stable, Pune-based demo network once; never overwrite user data."""
    if db.scalar(select(Pipeline.id).limit(1)) is not None:
        if db.get(SystemSetting, "thresholds") is None:
            db.add(SystemSetting(key="thresholds"))
        seed_demo_champions(db)
        db.commit()
        return

    now = datetime.now(timezone.utc)
    pipelines = []
    for index in range(24):
        row, col = divmod(index, 6)
        lat = PUNE_CENTER[0] + (row - 1.5) * 0.006 + (col % 2) * 0.0007
        lon = PUNE_CENTER[1] + (col - 2.5) * 0.006
        status = "LEAK" if index == 1 else "WARNING" if index == 2 else "INACTIVE" if index == 22 else "NORMAL"
        pipeline = Pipeline(
            pipeline_code=f"HG-P-{index + 1:03d}",
            name=f"Zone {(index % 4) + 1} distribution line {index + 1:02d}",
            zone=f"Zone {(index % 4) + 1}",
            location=["Shivajinagar", "Deccan", "Kothrud", "Erandwane", "Karve Nagar", "Model Colony"][index % 6],
            length_km=round(0.7 + (index % 7) * 0.23, 2),
            status=status,
            latitude=lat,
            longitude=lon,
            end_latitude=lat + 0.0021,
            end_longitude=lon + 0.0028,
        )
        db.add(pipeline)
        pipelines.append(pipeline)
    db.flush()

    extra_pipelines_info = [
        ("HG-P-025", "Zone 5 distribution line 25", "Zone 5", "Viman Nagar", 1.15, 18.5679, 73.9143),
        ("HG-P-026", "Zone 6 distribution line 26", "Zone 6", "Aundh", 1.38, 18.5580, 73.8077),
        ("HG-P-027", "Zone 7 distribution line 27", "Zone 7", "Baner", 1.61, 18.5590, 73.7868),
        ("HG-P-028", "Zone 8 distribution line 28", "Zone 8", "Hadapsar", 1.04, 18.5089, 73.9259),
        ("HG-P-029", "Zone 9 distribution line 29", "Zone 9", "Kalyani Nagar", 1.27, 18.5463, 73.9033),
    ]
    for code, name, zone, loc, length, lat, lon in extra_pipelines_info:
        pipe = Pipeline(
            pipeline_code=code,
            name=name,
            zone=zone,
            location=loc,
            length_km=length,
            status="NORMAL",
            latitude=lat,
            longitude=lon,
            end_latitude=lat + 0.0021,
            end_longitude=lon + 0.0028,
        )
        db.add(pipe)
        pipelines.append(pipe)
    db.flush()

    tanks = [
        Tank(name="Hill View Reservoir", location="Kothrud", capacity_liters=250_000, current_level=182_500, latitude=18.5078, longitude=73.8074, status="NORMAL"),
        Tank(name="Central Overhead Tank", location="Shivajinagar", capacity_liters=180_000, current_level=111_600, latitude=18.5312, longitude=73.8528, status="NORMAL"),
        Tank(name="East Distribution Tank", location="Erandwane", capacity_liters=140_000, current_level=56_000, latitude=18.5122, longitude=73.8671, status="NORMAL"),
    ]
    db.add_all(tanks)
    db.flush()

    sensors: list[Sensor] = []
    for index in range(18):
        pipeline = pipelines[index]
        lat = pipeline.latitude + 0.0009
        lon = pipeline.longitude + 0.0011
        status = "LEAK" if index == 1 else "WARNING" if index == 2 else "OFFLINE" if index in (10, 15) else "ONLINE"
        sensor = Sensor(
            sensor_code=f"S{index + 1}",
            device_id=f"HG-ESP32-{index + 1:03d}",
            pipeline_id=pipeline.id,
            sensor_type=("FLOW", "PRESSURE", "TANK_LEVEL", "ACOUSTIC")[index % 4],
            location=f"{pipeline.location} · monitoring point {index + 1}",
            latitude=lat,
            longitude=lon,
            status=status,
            battery_level=round(70 + (index * 7 % 30), 1),
            last_seen=now - (timedelta(days=2) if status == "OFFLINE" else timedelta(minutes=index * 3)),
        )
        db.add(sensor)
        sensors.append(sensor)

    extra_sensors_info = [
        ("S19", "HG-ESP32-019", pipelines[1].id, pipelines[1]),
        ("S20", "HG-ESP32-020", pipelines[2].id, pipelines[2]),
        ("S21", "HG-ESP32-021", pipelines[3].id, pipelines[3]),
        ("S22", "HG-ESP32-022", pipelines[24].id, pipelines[24]),
        ("S23", "HG-ESP32-023", pipelines[25].id, pipelines[25]),
        ("S24", "HG-ESP32-024", pipelines[26].id, pipelines[26]),
        ("S25", "HG-ESP32-025", pipelines[27].id, pipelines[27]),
        ("S26", "HG-ESP32-026", pipelines[28].id, pipelines[28]),
    ]
    for idx, (code, dev_id, pipe_id, pipe) in enumerate(extra_sensors_info, start=19):
        sensor = Sensor(
            sensor_code=code,
            device_id=dev_id,
            pipeline_id=pipe_id,
            sensor_type="FLOW",
            location=f"{pipe.location} · monitoring point {idx}",
            latitude=pipe.latitude + 0.0009,
            longitude=pipe.longitude + 0.0011,
            status="ONLINE",
            battery_level=round(75 + (idx * 3 % 20), 1),
            last_seen=now - timedelta(minutes=idx),
        )
        db.add(sensor)
        sensors.append(sensor)
    db.flush()

    for index, sensor in enumerate(sensors):
        for sample in range(24):
            at = now - timedelta(hours=23 - sample)
            flow = 7.5 + (index % 6) * 0.62 + 0.45 * math.sin(sample / 3)
            pressure = 3.1 + 0.12 * math.cos(sample / 4) - (index % 3) * 0.04
            tank_level = 63 + 8 * math.sin(sample / 8 + index / 5)
            if index == 1 and sample == 23:
                flow, pressure = 18.6, 1.8
            elif index == 2 and sample == 23:
                flow, pressure = 13.5, 2.4
            db.add(SensorReading(
                sensor_id=sensor.id,
                flow_rate=round(flow, 2),
                pressure=round(pressure, 2),
                tank_level=round(max(0, min(100, tank_level)), 1),
                battery_level=sensor.battery_level,
                timestamp=at,
            ))
    db.flush()

    seeded_alerts = [
        Alert(
            pipeline_id=pipelines[1].id, sensor_id=sensors[1].id, assigned_to=None,
            alert_type="LEAK_DETECTED", severity="CRITICAL",
            message=f"Leak condition at {sensors[1].location} (S2).",
            flow_rate=18.6, pressure=1.8, status="ACTIVE", created_at=now - timedelta(minutes=15),
        ),
        Alert(
            pipeline_id=pipelines[2].id, sensor_id=sensors[2].id, assigned_to=None,
            alert_type="LOW_PRESSURE", severity="WARNING",
            message=f"Pressure below operating range at {sensors[2].location}.",
            flow_rate=13.5, pressure=2.4, status="ACKNOWLEDGED",
            created_at=now - timedelta(hours=1), acknowledged_at=now - timedelta(minutes=45),
        ),
        Alert(
            pipeline_id=pipelines[10].id, sensor_id=sensors[10].id,
            alert_type="SENSOR_OFFLINE", severity="WARNING",
            message=f"Sensor {sensors[10].sensor_code} has not reported recently.",
            flow_rate=None, pressure=None, status="ACTIVE", created_at=now - timedelta(hours=2),
        ),
    ]
    db.add_all(seeded_alerts)
    db.flush()
    db.add_all([
        MaintenanceLog(
            pipeline_id=pipelines[1].id, alert_id=seeded_alerts[0].id, assigned_to=None,
            description="Zone 2 distribution line 02 — Inspect the coupling near sensor S2.",
            action_taken=None, status="IN_PROGRESS", created_at=now - timedelta(minutes=10),
        ),
        MaintenanceLog(
            pipeline_id=pipelines[0].id, assigned_to=None,
            description="Zone 1 distribution line 01 — Calibrate the flow meter.",
            action_taken="Recalibrated and verified against manual gauge.",
            status="COMPLETED", created_at=now - timedelta(days=2), completed_at=now - timedelta(days=1),
        ),
        MaintenanceLog(
            pipeline_id=pipelines[2].id, alert_id=seeded_alerts[1].id, assigned_to=None,
            description="Zone 3 distribution line 03 — Check the pressure regulator.",
            action_taken=None, status="PENDING", created_at=now - timedelta(minutes=30),
        ),
    ])
    db.add(SystemSetting(
        key="thresholds",
        flow_warning=DEFAULT_THRESHOLDS.flow_warning,
        flow_leak=DEFAULT_THRESHOLDS.flow_leak,
        pressure_warning=DEFAULT_THRESHOLDS.pressure_warning,
        pressure_leak=DEFAULT_THRESHOLDS.pressure_leak,
    ))
    seed_demo_champions(db)
    db.commit()
