from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    """One source of truth for the configurable baseline sensor rules."""

    flow_warning: float = 12.0
    flow_leak: float = 18.0
    pressure_warning: float = 2.5
    pressure_leak: float = 2.0


DEFAULT_THRESHOLDS = Thresholds()


def classify_reading(flow_rate: float, pressure: float, thresholds: Thresholds) -> str:
    if flow_rate >= thresholds.flow_leak or pressure <= thresholds.pressure_leak:
        return "LEAK"
    if flow_rate > thresholds.flow_warning or pressure < thresholds.pressure_warning:
        return "WARNING"
    return "NORMAL"


def classify_risk_level(
    classification: str,
    flow_rate: float,
    pressure: float,
    thresholds: Thresholds,
) -> str | None:
    """Split warning readings into low/medium bands while preserving legacy classes."""
    if classification == "LEAK":
        return "HIGH"
    if classification != "WARNING":
        return None

    flow_span = max(thresholds.flow_leak - thresholds.flow_warning, 1e-9)
    pressure_span = max(thresholds.pressure_warning - thresholds.pressure_leak, 1e-9)
    flow_score = max(0.0, (flow_rate - thresholds.flow_warning) / flow_span)
    pressure_score = max(0.0, (thresholds.pressure_warning - pressure) / pressure_span)
    return "MEDIUM" if max(flow_score, pressure_score) >= 0.5 else "LOW"


def generate_simulation_profile(thresholds: Thresholds) -> dict:
    """Return one representative reading for each classification band computed from thresholds."""
    fw = thresholds.flow_warning
    fl = thresholds.flow_leak
    pw = thresholds.pressure_warning
    pl = thresholds.pressure_leak

    flow_span = max(fl - fw, 1.0)
    pressure_span = max(pw - pl, 0.1)

    return {
        "normal": {
            "flow": round(max(0.0, fw - flow_span * 0.5), 1),
            "pressure": round(pw + pressure_span * 0.8, 2),
        },
        "low": {
            "flow": round(fw + flow_span * 0.25, 1),
            "pressure": round(pw - pressure_span * 0.25, 2),
        },
        "medium": {
            "flow": round(fw + flow_span * 0.75, 1),
            "pressure": round(pw - pressure_span * 0.75, 2),
        },
        "high": {
            "flow": round(fl + flow_span * 0.35, 1),
            "pressure": round(max(0.0, pl - pressure_span * 0.4), 2),
        },
    }