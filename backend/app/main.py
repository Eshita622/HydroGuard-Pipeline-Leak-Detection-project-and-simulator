from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 - register SQLAlchemy model metadata
from app.config import CORS_ORIGINS
from app.database import Base, SessionLocal, ensure_simulator_columns, engine
from app.routers import alerts, analytics, auth, monitoring, operations, simulation
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_simulator_columns()
    with SessionLocal() as db:
        seed_demo_data(db)
    yield


app = FastAPI(
    title="HydroGuard Backend",
    description="JWT-protected water network monitoring APIs with rule-based leak detection.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(monitoring.public_router)
app.include_router(auth.router)
app.include_router(monitoring.router)
app.include_router(alerts.router)
app.include_router(operations.router)
app.include_router(analytics.router)
app.include_router(simulation.router)