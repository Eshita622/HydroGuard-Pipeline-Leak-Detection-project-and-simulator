from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import ASSUMED_MANUAL_DELAY_MINUTES
from app.database import get_db
from app.models import Alert, Pipeline, Sensor, User, WaterChampion
from app.schemas import SensorDataInput
from app.services.leak_detection import generate_simulation_profile
from app.services.sensor_processing import load_thresholds, process_sensor_reading

router = APIRouter(prefix="/api/simulation", tags=["simulation"], dependencies=[Depends(get_current_user)])


@router.get("/profile")
def simulation_profile(db: Session = Depends(get_db)):
    thresholds = load_thresholds(db)
    return generate_simulation_profile(thresholds)


@router.get("/water-loss")
def simulation_water_loss(db: Session = Depends(get_db)):
    thresholds = load_thresholds(db)
    profile = generate_simulation_profile(thresholds)
    normal_flow = profile["normal"]["flow"]
    now = datetime.now(timezone.utc)

    simulated_alerts = db.scalars(
        select(Alert).where(Alert.source.in_(["SIMULATED", "SIMULATOR"]))
    ).all()

    total_litres_lost = 0.0
    total_projected_saving = 0.0
    zone_stats: dict[str, dict] = {}

    for alert in simulated_alerts:
        alert_flow = alert.flow_rate if alert.flow_rate is not None else normal_flow
        delta_flow = max(0.0, float(alert_flow) - float(normal_flow))

        created_at = alert.created_at.replace(tzinfo=timezone.utc) if alert.created_at.tzinfo is None else alert.created_at
        end_time = (
            (alert.resolved_at.replace(tzinfo=timezone.utc) if alert.resolved_at.tzinfo is None else alert.resolved_at)
            if (alert.status == "RESOLVED" and alert.resolved_at)
            else now
        )
        duration_minutes = max(0.0, (end_time - created_at).total_seconds() / 60.0)
        litres_lost = delta_flow * duration_minutes
        potential_loss = delta_flow * ASSUMED_MANUAL_DELAY_MINUTES
        projected_saving = max(0.0, potential_loss - litres_lost)

        pipeline = db.get(Pipeline, alert.pipeline_id) if alert.pipeline_id else None
        zone_name = pipeline.zone if pipeline and pipeline.zone else (f"Zone {alert.zone}" if getattr(alert, "zone", None) else "Zone 1")

        if zone_name not in zone_stats:
            zone_stats[zone_name] = {
                "zone": zone_name,
                "litres_lost": 0.0,
                "projected_saving_litres": 0.0,
                "active_leaks_count": 0,
                "alerts_count": 0,
                "is_simulated_estimate": True,
                "label": "Simulated estimate",
            }

        zone_stats[zone_name]["litres_lost"] += litres_lost
        zone_stats[zone_name]["projected_saving_litres"] += projected_saving
        zone_stats[zone_name]["alerts_count"] += 1
        if alert.status != "RESOLVED":
            zone_stats[zone_name]["active_leaks_count"] += 1

        total_litres_lost += litres_lost
        total_projected_saving += projected_saving

    zones_list = []
    for z in sorted(zone_stats.keys()):
        item = zone_stats[z]
        item["litres_lost"] = round(item["litres_lost"], 2)
        item["projected_saving_litres"] = round(item["projected_saving_litres"], 2)
        item["litresLost"] = item["litres_lost"]
        item["projectedSavingLitres"] = item["projected_saving_litres"]
        zones_list.append(item)

    return {
        "total_litres_lost": round(total_litres_lost, 2),
        "total_projected_saving_litres": round(total_projected_saving, 2),
        "litres_lost": round(total_litres_lost, 2),
        "projected_saving_litres": round(total_projected_saving, 2),
        "totalLitresLost": round(total_litres_lost, 2),
        "totalProjectedSavingLitres": round(total_projected_saving, 2),
        "assumed_manual_delay_minutes": ASSUMED_MANUAL_DELAY_MINUTES,
        "assumedManualDelayMinutes": ASSUMED_MANUAL_DELAY_MINUTES,
        "is_simulated_estimate": True,
        "label": "Simulated estimate",
        "zones": zones_list,
        "alerts_count": len(simulated_alerts),
    }


@router.post("/reset")
def reset_simulation(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    simulator_id = payload.get("simulatorId") or payload.get("simulator_id")
    now = datetime.now(timezone.utc)
    query = select(Alert).where(
        Alert.source.in_(["SIMULATED", "SIMULATOR"]),
        Alert.status != "RESOLVED",
    )
    if simulator_id:
        query = query.where(Alert.simulator_id == simulator_id)
    simulated_alerts = db.scalars(query).all()
    for alert in simulated_alerts:
        alert.status = "RESOLVED"
        alert.resolved_at = now
        if alert.assigned_to:
            champ = db.get(WaterChampion, alert.assigned_to)
            if champ:
                champ.availability_status = "AVAILABLE"
        if "auto-resolved: readings normal" not in alert.message:
            alert.message = f"{alert.message} — auto-resolved: readings normal"

    db.commit()
    return {
        "status": "ok",
        "message": "Simulation alerts resolved and affected sensors reset to normal.",
        "resolvedAlerts": len(simulated_alerts),
    }


@router.post("/{scenario}")
def simulate(
    scenario: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if scenario not in {"normal", "warning", "leak"}:
        raise HTTPException(status_code=404, detail="Scenario must be normal, warning, or leak.")
    sensor_id = str(payload.get("sensor_id") or payload.get("sensorId") or "")
    if not sensor_id:
        sensor = db.scalar(select(Sensor).order_by(Sensor.id))
        if sensor is None:
            raise HTTPException(status_code=503, detail="No registered sensors are available to simulate.")
        sensor_id = sensor.sensor_code
    presets = {
        "normal": {"flow_rate": 8.6, "pressure": 3.0, "tank_level": 62.0},
        "warning": {"flow_rate": 13.5, "pressure": 2.4, "tank_level": 47.0},
        "leak": {"flow_rate": 18.6, "pressure": 1.8, "tank_level": 23.0},
    }
    reading = {
        **presets[scenario],
        "sensor_id": sensor_id,
        "device_id": "SIMULATION",
        "simulator_id": payload.get("simulatorId") or payload.get("simulator_id"),
    }
    # Allow explicitly supplied numeric values for reproducible demos while still
    # using the exact same validation and processing path as hardware readings.
    for key in ("flow_rate", "pressure", "tank_level", "battery_level", "timestamp"):
        if key in payload:
            reading[key] = payload[key]
    data = SensorDataInput.model_validate(reading)
    return process_sensor_reading(db, data)