from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Alert, Pipeline, Sensor, SensorReading, Tank, User, WaterChampion
from app.schemas import PipelineCreate, PipelineUpdate, SensorCreate, SensorDataInput, SensorUpdate
from app.services.sensor_processing import find_sensor, process_sensor_reading
from app.views import alert_risk_level, alert_view, pipeline_view, sensor_view, tank_view

public_router = APIRouter(prefix="/api", tags=["health and telemetry"])
router = APIRouter(prefix="/api", tags=["network monitoring"], dependencies=[Depends(get_current_user)])


@public_router.get("/health")
def health():
    return {"status": "healthy", "service": "HydroGuard Backend"}


@public_router.get("/healthz")
def healthz():
    return {"status": "ok", "service": "HydroGuard Backend"}


def _pipeline(db: Session, identifier: str) -> Pipeline | None:
    pipeline = db.scalar(select(Pipeline).where(Pipeline.pipeline_code == identifier))
    if pipeline is None and identifier.isdigit():
        pipeline = db.get(Pipeline, int(identifier))
    return pipeline


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    pipelines = db.scalars(select(Pipeline)).all()
    sensors = db.scalars(select(Sensor)).all()
    tanks = db.scalars(select(Tank)).all()
    alerts = db.scalars(select(Alert).where(Alert.status != "RESOLVED")).all()
    readings = db.scalars(
        select(SensorReading)
        .where(SensorReading.source == "FIELD")
        .order_by(SensorReading.timestamp.desc())
        .limit(500)
    ).all()
    latest_by_sensor: dict[int, SensorReading] = {}
    for reading in readings:
        latest_by_sensor.setdefault(reading.sensor_id, reading)
    pressures = [r.pressure for r in latest_by_sensor.values() if r.pressure is not None]
    flows = [r.flow_rate for r in latest_by_sensor.values() if r.flow_rate is not None]
    active = [s for s in sensors if s.status != "OFFLINE"]
    critical = sum(1 for a in alerts if a.severity == "CRITICAL")
    warnings = sum(1 for a in alerts if a.severity == "WARNING")
    field_critical = sum(1 for a in alerts if a.severity == "CRITICAL" and a.source == "FIELD")
    field_warnings = sum(1 for a in alerts if a.severity == "WARNING" and a.source == "FIELD")
    risk_counts = {
        level: sum(1 for alert in alerts if alert_risk_level(db, alert) == level.upper())
        for level in ("low", "medium", "high")
    }
    simulated_alerts = sum(1 for alert in alerts if alert.source.upper() in ("SIMULATED", "SIMULATOR"))
    field_alerts = len(alerts) - simulated_alerts
    status = "critical" if critical else "attention" if warnings else "operational"
    risk_level = "critical" if critical >= 3 else "high" if critical else "medium" if warnings else "low"
    return {
        "total_pipelines": len(pipelines),
        "active_pipelines": sum(p.status != "INACTIVE" for p in pipelines),
        "warning_pipelines": sum(p.status == "WARNING" for p in pipelines),
        "leaking_pipelines": sum(p.status == "LEAK" for p in pipelines),
        "inactive_pipelines": sum(p.status == "INACTIVE" for p in pipelines),
        "total_sensors": len(sensors),
        "online_sensors": sum(s.status != "OFFLINE" for s in sensors),
        "offline_sensors": sum(s.status == "OFFLINE" for s in sensors),
        "total_tanks": len(tanks),
        "active_alerts": len(alerts),
        "critical_alerts": critical,
        "average_pressure": round(sum(pressures) / len(pressures), 2) if pressures else 0,
        "average_flow_rate": round(sum(flows) / len(flows), 2) if flows else 0,
        "total_pipeline_length_km": round(sum(p.length_km for p in pipelines), 2),
        "systemStatus": status,
        "metrics": {
            "pipelineLengthKm": round(sum(p.length_km for p in pipelines), 2),
            "activeFlowMeters": sum(s.sensor_type == "FLOW" for s in active),
            "onlineSensors": len(active),
            "totalSensors": len(sensors),
            "activeAlerts": len(alerts),
            "lowRiskAlerts": risk_counts["low"],
            "mediumRiskAlerts": risk_counts["medium"],
            "highRiskAlerts": risk_counts["high"],
            "simulatedActiveAlerts": simulated_alerts,
            "fieldActiveAlerts": field_alerts,
            "averagePressureBar": round(sum(pressures) / len(pressures), 2) if pressures else 0,
            "tankLevelPercent": round(sum(t.current_level / t.capacity_liters * 100 for t in tanks) / len(tanks)) if tanks else 0,
            "waterLossPercent": round(min(100, field_critical * 4.2 + field_warnings * 1.5), 1),
        },
        "recentAlerts": [alert_view(db, a) for a in sorted(alerts, key=lambda a: a.created_at, reverse=True)[:5]],
        "risk": {
            "level": risk_level,
            "explanation": "Critical risk from active leak alerts." if critical else "Warnings need field review." if warnings else "Current readings are within normal ranges.",
            "factors": ([f"{critical} critical alert(s)"] if critical else []) + ([f"{warnings} warning alert(s)"] if warnings else []) + ([f"{simulated_alerts} simulated alert(s)"] if simulated_alerts else []) + ["Pressure and flow readings"],
        },
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/pipelines")
def list_pipelines(db: Session = Depends(get_db)):
    return [pipeline_view(db, p) for p in db.scalars(select(Pipeline).order_by(Pipeline.id)).all()]


@router.get("/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: str, db: Session = Depends(get_db)):
    pipeline = _pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    return pipeline_view(db, pipeline)


@router.post("/pipelines", status_code=201)
def create_pipeline(data: PipelineCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    values = data.model_dump()
    values["end_latitude"] = values["end_latitude"] or values["latitude"]
    values["end_longitude"] = values["end_longitude"] or values["longitude"]
    values["status"] = values["status"].upper()
    pipeline = Pipeline(**values)
    db.add(pipeline)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Pipeline code is already in use.")
    db.refresh(pipeline)
    return pipeline_view(db, pipeline)


@router.put("/pipelines/{pipeline_id}")
def update_pipeline(pipeline_id: str, data: PipelineUpdate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    pipeline = _pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(pipeline, key, value.upper() if key == "status" and value else value)
    db.commit()
    db.refresh(pipeline)
    return pipeline_view(db, pipeline)


@router.delete("/pipelines/{pipeline_id}", status_code=204)
def delete_pipeline(pipeline_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    pipeline = _pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    if pipeline.sensors:
        raise HTTPException(status_code=409, detail="Move or remove the pipeline's sensors before deleting it.")
    db.delete(pipeline)
    db.commit()


@router.get("/sensors")
def list_sensors(db: Session = Depends(get_db)):
    return [sensor_view(db, s) for s in db.scalars(select(Sensor).order_by(Sensor.id)).all()]


@router.get("/sensors/{sensor_id}")
def get_sensor(sensor_id: str, db: Session = Depends(get_db)):
    sensor = find_sensor(db, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")
    return sensor_view(db, sensor)


@router.get("/sensors/{sensor_id}/readings")
def sensor_readings(sensor_id: str, hours: int = Query(default=24, ge=1, le=8760), db: Session = Depends(get_db)):
    sensor = find_sensor(db, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.scalars(select(SensorReading).where(
        SensorReading.sensor_id == sensor.id, SensorReading.timestamp >= cutoff
    ).order_by(SensorReading.timestamp.desc())).all()
    return [{
        "id": str(row.id), "sensor_id": row.sensor_id, "sensorId": sensor.sensor_code,
        "flow_rate": row.flow_rate, "flowLpm": row.flow_rate, "pressure": row.pressure,
        "pressureBar": row.pressure, "tank_level": row.tank_level, "tankLevelPercent": row.tank_level,
        "battery_level": row.battery_level, "timestamp": row.timestamp.isoformat(),
        "source": row.source.lower(), "simulated": row.source.upper() in ("SIMULATED", "SIMULATOR"),
        "simulatorId": row.simulator_id,
    } for row in rows]


@router.post("/sensors", status_code=201)
def create_sensor(data: SensorCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if db.get(Pipeline, data.pipeline_id) is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    sensor = Sensor(**data.model_dump(), status="ONLINE", last_seen=datetime.now(timezone.utc))
    db.add(sensor)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sensor code is already in use.")
    db.refresh(sensor)
    return sensor_view(db, sensor)


@router.put("/sensors/{sensor_id}")
def update_sensor(sensor_id: str, data: SensorUpdate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    sensor = find_sensor(db, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "pipeline_id" and value and db.get(Pipeline, value) is None:
            raise HTTPException(status_code=404, detail="Pipeline not found.")
        setattr(sensor, key, value.upper() if key == "status" and value else value)
    db.commit()
    db.refresh(sensor)
    return sensor_view(db, sensor)


@public_router.post("/sensor-data", status_code=201)
def receive_sensor_data(data: SensorDataInput, db: Session = Depends(get_db)):
    return process_sensor_reading(db, data)


@router.get("/map")
def map_data(db: Session = Depends(get_db)):
    pipelines = db.scalars(select(Pipeline).order_by(Pipeline.id)).all()
    sensors = db.scalars(select(Sensor).order_by(Sensor.id)).all()
    tanks = db.scalars(select(Tank).order_by(Tank.id)).all()
    alerts = db.scalars(select(Alert).where(Alert.status != "RESOLVED").order_by(Alert.created_at.desc())).all()
    champions = db.scalars(select(WaterChampion).order_by(WaterChampion.id)).all()
    return {
        "tanks": [tank_view(t) for t in tanks],
        "sensors": [sensor_view(db, s) for s in sensors],
        "pipelines": [pipeline_view(db, p) for p in pipelines],
        "active_alerts": [alert_view(db, a) for a in alerts],
        "water_champions": [{
            "id": str(c.id), "name": c.name, "code": f"WC-{c.id:03d}",
            "latitude": c.latitude, "longitude": c.longitude,
            "status": c.availability_status.lower(),
        } for c in champions],
    }