import datetime
import os

import bcrypt
import jwt
from fastapi import Cookie, HTTPException

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_TTL_HOURS = 24


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def create_session_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_session_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


def get_current_username(aiprs_session: str | None = Cookie(default=None)) -> str:
    if aiprs_session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_session_token(aiprs_session)


def get_current_username_optional(aiprs_session: str | None = Cookie(default=None)) -> str:
    """Like get_current_username, but returns "Guest" instead of raising when
    there's no session — for pages that work for logged-out visitors too."""
    if aiprs_session is None:
        return "Guest"
    try:
        return decode_session_token(aiprs_session)
    except HTTPException:
        return "Guest"
