from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Alert, MaintenanceLog, Pipeline, Sensor, SensorReading, Tank, WaterChampion

router = APIRouter(prefix="/api", tags=["analytics and reports"], dependencies=[Depends(get_current_user)])


def bounds(range_name: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    hours = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}.get(range_name)
    if hours is None:
        raise HTTPException(status_code=422, detail="range must be 24h, 7d, or 30d.")
    return now - timedelta(hours=hours), now


def readings_in_window(db: Session, start: datetime, end: datetime) -> list[SensorReading]:
    return db.scalars(select(SensorReading).where(
        SensorReading.timestamp >= start,
        SensorReading.timestamp <= end,
        SensorReading.source == "FIELD",
    ).order_by(SensorReading.timestamp)).all()


def analytics_bundle(db: Session, range_name: str) -> dict:
    start, end = bounds(range_name)
    rows = db.scalars(select(SensorReading).where(
        SensorReading.timestamp >= start,
        SensorReading.timestamp <= end,
    ).order_by(SensorReading.timestamp)).all()
    
    alerts = db.scalars(select(Alert).where(
        Alert.created_at >= start,
        Alert.created_at <= end,
    )).all()
    
    tanks = db.scalars(select(Tank)).all()
    sensors = db.scalars(select(Sensor)).all()
    champions = db.scalars(select(WaterChampion)).all()
    pipelines = db.scalars(select(Pipeline)).all()
    
    sensor_map = {s.id: s for s in sensors}
    pipeline_map = {p.id: p for p in pipelines}
    champion_map = {c.id: c.name for c in champions}
    
    # 1. KPIs
    leak_events = len(alerts)
    response_times = []
    for alert in alerts:
        end_time = alert.acknowledged_at or alert.resolved_at
        if alert.assigned_at and end_time:
            # assigned_at is a datetime object, but we need to ensure it's UTC aware
            assign_time = alert.assigned_at
            if assign_time.tzinfo is None:
                assign_time = assign_time.replace(tzinfo=timezone.utc)
            e_time = end_time
            if e_time.tzinfo is None:
                e_time = e_time.replace(tzinfo=timezone.utc)
            minutes = (e_time - assign_time).total_seconds() / 60.0
            if minutes >= 0:
                response_times.append(minutes)
    
    mean_response = round(sum(response_times) / len(response_times), 1) if response_times else "-"
    distinct_sensors = len(set(r.sensor_id for r in rows))
    
    kpis = {
        "leakEvents": leak_events,
        "meanResponseMinutes": mean_response,
        "sensorsReporting": distinct_sensors,
        "totalSensors": len(sensors)
    }
    
    # Bucket formatting
    def bucket_key(dt):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:00" if range_name == "24h" else "%Y-%m-%d")

    # 2. Charts: flowPressure
    # Group by bucket AND zone
    # For Zone we use Pipeline.zone
    fp_grouped = defaultdict(list)
    for row in rows:
        b = bucket_key(row.timestamp)
        sensor = sensor_map.get(row.sensor_id)
        pipeline = pipeline_map.get(sensor.pipeline_id) if sensor else None
        zone = pipeline.zone if pipeline and pipeline.zone else "Zone 1"
        fp_grouped[(b, zone)].append(row)
        
    flow_pressure = []
    for (b, z), bucket in sorted(fp_grouped.items()):
        flow_pressure.append({
            "time": b,
            "zone": z,
            "flowLpm": round(sum(r.flow_rate or 0 for r in bucket) / len(bucket), 2),
            "pressureBar": round(sum(r.pressure or 0 for r in bucket) / len(bucket), 2),
        })

    # tankLevel
    tank_grouped = defaultdict(list)
    for row in rows:
        if row.tank_level is not None:
            b = bucket_key(row.timestamp)
            tank_grouped[b].append(row.tank_level)
            
    # Assuming tank level varies, returning average per bucket. If not, returning current.
    # The requirement: "keep if readings vary, otherwise show current level per tank as bars."
    # Since our SensorReadings don't tie to a specific tank, we'll return average of all tanks per bucket.
    tank_level = []
    for b, bucket in sorted(tank_grouped.items()):
        tank_level.append({
            "time": b,
            "tankName": "Main Tank", # Simplified since we don't have tank ID on readings
            "tankLevelPercent": round(sum(bucket) / len(bucket), 1)
        })

    # alertsByRisk
    risk_grouped = defaultdict(int)
    for alert in alerts:
        b = bucket_key(alert.created_at)
        risk = alert.risk_level
        r = risk.lower() if risk else "low"
        s = "simulated" if alert.source.upper() in ("SIMULATED", "SIMULATOR") else "field"
        risk_grouped[(b, r, s)] += 1
        
    alerts_by_risk = []
    for (b, r, s), count in sorted(risk_grouped.items()):
        alerts_by_risk.append({
            "time": b,
            "riskLevel": r,
            "source": s,
            "count": count
        })

    # fieldResponse
    resp_grouped = defaultdict(list)
    for alert in alerts:
        end_time = alert.acknowledged_at or alert.resolved_at
        if alert.assigned_to and alert.assigned_at and end_time:
            c_name = champion_map.get(alert.assigned_to, "Unknown")
            assign_time = alert.assigned_at
            if assign_time.tzinfo is None:
                assign_time = assign_time.replace(tzinfo=timezone.utc)
            e_time = end_time
            if e_time.tzinfo is None:
                e_time = e_time.replace(tzinfo=timezone.utc)
            minutes = (e_time - assign_time).total_seconds() / 60.0
            if minutes >= 0:
                resp_grouped[c_name].append(minutes)
                
    field_response = []
    for c_name, times in resp_grouped.items():
        field_response.append({
            "championName": c_name,
            "averageResponseMinutes": round(sum(times) / len(times), 1)
        })

    # alertsByZone
    zone_alerts = defaultdict(int)
    for alert in alerts:
        sensor = sensor_map.get(alert.sensor_id)
        pipeline = pipeline_map.get(sensor.pipeline_id) if sensor else None
        zone = pipeline.zone if pipeline and pipeline.zone else "Zone 1"
        zone_alerts[zone] += 1
        
    alerts_by_zone = [{"zone": z, "count": c} for z, c in sorted(zone_alerts.items())]

    # simulatedWaterLostPerZone
    sim_loss = defaultdict(float)
    from app.services.sensor_processing import load_thresholds
    from app.services.leak_detection import generate_simulation_profile
    thresholds = load_thresholds(db)
    profile = generate_simulation_profile(thresholds)
    normal_flow = profile["normal"]["flow"]
    now = datetime.now(timezone.utc)

    for alert in alerts:
        if alert.source.upper() in ("SIMULATED", "SIMULATOR"):
            alert_flow = alert.flow_rate if alert.flow_rate is not None else normal_flow
            delta_flow = max(0.0, float(alert_flow) - float(normal_flow))
            created_at = alert.created_at.replace(tzinfo=timezone.utc) if alert.created_at.tzinfo is None else alert.created_at
            end_time = (
                (alert.resolved_at.replace(tzinfo=timezone.utc) if alert.resolved_at.tzinfo is None else alert.resolved_at)
                if (alert.status == "RESOLVED" and alert.resolved_at)
                else now
            )
            # Bound end_time to the analytics range end if needed, but since alerts are in range, we just calculate it
            if end_time > end:
                end_time = end
            duration_minutes = max(0.0, (end_time - created_at).total_seconds() / 60.0)
            litres_lost = delta_flow * duration_minutes
            sensor = sensor_map.get(alert.sensor_id)
            pipeline = pipeline_map.get(sensor.pipeline_id) if sensor else None
            zone = pipeline.zone if pipeline and pipeline.zone else "Zone 1"
            sim_loss[zone] += litres_lost
            
    simulated_loss = []
    for z, loss in sorted(sim_loss.items()):
        simulated_loss.append({
            "zone": z,
            "litresLost": round(loss, 2),
            "label": "Simulated estimate"
        })

    return {
        "range": range_name,
        "kpis": kpis,
        "flowPressure": flow_pressure,
        "tankLevel": tank_level,
        "alertsByRisk": alerts_by_risk,
        "fieldResponse": field_response,
        "alertsByZone": alerts_by_zone,
        "simulatedWaterLostPerZone": simulated_loss,
    }


@router.get("/analytics")
def get_analytics(range: str = Query(default="7d"), db: Session = Depends(get_db)):
    return analytics_bundle(db, range)


@router.get("/analytics/{kind}")
def get_analytics_kind(kind: str, range: str = Query(default="7d"), db: Session = Depends(get_db)):
    bundle = analytics_bundle(db, range)
    if kind == "flow":
        return bundle["flowPressure"]
    if kind == "alerts":
        return bundle["alertsByRisk"]
    raise HTTPException(status_code=404, detail="Unknown analytics series.")


@router.get("/reports")
def get_report(
    type: str = Query(min_length=2),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
):
    if not from_date or not to_date:
        raise HTTPException(status_code=422, detail="Both from and to dates are required.")
    try:
        start = datetime.combine(date.fromisoformat(from_date), datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(date.fromisoformat(to_date), datetime.max.time(), tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Dates must use YYYY-MM-DD.")
    if start > end:
        raise HTTPException(status_code=422, detail="The start date must be before the end date.")
    rows = readings_in_window(db, start, end)
    alerts = db.scalars(select(Alert).where(
        Alert.created_at >= start,
        Alert.created_at <= end,
        Alert.source == "FIELD",
    )).all()
    pipelines = db.scalars(select(Pipeline)).all()
    sensors = db.scalars(select(Sensor)).all()
    maintenance = db.scalars(select(MaintenanceLog)).all()
    if type == "water-usage":
        title, columns, records = "Water usage", ["Recorded at", "Sensor", "Flow (L/min)", "Pressure (bar)"], [
            [r.timestamp.isoformat(), db.get(Sensor, r.sensor_id).sensor_code, f"{r.flow_rate or 0:.1f}", f"{r.pressure or 0:.1f}"] for r in rows
        ]
    elif type == "water-loss":
        title, columns, records = "Estimated water loss", ["Recorded at", "Estimated loss (liters)", "Leak condition"], [
            [r.timestamp.isoformat(), f"{max(0, (r.flow_rate or 0) - 12) * 60:.1f}", str((r.flow_rate or 0) >= 18 or (r.pressure or 99) < 2)] for r in rows
        ]
    elif type == "leak-events":
        title, columns, records = "Leak events", ["Alert ID", "Pipeline", "Sensor", "Flow", "Pressure", "Status", "Detected at"], [
            [str(a.id), db.get(Pipeline, a.pipeline_id).name if a.pipeline_id and db.get(Pipeline, a.pipeline_id) else "", db.get(Sensor, a.sensor_id).sensor_code if a.sensor_id and db.get(Sensor, a.sensor_id) else "", str(a.flow_rate or 0), str(a.pressure or 0), a.status, a.created_at.isoformat()] for a in alerts
        ]
    elif type == "pipeline-health":
        title, columns, records = "Pipeline health", ["Pipeline", "Location", "Status", "Length (km)"], [
            [p.name, p.location, p.status, str(p.length_km)] for p in pipelines
        ]
    elif type == "sensor-health":
        title, columns, records = "Sensor health", ["Sensor", "Location", "Status", "Battery", "Last seen"], [
            [s.sensor_code, s.location, s.status, f"{s.battery_level:.0f}%", s.last_seen.isoformat() if s.last_seen else ""] for s in sensors
        ]
    elif type == "maintenance":
        title, columns, records = "Maintenance performance", ["Maintenance ID", "Pipeline", "Description", "Status", "Created"], [
            [f"MNT-{m.id:04d}", db.get(Pipeline, m.pipeline_id).name if m.pipeline_id and db.get(Pipeline, m.pipeline_id) else "", m.description, m.status, m.created_at.isoformat()] for m in maintenance
        ]
    else:
        raise HTTPException(status_code=422, detail="Unknown report type.")
    return {
        "title": title, "from": from_date, "to": to_date,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "columns": columns, "rows": records,
    }