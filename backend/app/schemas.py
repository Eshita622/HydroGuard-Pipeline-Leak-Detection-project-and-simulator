from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


Role = Literal["ADMIN", "WATER_CHAMPION", "administrator", "water-champion"]
PipelineStatus = Literal["NORMAL", "WARNING", "LEAK", "INACTIVE"]
SensorType = Literal["FLOW", "PRESSURE", "TANK_LEVEL", "ACOUSTIC"]
AlertStatus = Literal["ACTIVE", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS", "RESOLVED"]
Severity = Literal["INFO", "WARNING", "CRITICAL"]


class UserRegister(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    fullName: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=8, max_length=24)
    mobile: str | None = Field(default=None, min_length=8, max_length=24)
    password: str = Field(min_length=8, max_length=128)
    role: Role
    assigned_zone: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def require_name_and_phone(self):
        if not (self.name or self.fullName):
            raise ValueError("name is required")
        if not (self.phone or self.mobile):
            raise ValueError("phone is required")
        return self


class UserLogin(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SensorDataInput(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    device_id: str | None = Field(default=None, alias="deviceId", min_length=1, max_length=80)
    simulator_id: str | None = Field(default=None, alias="simulatorId", min_length=1, max_length=64)
    source: str | None = Field(default=None, min_length=1, max_length=32)
    sensor_id: str = Field(alias="sensorId", min_length=1, max_length=32)
    flow_rate: float | None = Field(default=None, ge=0, le=500)
    flowLpm: float | None = Field(default=None, ge=0, le=500)
    pressure: float | None = Field(default=None, ge=0, le=20)
    pressureBar: float | None = Field(default=None, ge=0, le=20)
    tank_level: float | None = Field(default=None, ge=0, le=100)
    tankLevelPercent: float | None = Field(default=None, ge=0, le=100)
    battery_level: float | None = Field(default=None, ge=0, le=100)
    batteryLevel: float | None = Field(default=None, ge=0, le=100)
    timestamp: datetime | None = None

    @model_validator(mode="after")
    def require_measurements(self):
        if self.flow_rate is None and self.flowLpm is None:
            raise ValueError("flow_rate is required")
        if self.pressure is None and self.pressureBar is None:
            raise ValueError("pressure is required")
        if self.tank_level is None and self.tankLevelPercent is None:
            raise ValueError("tank_level is required")
        return self

    @property
    def flow(self) -> float:
        return self.flow_rate if self.flow_rate is not None else self.flowLpm  # type: ignore[return-value]

    @property
    def pressure_value(self) -> float:
        return self.pressure if self.pressure is not None else self.pressureBar  # type: ignore[return-value]

    @property
    def tank(self) -> float:
        return self.tank_level if self.tank_level is not None else self.tankLevelPercent  # type: ignore[return-value]

    @property
    def battery(self) -> float | None:
        return self.battery_level if self.battery_level is not None else self.batteryLevel


class PipelineCreate(BaseModel):
    pipeline_code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=120)
    zone: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=2, max_length=160)
    length_km: float = Field(gt=0, le=10000)
    status: PipelineStatus = "NORMAL"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    end_latitude: float | None = Field(default=None, ge=-90, le=90)
    end_longitude: float | None = Field(default=None, ge=-180, le=180)


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    zone: str | None = Field(default=None, min_length=1, max_length=80)
    location: str | None = Field(default=None, min_length=2, max_length=160)
    length_km: float | None = Field(default=None, gt=0, le=10000)
    status: PipelineStatus | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    end_latitude: float | None = Field(default=None, ge=-90, le=90)
    end_longitude: float | None = Field(default=None, ge=-180, le=180)


class SensorCreate(BaseModel):
    sensor_code: str = Field(min_length=2, max_length=32)
    pipeline_id: int
    sensor_type: SensorType = "FLOW"
    location: str = Field(min_length=2, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    device_id: str | None = Field(default=None, max_length=80)
    battery_level: float = Field(default=100, ge=0, le=100)


class SensorUpdate(BaseModel):
    pipeline_id: int | None = None
    sensor_type: SensorType | None = None
    location: str | None = Field(default=None, min_length=2, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: Literal["ONLINE", "WARNING", "LEAK", "OFFLINE"] | None = None
    battery_level: float | None = Field(default=None, ge=0, le=100)
    device_id: str | None = Field(default=None, max_length=80)


class TankInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=160)
    capacity_liters: float = Field(gt=0, le=1_000_000_000)
    current_level: float = Field(ge=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    status: str = Field(default="NORMAL", max_length=20)

    @model_validator(mode="after")
    def level_within_capacity(self):
        if self.current_level > self.capacity_liters:
            raise ValueError("current_level cannot exceed capacity_liters")
        return self


class AlertAssignment(BaseModel):
    champion_id: int | None = None
    championId: str | int | None = None
    assigned_to: int | None = None

    @property
    def assignee_id(self) -> int | None:
        raw = self.champion_id or self.championId or self.assigned_to
        return int(raw) if raw not in (None, "") else None


class MaintenanceCreate(BaseModel):
    pipeline_id: int | None = None
    alert_id: int | None = None
    assigned_to: int | None = None
    championId: str | int | None = None
    pipeline: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    issue: str | None = Field(default=None, max_length=2000)
    action_taken: str | None = Field(default=None, max_length=2000)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "pending", "in-progress", "completed", "assigned"] = "PENDING"


class MaintenanceUpdate(BaseModel):
    pipeline_id: int | None = None
    alert_id: int | None = None
    assigned_to: int | None = None
    championId: str | int | None = None
    description: str | None = Field(default=None, max_length=2000)
    issue: str | None = Field(default=None, max_length=2000)
    action_taken: str | None = Field(default=None, max_length=2000)
    priority: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "pending", "in-progress", "completed", "assigned"] | None = None


class ChampionCreate(BaseModel):
    user_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=24)
    assigned_zone: str = Field(min_length=1, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    availability_status: str = "AVAILABLE"


class ThresholdUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    flow_warning: float = Field(gt=0, le=500, alias="flowWarningThreshold")
    flow_leak: float = Field(gt=0, le=500, alias="flowLeakThreshold")
    pressure_warning: float = Field(ge=0, le=20, alias="pressureWarningThreshold")
    pressure_leak: float = Field(ge=0, le=20, alias="pressureCriticalThreshold")


class ProfileUpdate(BaseModel):
    fullName: str = Field(min_length=2, max_length=120)
    email: EmailStr
    mobile: str = Field(min_length=8, max_length=24)
    assignedZone: str = Field(default="", max_length=80)