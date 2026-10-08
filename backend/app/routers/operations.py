from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Alert, MaintenanceLog, Pipeline, Sensor, SystemSetting, Tank, User, WaterChampion
from app.schemas import (
    ChampionCreate,
    MaintenanceCreate,
    MaintenanceUpdate,
    ProfileUpdate,
    TankInput,
    ThresholdUpdate,
)
from app.services.sms_service import list_sms
from app.views import champion_view, maintenance_view, sensor_view, tank_view

router = APIRouter(prefix="/api", tags=["operations"], dependencies=[Depends(get_current_user)])


def _id(value: str) -> int:
    if not value.isdigit():
        raise HTTPException(status_code=404, detail="Record not found.")
    return int(value)


@router.get("/tanks")
def list_tanks(db: Session = Depends(get_db)):
    return [tank_view(t) for t in db.scalars(select(Tank).order_by(Tank.id)).all()]


@router.get("/tanks/{tank_id}")
def get_tank(tank_id: str, db: Session = Depends(get_db)):
    tank = db.get(Tank, _id(tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found.")
    return tank_view(tank)


@router.post("/tanks", status_code=201)
def create_tank(data: TankInput, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    tank = Tank(**data.model_dump(), status=data.status.upper())
    db.add(tank)
    db.commit()
    db.refresh(tank)
    return tank_view(tank)


@router.put("/tanks/{tank_id}")
def update_tank(tank_id: str, data: TankInput, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    tank = db.get(Tank, _id(tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Tank not found.")
    for key, value in data.model_dump().items():
        setattr(tank, key, value.upper() if key == "status" else value)
    db.commit()
    db.refresh(tank)
    return tank_view(tank)


@router.get("/water-champions")
def list_champions(db: Session = Depends(get_db)):
    return [champion_view(db, c) for c in db.scalars(select(WaterChampion).order_by(WaterChampion.id)).all()]


@router.get("/sms-log")
def get_sms_log():
    return list_sms()


@router.get("/water-champions/{champion_id}")
def get_champion(champion_id: str, db: Session = Depends(get_db)):
    champion = db.get(WaterChampion, _id(champion_id))
    if champion is None:
        raise HTTPException(status_code=404, detail="Water Champion not found.")
    return champion_view(db, champion)


@router.post("/water-champions", status_code=201)
def create_champion(data: ChampionCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if data.user_id and db.get(User, data.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    champion = WaterChampion(**data.model_dump(), availability_status=data.availability_status.upper())
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion_view(db, champion)


@router.put("/water-champions/{champion_id}")
def update_champion(champion_id: str, data: ChampionCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    champion = db.get(WaterChampion, _id(champion_id))
    if champion is None:
        raise HTTPException(status_code=404, detail="Water Champion not found.")
    for key, value in data.model_dump().items():
        setattr(champion, key, value.upper() if key == "availability_status" else value)
    db.commit()
    db.refresh(champion)
    return champion_view(db, champion)


def find_pipeline(db: Session, pipeline_id: int | None, pipeline_name: str | None) -> Pipeline | None:
    if pipeline_id:
        return db.get(Pipeline, pipeline_id)
    if pipeline_name:
        return db.scalar(select(Pipeline).where(
            (Pipeline.name == pipeline_name) | (Pipeline.pipeline_code == pipeline_name)
        ))
    return None


def champion_from_payload(db: Session, assigned_to: int | None, champion_id: str | int | None) -> int | None:
    raw = assigned_to if assigned_to is not None else champion_id
    if raw in (None, ""):
        return None
    try:
        result = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="championId must be a valid Water Champion ID.")
    if db.get(WaterChampion, result) is None:
        raise HTTPException(status_code=404, detail="Water Champion not found.")
    return result


@router.get("/maintenance")
def list_maintenance(db: Session = Depends(get_db)):
    records = db.scalars(select(MaintenanceLog).order_by(MaintenanceLog.created_at.desc())).all()
    return [maintenance_view(db, item) for item in records]


@router.post("/maintenance", status_code=201)
def create_maintenance(data: MaintenanceCreate, db: Session = Depends(get_db)):
    pipeline = find_pipeline(db, data.pipeline_id, data.pipeline)
    if data.pipeline_id and pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    alert = db.get(Alert, data.alert_id) if data.alert_id else None
    if data.alert_id and alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    champion_id = champion_from_payload(db, data.assigned_to, data.championId)
    description = data.description or data.issue or "Maintenance task"
    if not data.description and data.pipeline:
        description = f"{data.pipeline} — {description}"
    status = data.status.upper().replace("-", "_")
    if status == "ASSIGNED":
        status = "IN_PROGRESS"
    record = MaintenanceLog(
        pipeline_id=pipeline.id if pipeline else (alert.pipeline_id if alert else None),
        alert_id=alert.id if alert else None,
        assigned_to=champion_id,
        description=description,
        action_taken=data.action_taken,
        status=status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return maintenance_view(db, record)


@router.patch("/maintenance/{record_id}")
@router.put("/maintenance/{record_id}")
def update_maintenance(
    record_id: str,
    data: MaintenanceUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    record = db.get(MaintenanceLog, _id(record_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    values = data.model_dump(exclude_unset=True)
    champion_raw = values.pop("championId", None)
    assigned = values.pop("assigned_to", None)
    if champion_raw is not None or assigned is not None:
        record.assigned_to = champion_from_payload(db, assigned, champion_raw)
    pipeline_name = values.pop("pipeline", None)
    pipeline_id = values.pop("pipeline_id", None)
    if pipeline_name or pipeline_id:
        pipeline = find_pipeline(db, pipeline_id, pipeline_name)
        if pipeline is None:
            raise HTTPException(status_code=404, detail="Pipeline not found.")
        record.pipeline_id = pipeline.id
    alert_id = values.pop("alert_id", None)
    if alert_id is not None:
        if alert_id and db.get(Alert, alert_id) is None:
            raise HTTPException(status_code=404, detail="Alert not found.")
        record.alert_id = alert_id
    description = values.pop("issue", None) or values.pop("description", None)
    if description is not None:
        record.description = description
    for key, value in values.items():
        if key == "status" and value:
            value = value.upper().replace("-", "_")
            if value == "ASSIGNED":
                value = "IN_PROGRESS"
            if value == "COMPLETED":
                record.completed_at = datetime.now(timezone.utc)
                if record.alert_id:
                    linked_alert = db.get(Alert, record.alert_id)
                    if linked_alert and linked_alert.status != "RESOLVED":
                        linked_alert.status = "RESOLVED"
                        linked_alert.resolved_at = datetime.now(timezone.utc)
                        if linked_alert.assigned_to:
                            champ = db.get(WaterChampion, linked_alert.assigned_to)
                            if champ:
                                champ.availability_status = "AVAILABLE"
                if record.assigned_to:
                    champ = db.get(WaterChampion, record.assigned_to)
                    if champ:
                        champ.availability_status = "AVAILABLE"
            else:
                record.completed_at = None
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return maintenance_view(db, record)


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id), "fullName": user.name, "email": user.email,
        "mobile": user.phone, "role": "administrator" if user.role == "ADMIN" else "water-champion",
        "assignedZone": user.champion.assigned_zone if user.champion else "",
    }


@router.patch("/profile")
@router.put("/profile")
def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.name = data.fullName.strip()
    user.email = str(data.email).lower()
    user.phone = data.mobile.strip()
    if user.champion:
        user.champion.name = user.name
        user.champion.phone = user.phone
        user.champion.assigned_zone = data.assignedZone
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="That email or phone number is already in use.")
    return get_profile(user)


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    settings = db.get(SystemSetting, "thresholds")
    if settings is None:
        settings = SystemSetting(key="thresholds")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    sensors = db.scalars(select(Sensor).order_by(Sensor.id)).all()
    devices = []
    for sensor in sensors:
        current = sensor_view(db, sensor)
        devices.append({
            "id": str(sensor.id),
            "name": sensor.device_id or sensor.sensor_code,
            "location": sensor.location,
            "status": current["status"],
            "lastSeen": current["lastUpdated"],
            "source": current["source"],
            "simulated": current["simulated"],
        })
    return {
        "flow_warning": settings.flow_warning,
        "flow_leak": settings.flow_leak,
        "pressure_warning": settings.pressure_warning,
        "pressure_leak": settings.pressure_leak,
        "flowWarningThreshold": settings.flow_warning,
        "flowLeakThreshold": settings.flow_leak,
        "pressureWarningThreshold": settings.pressure_warning,
        "pressureCriticalThreshold": settings.pressure_leak,
        "devices": devices,
    }


@router.patch("/settings")
@router.put("/settings")
def update_settings(data: ThresholdUpdate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if data.flow_leak <= data.flow_warning:
        raise HTTPException(status_code=422, detail="Leak flow threshold must be higher than warning flow.")
    if data.pressure_leak >= data.pressure_warning:
        raise HTTPException(status_code=422, detail="Critical pressure threshold must be below warning pressure.")
    settings = db.get(SystemSetting, "thresholds")
    if settings is None:
        settings = SystemSetting(key="thresholds")
        db.add(settings)
    for key, value in data.model_dump().items():
        setattr(settings, key, value)
    db.commit()
    return get_settings(db)