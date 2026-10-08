"""Command-line script to drop and cleanly reseed the HydroGuard demo database."""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401 - register SQLAlchemy model metadata
from app.database import Base, SessionLocal, engine, ensure_simulator_columns
from app.seed import seed_demo_data


def reset_demo(wipe_users: bool = False) -> None:
    print("Dropping existing HydroGuard database tables...")
    if wipe_users:
        Base.metadata.drop_all(bind=engine)
    else:
        tables_to_drop = [t for name, t in Base.metadata.tables.items() if name != "users"]
        Base.metadata.drop_all(bind=engine, tables=tables_to_drop)
    print("Recreating database schema...")
    Base.metadata.create_all(bind=engine)
    ensure_simulator_columns()
    print("Seeding fresh Pune demo network...")
    with SessionLocal() as db:
        seed_demo_data(db)
    print("HydroGuard demo database dropped and cleanly reseeded successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset HydroGuard demo database.")
    parser.add_argument("--wipe-users", action="store_true", help="Also wipe the users table (default is to keep users).")
    args = parser.parse_args()
    reset_demo(wipe_users=args.wipe_users)
