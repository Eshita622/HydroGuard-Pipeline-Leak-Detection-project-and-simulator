from datetime import datetime, timedelta, timezone
import re

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from app.database import get_db
from app.models import User

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def normalize_phone(value: str) -> str:
    value = value.strip()
    return ("+" if value.startswith("+") else "") + re.sub(r"\D", "", value)


def public_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "fullName": user.name,
        "email": user.email,
        "phone": user.phone,
        "mobile": user.phone,
        "role": "administrator" if user.role == "ADMIN" else "water-champion",
        "assignedZone": user.champion.assigned_zone if user.champion else "",
        "created_at": user.created_at.isoformat(),
    }


def issue_access_token(user: User) -> str:
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET must be set before signing in.",
        )
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid bearer access token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not JWT_SECRET:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def find_login_user(db: Session, identifier: str) -> User | None:
    normalized = identifier.strip().lower()
    if "@" in normalized:
        return db.scalar(select(User).where(User.email == normalized))
    return db.scalar(select(User).where(User.phone == normalize_phone(identifier)))