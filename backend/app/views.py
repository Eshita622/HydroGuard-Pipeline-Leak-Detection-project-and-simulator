from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, MaintenanceLog, Pipeline, Sensor, SensorReading, SystemSetting, Tank, WaterChampion
from app.services.leak_detection import (
    DEFAULT_THRESHOLDS,
    Thresholds,
    classify_reading,
    classify_risk_level,
)
from app.services.sms_service import sms_for_alert


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def alert_risk_level(db: Session, alert: Alert) -> str | None:
    if alert.risk_level:
        return alert.risk_level.upper()
    if alert.flow_rate is None or alert.pressure is None:
        return "HIGH" if alert.severity == "CRITICAL" else None
    saved = db.get(SystemSetting, "thresholds")
    thresholds = Thresholds(
        flow_warning=saved.flow_warning,
        flow_leak=saved.flow_leak,
        pressure_warning=saved.pressure_warning,
        pressure_leak=saved.pressure_leak,
    ) if saved else DEFAULT_THRESHOLDS
    classification = classify_reading(alert.flow_rate, alert.pressure, thresholds)
    return classify_risk_level(classification, alert.flow_rate, alert.pressure, thresholds)


def pipeline_view(db: Session, pipeline: Pipeline) -> dict:
    sensors = db.scalars(select(Sensor).where(Sensor.pipeline_id == pipeline.id)).all()
    sensor_views = {sensor.id: sensor_view(db, sensor) for sensor in sensors}
    tanks = db.scalars(select(Tank).order_by(Tank.id)).all()
    points = [[pipeline.latitude, pipeline.longitude], [pipeline.end_latitude, pipeline.end_longitude]]
    simulated_alerts = db.scalars(select(Alert).where(
        Alert.pipeline_id == pipeline.id,
        Alert.source.in_(["SIMULATED", "SIMULATOR"]),
        Alert.status != "RESOLVED",
    )).all()
    simulated_risks = [alert_risk_level(db, alert) for alert in simulated_alerts]
    effective_status = (
        "leak" if "HIGH" in simulated_risks
        else "warning" if simulated_alerts
        else pipeline.status.lower()
    )
    return {
        "id": str(pipeline.id),
        "pipeline_id": pipeline.id,
        "pipeline_code": pipeline.pipeline_code,
        "code": pipeline.pipeline_code,
        "name": pipeline.name,
        "zone": pipeline.zone,
        "location": pipeline.location,
        "length_km": pipeline.length_km,
        "status": effective_status,
        "status_code": pipeline.status,
        "source": "simulator" if simulated_alerts else "field",
        "simulated": bool(simulated_alerts),
        "latitude": pipeline.latitude,
        "longitude": pipeline.longitude,
        "start_coordinates": points[0],
        "end_coordinates": points[1],
        "coordinates": points,
        "flowLpm": latest_reading(db, sensors[0].id).flow_rate if sensors and latest_reading(db, sensors[0].id) else 0,
        "pressureBar": latest_reading(db, sensors[0].id).pressure if sensors and latest_reading(db, sensors[0].id) else 0,
        "detectedAt": None,
        "tanks": [
            {
                "id": str(t.id),
                "name": t.name,
                "levelPercent": round(t.current_level / t.capacity_liters * 100, 1),
                "coordinates": [t.latitude, t.longitude],
            }
            for t in tanks[:1]
        ],
        "sensors": [
            {
                "sensorId": s.sensor_code,
                "status": sensor_views[s.id]["status"],
                "coordinates": [s.latitude, s.longitude],
                "location": s.location,
                "source": sensor_views[s.id]["source"],
                "simulated": sensor_views[s.id]["simulated"],
            }
            for s in sensors
        ],
        "created_at": iso(pipeline.created_at),
    }


def latest_reading(db: Session, sensor_id: int) -> SensorReading | None:
    return db.scalar(
        select(SensorReading)
        .where(SensorReading.sensor_id == sensor_id)
        .order_by(SensorReading.timestamp.desc(), SensorReading.id.desc())
        .limit(1)
    )


def sensor_view(db: Session, sensor: Sensor) -> dict:
    reading = latest_reading(db, sensor.id)
    simulated_alert = db.scalar(select(Alert).where(
        Alert.sensor_id == sensor.id,
        Alert.source.in_(["SIMULATED", "SIMULATOR"]),
        Alert.status != "RESOLVED",
    ).order_by(Alert.created_at.desc()).limit(1))
    simulated_risk = alert_risk_level(db, simulated_alert) if simulated_alert else None
    status = (
        "leak" if simulated_risk == "HIGH"
        else "warning" if simulated_alert
        else sensor.status.lower()
    )
    reading_source = reading.source.lower() if reading else "field"
    is_simulated = reading.source.upper() in ("SIMULATED", "SIMULATOR") if reading else False
    return {
        "id": str(sensor.id),
        "sensor_db_id": sensor.id,
        "sensor_id": sensor.sensor_code,
        "sensor_code": sensor.sensor_code,
        "device_id": sensor.device_id,
        "pipeline_id": sensor.pipeline_id,
        "pipelineId": str(sensor.pipeline_id),
        "pipeline_code": sensor.pipeline.pipeline_code if sensor.pipeline else None,
        "pipelineCode": sensor.pipeline.pipeline_code if sensor.pipeline else None,
        "pipeline_name": sensor.pipeline.name if sensor.pipeline else None,
        "zone": sensor.pipeline.zone if sensor.pipeline else None,
        "sensor_type": sensor.sensor_type,
        "location": sensor.location,
        "latitude": sensor.latitude,
        "longitude": sensor.longitude,
        "status": status,
        "status_code": sensor.status,
        "statusSource": "simulator" if simulated_alert else "field",
        "source": reading_source,
        "readingSource": reading_source,
        "simulated": is_simulated,
        "riskLevel": simulated_risk.lower() if simulated_risk else None,
        "simulatorId": simulated_alert.simulator_id if simulated_alert else None,
        "battery_level": sensor.battery_level,
        "batteryPercent": sensor.battery_level,
        "flow_rate": reading.flow_rate if reading else 0,
        "flowLpm": reading.flow_rate if reading else 0,
        "pressure": reading.pressure if reading else 0,
        "pressureBar": reading.pressure if reading else 0,
        "tank_level": reading.tank_level if reading else 0,
        "tankLevelPercent": reading.tank_level if reading else 0,
        "last_seen": iso(sensor.last_seen),
        "lastUpdated": iso(reading.timestamp if reading else sensor.last_seen or sensor.created_at),
        "created_at": iso(sensor.created_at),
    }


def tank_view(tank: Tank) -> dict:
    level_percent = round((tank.current_level / tank.capacity_liters) * 100, 1)
    return {
        "id": str(tank.id),
        "name": tank.name,
        "location": tank.location,
        "capacity_liters": tank.capacity_liters,
        "current_level": tank.current_level,
        "level_percent": level_percent,
        "levelPercent": level_percent,
        "latitude": tank.latitude,
        "longitude": tank.longitude,
        "coordinates": [tank.latitude, tank.longitude],
        "status": tank.status.lower(),
        "status_code": tank.status,
    }


def alert_view(db: Session, alert: Alert) -> dict:
    sensor = db.get(Sensor, alert.sensor_id) if alert.sensor_id else None
    pipeline = db.get(Pipeline, alert.pipeline_id) if alert.pipeline_id else None
    champion = db.get(WaterChampion, alert.assigned_to) if alert.assigned_to else None
    risk_level = alert_risk_level(db, alert)
    mock_sms = sms_for_alert(alert.id)
    is_simulated = alert.source.upper() in ("SIMULATED", "SIMULATOR")
    return {
        "id": str(alert.id),
        "pipeline_id": alert.pipeline_id,
        "sensor_id": alert.sensor_id,
        "alert_type": alert.alert_type,
        "type": alert.alert_type.replace("_", " ").title(),
        "severity": alert.severity.lower(),
        "riskLevel": risk_level.lower() if risk_level else None,
        "riskTitle": f"{risk_level.title()} risk" if risk_level else None,
        "source": alert.source.lower(),
        "simulated": is_simulated,
        "simulatorId": alert.simulator_id,
        "mockSmsMessage": mock_sms["message"] if mock_sms else None,
        "message": alert.message,
        "flow_rate": alert.flow_rate,
        "flowLpm": alert.flow_rate or 0,
        "pressure": alert.pressure,
        "pressureBar": alert.pressure or 0,
        "status": alert.status.lower(),
        "status_code": alert.status,
        "zone": pipeline.zone if pipeline else "",
        "location": sensor.location if sensor else (pipeline.location if pipeline else ""),
        "sensorId": sensor.sensor_code if sensor else "",
        "championId": str(champion.id) if champion else None,
        "championName": champion.name if champion else "Unassigned",
        "created_at": iso(alert.created_at),
        "createdAt": iso(alert.created_at),
        "acknowledged_at": iso(alert.acknowledged_at),
        "resolved_at": iso(alert.resolved_at),
    }


def maintenance_view(db: Session, record: MaintenanceLog) -> dict:
    champion = db.get(WaterChampion, record.assigned_to) if record.assigned_to else None
    pipeline = db.get(Pipeline, record.pipeline_id) if record.pipeline_id else None
    alert = db.get(Alert, record.alert_id) if record.alert_id else None
    location = pipeline.location if pipeline else (alert.sensor.location if alert and alert.sensor else "")
    description = record.description
    return {
        "id": str(record.id),
        "maintenance_id": f"MNT-{record.id:04d}",
        "maintenanceId": f"MNT-{record.id:04d}",
        "pipeline_id": record.pipeline_id,
        "pipeline": pipeline.name if pipeline else description.split(" — ", 1)[0],
        "location": location,
        "alert_id": record.alert_id,
        "alertId": str(record.alert_id) if record.alert_id else None,
        "assigned_to": record.assigned_to,
        "championId": str(champion.id) if champion else None,
        "championName": champion.name if champion else "Unassigned",
        "description": description,
        "issue": description.split(" — ", 1)[-1],
        "action_taken": record.action_taken,
        "priority": "critical" if alert and alert.severity == "CRITICAL" else "medium",
        "status": {"PENDING": "pending", "IN_PROGRESS": "in-progress", "COMPLETED": "completed"}.get(record.status, record.status.lower()),
        "status_code": record.status,
        "created_at": iso(record.created_at),
        "startedAt": iso(record.created_at),
        "completed_at": iso(record.completed_at),
        "completedAt": iso(record.completed_at),
    }


def champion_view(db: Session, champion: WaterChampion) -> dict:
    open_alerts = db.query(Alert).filter(
        Alert.assigned_to == champion.id, Alert.status.in_(["ASSIGNED", "ACKNOWLEDGED"])
    ).count()
    
    resolved_alerts_count = db.query(Alert).filter(
        Alert.assigned_to == champion.id, Alert.status == "RESOLVED"
    ).count()
    unlinked_maint_count = db.query(MaintenanceLog).filter(
        MaintenanceLog.assigned_to == champion.id, 
        MaintenanceLog.status == "COMPLETED", 
        MaintenanceLog.alert_id.is_(None)
    ).count()
    completed = resolved_alerts_count + unlinked_maint_count
    
    response_times = []
    past_alerts = db.query(Alert).filter(
        Alert.assigned_to == champion.id, Alert.assigned_at.is_not(None)
    ).all()
    for a in past_alerts:
        end_time = a.acknowledged_at or a.resolved_at
        if end_time:
            diff = (end_time - a.assigned_at).total_seconds() / 60.0
            if diff >= 0:
                response_times.append(diff)
                
    if response_times:
        avg_response = int(round(sum(response_times) / len(response_times)))
    else:
        avg_response = "-"

    has_simulator_assignment = db.scalar(select(Alert.id).where(
        Alert.assigned_to == champion.id,
        Alert.source.in_(["SIMULATED", "SIMULATOR"]),
        Alert.status != "RESOLVED",
    ).limit(1)) is not None
    status = "ON_SITE" if has_simulator_assignment else champion.availability_status
    return {
        "id": str(champion.id),
        "user_id": champion.user_id,
        "name": champion.name,
        "phone": champion.phone,
        "assigned_zone": champion.assigned_zone,
        "assignedZone": champion.assigned_zone,
        "latitude": champion.latitude,
        "longitude": champion.longitude,
        "availability_status": champion.availability_status,
        "status": status.lower().replace("_", "-"),
        "statusSource": "simulator" if has_simulator_assignment else "field",
        "activeAlerts": open_alerts,
        "completedRepairs": completed,
        "averageResponseMinutes": avg_response,
    }