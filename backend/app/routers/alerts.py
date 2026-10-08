from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Alert, MaintenanceLog, Pipeline, Sensor, User, WaterChampion
from app.schemas import AlertAssignment
from app.views import alert_view, maintenance_view

router = APIRouter(prefix="/api/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


def _alert(db: Session, alert_id: str) -> Alert | None:
    if not alert_id.isdigit():
        return None
    return db.get(Alert, int(alert_id))


@router.get("")
def list_alerts(
    status: str | None = None,
    severity: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(Alert)
    if status:
        query = query.where(Alert.status == status.upper())
    if severity:
        query = query.where(Alert.severity == severity.upper())
    if type:
        query = query.where(Alert.alert_type == type.upper().replace("-", "_"))
    alerts = db.scalars(query.order_by(Alert.created_at.desc())).all()
    return [alert_view(db, alert) for alert in alerts]


@router.get("/{alert_id}")
def get_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = _alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert_view(db, alert)


@router.post("/{alert_id}/acknowledge")
@router.put("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    alert = _alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status == "RESOLVED":
        raise HTTPException(status_code=409, detail="A resolved alert cannot be acknowledged.")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert_view(db, alert)


@router.post("/{alert_id}/assign")
@router.put("/{alert_id}/assign")
def assign_alert(
    alert_id: str,
    data: AlertAssignment,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    alert = _alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    champion_id = data.assignee_id
    if champion_id is not None:
        champion = db.get(WaterChampion, champion_id)
        if champion is None:
            raise HTTPException(status_code=404, detail="Water Champion not found.")
        champion.availability_status = "ON_SITE"
    alert.assigned_to = champion_id
    if champion_id:
        alert.status = "ASSIGNED"
        if not alert.assigned_at:
            alert.assigned_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert_view(db, alert)


@router.post("/{alert_id}/resolve")
@router.put("/{alert_id}/resolve")
def resolve_alert(alert_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    alert = _alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alert.status = "RESOLVED"
    alert.resolved_at = datetime.now(timezone.utc)
    if alert.assigned_to:
        champion = db.get(WaterChampion, alert.assigned_to)
        if champion:
            open_alerts = db.scalars(select(Alert).where(
                Alert.assigned_to == champion.id,
                Alert.id != alert.id,
                Alert.status.in_(["ACTIVE", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS"])
            )).first()
            if not open_alerts:
                champion.availability_status = "AVAILABLE"
    if alert.pipeline_id and alert.source.upper() not in ("SIMULATED", "SIMULATOR"):
        pipeline = db.get(Pipeline, alert.pipeline_id)
        if pipeline and alert.sensor_id:
            sensor = db.get(Sensor, alert.sensor_id)
            if sensor:
                sensor.status = "ONLINE"
                # Preserve another sensor's active condition on this pipeline.
                states = db.scalars(select(Sensor.status).where(
                    Sensor.pipeline_id == pipeline.id, Sensor.id != sensor.id
                )).all()
                pipeline.status = "LEAK" if "LEAK" in states else "WARNING" if "WARNING" in states else "NORMAL"
    db.commit()
    db.refresh(alert)
    return alert_view(db, alert)


@router.post("/{alert_id}/maintenance", status_code=201)
def start_alert_maintenance(
    alert_id: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    alert = _alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    champion_raw = payload.get("championId") or payload.get("assigned_to")
    champion = None
    if champion_raw not in (None, ""):
        try:
            champion = db.get(WaterChampion, int(champion_raw))
        except (TypeError, ValueError):
            champion = None
        if champion is None:
            raise HTTPException(status_code=404, detail="Water Champion not found.")
    pipeline = db.get(Pipeline, alert.pipeline_id) if alert.pipeline_id else None
    sensor = db.get(Sensor, alert.sensor_id) if alert.sensor_id else None
    record = MaintenanceLog(
        pipeline_id=alert.pipeline_id,
        alert_id=alert.id,
        assigned_to=champion.id if champion else None,
        description=f"{pipeline.name if pipeline else 'Network repair'} — {payload.get('description') or alert.message}",
        status="IN_PROGRESS" if champion else "PENDING",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return maintenance_view(db, record)