import math
import random
import os
import sys
from datetime import datetime, timedelta, timezone

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import SessionLocal
from app.models import Sensor, SensorReading, Alert, Pipeline

def seed_history_data():
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=30)
        
        sensors = db.scalars(select(Sensor)).all()
        pipelines = db.scalars(select(Pipeline)).all()
        pipeline_map = {p.id: p for p in pipelines}

        if not sensors:
            print("No sensors found to seed history.")
            return

        print(f"Generating 30 days of simulated data for {len(sensors)} sensors...")
        
        readings_to_insert = []
        alerts_to_insert = []

        for index, sensor in enumerate(sensors):
            pipeline = pipeline_map.get(sensor.pipeline_id)
            zone = pipeline.zone if pipeline and pipeline.zone else "Zone 1"
            
            # Generate 1 reading per hour for 30 days
            for day in range(30):
                for hour in range(24):
                    at = start_date + timedelta(days=day, hours=hour)
                    
                    # Normal flow
                    flow = 7.5 + (index % 6) * 0.62 + 0.45 * math.sin(hour / 3)
                    pressure = 3.1 + 0.12 * math.cos(hour / 4) - (index % 3) * 0.04
                    tank_level = 63 + 8 * math.sin(hour / 8 + index / 5)
                    
                    # Random chance for a simulated leak (2% chance per day)
                    is_leak = random.random() < 0.02
                    
                    if is_leak:
                        flow += 8.0  # Spike flow
                        pressure -= 1.0  # Drop pressure
                        
                        # Only create alert once per day max per sensor
                        if hour == 12:
                            alert = Alert(
                                pipeline_id=sensor.pipeline_id,
                                sensor_id=sensor.id,
                                alert_type="LEAK_DETECTED",
                                severity="CRITICAL",
                                message=f"Simulated historical leak at {sensor.location}.",
                                flow_rate=round(flow, 2),
                                pressure=round(pressure, 2),
                                status="RESOLVED",
                                source="SIMULATED",
                                simulator_id="HISTORY_SEED",
                                created_at=at,
                                resolved_at=at + timedelta(hours=random.randint(1, 5)), # Resolved 1-5 hrs later
                            )
                            alerts_to_insert.append(alert)
                    
                    readings_to_insert.append(SensorReading(
                        sensor_id=sensor.id,
                        flow_rate=round(flow, 2),
                        pressure=round(pressure, 2),
                        tank_level=round(max(0, min(100, tank_level)), 1),
                        battery_level=sensor.battery_level,
                        timestamp=at,
                    ))

            # Commit in batches
            if len(readings_to_insert) > 5000:
                db.add_all(readings_to_insert)
                db.commit()
                readings_to_insert = []

        if readings_to_insert:
            db.add_all(readings_to_insert)
            db.commit()
            
        if alerts_to_insert:
            db.add_all(alerts_to_insert)
            db.commit()

        print("History seed complete.")

if __name__ == "__main__":
    seed_history_data()
