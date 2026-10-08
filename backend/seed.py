from app.database import Base, SessionLocal, engine
from app.seed import seed_demo_data
import app.models  # noqa: F401 - register SQLAlchemy model metadata


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    print("HydroGuard seed data is ready.")


if __name__ == "__main__":
    main()