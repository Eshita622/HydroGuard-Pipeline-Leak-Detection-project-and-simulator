from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Pipeline, Sensor, SensorReading, SystemSetting, Tank, WaterChampion, utcnow
from app.schemas import SensorDataInput
from app.services.leak_detection import (
    DEFAULT_THRESHOLDS,
    Thresholds,
    classify_reading,
    classify_risk_level,
)
from app.services.sms_service import send_sms
from app.views import alert_view, sensor_view


def load_thresholds(db: Session) -> Thresholds:
    saved = db.get(SystemSetting, "thresholds")
    if saved is None:
        return DEFAULT_THRESHOLDS
    return Thresholds(
        flow_warning=saved.flow_warning,
        flow_leak=saved.flow_leak,
        pressure_warning=saved.pressure_warning,
        pressure_leak=saved.pressure_leak,
    )


def find_sensor(db: Session, sensor_id: str) -> Sensor | None:
    sensor = db.scalar(select(Sensor).where(Sensor.sensor_code == sensor_id))
    if sensor is None and sensor_id.isdigit():
        sensor = db.get(Sensor, int(sensor_id))
    return sensor


def process_sensor_reading(db: Session, data: SensorDataInput) -> dict:
    sensor = find_sensor(db, data.sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail=f"Sensor {data.sensor_id} is not registered.")
    if data.device_id and data.device_id != "SIMULATION" and sensor.device_id and sensor.device_id != data.device_id:
        raise HTTPException(status_code=403, detail="The device ID does not match this registered sensor.")

    stamp = data.timestamp or utcnow()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    flow, pressure, tank_level = data.flow, data.pressure_value, data.tank
    thresholds = load_thresholds(db)
    is_simulated = data.device_id == "SIMULATION" or (data.source is not None and data.source.upper() in ("SIMULATION", "SIMULATED", "SIMULATOR"))
    source = "SIMULATED" if is_simulated else "FIELD"
    simulator_id = data.simulator_id if is_simulated else None
    battery = data.battery if data.battery is not None else sensor.battery_level
    classification = classify_reading(flow, pressure, thresholds)
    risk_level = classify_risk_level(classification, flow, pressure, thresholds)

    db.add(SensorReading(
        sensor_id=sensor.id,
        flow_rate=flow,
        pressure=pressure,
        tank_level=tank_level,
        battery_level=battery,
        timestamp=stamp,
        source=source,
        simulator_id=simulator_id,
    ))

    pipeline = db.get(Pipeline, sensor.pipeline_id)
    # Simulated readings are an overlay: they must never change seeded sensor,
    # pipeline, tank, champion, or field-alert records.
    if not is_simulated:
        if data.device_id:
            sensor.device_id = data.device_id
        sensor.battery_level = battery
        sensor.last_seen = stamp
        sensor.status = classification
        tank = db.scalar(select(Tank).order_by(Tank.id).limit(1))
        if tank is not None:
            tank.current_level = tank.capacity_liters * tank_level / 100
            tank.status = "LOW" if tank_level < 20 else "NORMAL"

    alert_type = (
        "LEAK_DETECTED" if classification == "LEAK"
        else "HIGH_FLOW" if classification == "WARNING" and flow > thresholds.flow_warning
        else "LOW_PRESSURE" if classification == "WARNING"
        else None
    )
    alert = None
    previous_risk_level = None
    if alert_type:
        alert_query = select(Alert).where(
            Alert.sensor_id == sensor.id,
            Alert.source == source,
            Alert.status != "RESOLVED",
        )
        if is_simulated and simulator_id is not None:
            alert_query = alert_query.where(Alert.simulator_id == simulator_id)
        alert = db.scalar(alert_query.order_by(Alert.created_at.desc()).limit(1))
        if alert is None:
            alert = Alert(
                pipeline_id=sensor.pipeline_id,
                sensor_id=sensor.id,
                alert_type=alert_type,
                severity="CRITICAL" if classification == "LEAK" else "WARNING",
                message=f"{risk_level.title()} risk · {classification.title()} condition at {sensor.location} ({sensor.sensor_code}).",
                flow_rate=flow,
                pressure=pressure,
                risk_level=risk_level,
                source=source,
                simulator_id=simulator_id,
                status="ACTIVE",
                created_at=stamp,
            )
            db.add(alert)
        else:
            previous_risk_level = alert.risk_level
            alert.flow_rate = flow
            alert.pressure = pressure
            alert.alert_type = alert_type
            alert.severity = "CRITICAL" if classification == "LEAK" else "WARNING"
            alert.risk_level = risk_level
            alert.message = f"{risk_level.title()} risk · {classification.title()} condition at {sensor.location} ({sensor.sensor_code})."
    else:
        # Auto-clear for simulations: when a SIMULATED sensor returns to NORMAL,
        # resolve its active SIMULATED alert with note "auto-resolved: readings normal".
        # Never auto-resolve FIELD alerts.
        if is_simulated:
            open_alerts_query = select(Alert).where(
                Alert.sensor_id == sensor.id,
                Alert.source == source,
                Alert.status != "RESOLVED",
            )
            if simulator_id is not None:
                open_alerts_query = open_alerts_query.where(Alert.simulator_id == simulator_id)
            for open_alert in db.scalars(open_alerts_query):
                open_alert.status = "RESOLVED"
                open_alert.resolved_at = stamp
                if "auto-resolved: readings normal" not in open_alert.message:
                    open_alert.message = f"{open_alert.message} — auto-resolved: readings normal"

    db.flush()
    if pipeline is not None and not is_simulated:
        sensor_states = db.scalars(select(Sensor.status).where(Sensor.pipeline_id == pipeline.id)).all()
        if "LEAK" in sensor_states:
            pipeline.status = "LEAK"
        elif "WARNING" in sensor_states:
            pipeline.status = "WARNING"
        else:
            pipeline.status = "NORMAL"

    db.commit()
    db.refresh(sensor)
    if alert is not None:
        db.refresh(alert)

    mock_sms = None
    risk_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    should_mock_sms = (
        risk_level == "HIGH"
        and (previous_risk_level is None or risk_rank.get(previous_risk_level, 0) < risk_rank["HIGH"])
    )
    if should_mock_sms and alert is not None:
        champion = None
        if alert.assigned_to:
            champion = db.get(WaterChampion, alert.assigned_to)
        if champion is None and pipeline is not None:
            champion = db.scalar(
                select(WaterChampion)
                .where(
                    WaterChampion.assigned_zone == pipeline.zone,
                    WaterChampion.availability_status == "AVAILABLE",
                )
                .order_by(WaterChampion.id)
                .limit(1)
            )
        if champion is None:
            champion = db.scalar(
                select(WaterChampion)
                .where(WaterChampion.availability_status == "AVAILABLE")
                .order_by(WaterChampion.id)
                .limit(1)
            )
        zone = pipeline.zone if pipeline else "Unassigned zone"
        sms_message = (
            "HYDROGUARD Alert: Possible WATER LEAKAGE detected!\n"
            f"Location: {zone} · {sensor.location}\n"
            f"Abnormal Flow: {flow:g} L/min (High)\n"
            f"Time: {stamp.isoformat()}\n"
            "Action: Please inspect and take necessary action.\n"
            "– HydroGuard Team"
        )
        mock_sms = send_sms(
            champion.phone if champion else None,
            sms_message,
            alert_id=str(alert.id),
            zone=zone,
            risk_level="high",
            source=source,
        )

    reading_payload = sensor_view(db, sensor)
    alert_payload = alert_view(db, alert) if alert else None
    effective_pipeline_status = pipeline.status.lower() if pipeline else classification.lower()
    if is_simulated and alert is not None:
        effective_pipeline_status = "leak" if risk_level == "HIGH" else "warning"
    return {
        "reading": reading_payload,
        "pipelineStatus": effective_pipeline_status,
        "classification": classification,
        "riskLevel": risk_level.lower() if risk_level else "none",
        "source": source.lower(),
        "simulated": is_simulated,
        "alertStatus": alert.status.lower() if alert else None,
        "alert": alert_payload,
        "mockSms": mock_sms,
        "notificationsStatus": "mock_sent" if mock_sms else "disabled",
        "message": (
            "High risk leak condition recorded and a critical alert is active."
            if classification == "LEAK"
            else "Warning condition recorded for review."
            if classification == "WARNING"
            else "Reading is within the configured normal range."
        ),
    }