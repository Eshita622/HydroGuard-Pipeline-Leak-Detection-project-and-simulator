from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    find_login_user,
    get_current_user,
    hash_password,
    issue_access_token,
    normalize_phone,
    public_user,
    verify_password,
)
from app.database import get_db
from app.models import User, WaterChampion
from app.schemas import UserLogin, UserRegister

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    name = (data.name or data.fullName or "").strip()
    phone = normalize_phone(data.phone or data.mobile or "")
    role = "ADMIN" if data.role in ("ADMIN", "administrator") else "WATER_CHAMPION"
    user = User(
        name=name,
        email=str(data.email).strip().lower(),
        phone=phone,
        password_hash=hash_password(data.password),
        role=role,
    )
    db.add(user)
    try:
        db.flush()
        if role == "WATER_CHAMPION":
            assigned = (data.assigned_zone or "Unassigned").strip()
            db.add(WaterChampion(user_id=user.id, name=user.name, phone=user.phone, assigned_zone=assigned))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That email or phone number is already registered.")
    db.refresh(user)
    profile = public_user(user)
    return {
        "user": profile,
        "access_token": issue_access_token(user),
        "token_type": "bearer",
        "expires_in": 60 * 60 * 12,
    }


@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = find_login_user(db, data.identifier)
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email, phone, or password.")
    if user.role == "WATER_CHAMPION" and user.champion is None:
        db.add(WaterChampion(user_id=user.id, name=user.name, phone=user.phone, assigned_zone="Unassigned"))
        db.commit()
        db.refresh(user)
    return {
        "user": public_user(user),
        "access_token": issue_access_token(user),
        "token_type": "bearer",
        "expires_in": 60 * 60 * 12,
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return public_user(user)


@router.get("/session")
def session(user: User = Depends(get_current_user)):
    return {"user": public_user(user)}


@router.delete("/session", status_code=204)
def logout(_user: User = Depends(get_current_user)):
    return None