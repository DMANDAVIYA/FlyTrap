"""Login cookies (spec 10.3), passwords and API bearer tokens."""

import hashlib
import hmac
import re
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import Response
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bait
from app.bait import ALPHABET
from app.config import Settings
from app.models import ApiToken, User
from app.seed import DEMO_EMAIL, adopt_user
from app.words import is_clean

AUTH_COOKIE, AUTH_SALT = "hl_auth", "hl-auth"
ADMIN_COOKIE, ADMIN_SALT = "hl_admin", "hl-admin"
COOKIE_MAX_AGE = 7 * 24 * 3600
MIGRATION_USER = "ops-migrate"
TOKEN_RE = re.compile(r"hl_live_[0-9A-Za-z]{24}")
PBKDF2_ROUNDS = 200_000


# --- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    scheme, _, rest = stored.partition("$")
    if scheme != "pbkdf2_sha256":
        return False  # unusable password ("!...")
    rounds, salt, expected = rest.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    return hmac.compare_digest(digest.hex(), expected)


def password_ok(settings: Settings, user: User, password: str) -> bool:
    # The demo customer's password is derived from BAIT_SECRET (spec 10.3), which
    # is not known when the pod template is built, so it is checked directly.
    if user.email == DEMO_EMAIL:
        return hmac.compare_digest(password, bait.demo_password(settings.bait_secret))
    return verify_password(password, user.password_hash)


# --- signed cookies ------------------------------------------------------------


def sign(secret: str, salt: str, claims: dict) -> str:
    return URLSafeTimedSerializer(secret, salt=salt).dumps(claims)


def read_claims(secret: str, token: str | None, salt: str) -> dict | None:
    if not token:
        return None
    try:
        claims = URLSafeTimedSerializer(secret, salt=salt).loads(token, max_age=COOKIE_MAX_AGE)
    except BadData:
        return None
    return claims if isinstance(claims, dict) else None


def auth_claims(user: User) -> dict:
    return {"uid": user.id, "email": user.email, "name": user.name, "ver": user.session_version}


def set_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(name, value, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")


def log_in(response: Response, settings: Settings, user: User) -> None:
    set_cookie(response, AUTH_COOKIE, sign(settings.session_secret, AUTH_SALT, auth_claims(user)))


def log_in_admin(response: Response, settings: Settings, identity: str) -> None:
    set_cookie(response, ADMIN_COOKIE, sign(settings.session_secret, ADMIN_SALT, {"user": identity}))


def new_api_token() -> str:
    while not is_clean(token := "hl_live_" + "".join(secrets.choice(ALPHABET) for _ in range(24))):
        pass
    return token


# --- customers -----------------------------------------------------------------


def current_user(request: Request, db: Session) -> User | None:
    settings: Settings = request.app.state.settings
    claims = read_claims(settings.session_secret, request.cookies.get(AUTH_COOKIE), AUTH_SALT)
    if not claims or not isinstance(claims.get("uid"), int):
        return None
    if settings.is_pod:
        return adopt_user(db, claims)
    user = db.get(User, claims["uid"])
    if user and user.email == claims.get("email") and user.session_version == claims.get("ver"):
        return user
    return None


def api_user(request: Request, db: Session) -> User | None:
    """Bearer token first, then the login cookie. A bad bearer token is a 401."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return current_user(request, db)
    token = header[7:].strip()
    row = db.scalar(select(ApiToken).where(ApiToken.token == token, ApiToken.revoked_at.is_(None)))
    if row:
        return db.get(User, row.user_id)
    if request.app.state.settings.is_pod and TOKEN_RE.fullmatch(token):
        # Planted and derived tokens are never in the template; any well-formed
        # key works here so a visitor holding one is never turned away.
        return db.scalar(select(User).where(User.role == "admin").order_by(User.id))
    raise HTTPException(status_code=401, detail="invalid API token")


# --- admin panel -------------------------------------------------------------


def admin_login(settings: Settings, db: Session, username: str, password: str) -> str | None:
    """Return the admin identity for valid credentials, else None."""
    if settings.is_pod and username == MIGRATION_USER:
        return MIGRATION_USER if password.startswith("hlm-") else None
    user = db.scalar(select(User).where(User.email == username, User.role == "admin"))
    return user.email if user and password_ok(settings, user, password) else None


def current_admin(request: Request, db: Session) -> str | None:
    settings: Settings = request.app.state.settings
    claims = read_claims(settings.session_secret, request.cookies.get(ADMIN_COOKIE), ADMIN_SALT)
    name = claims.get("user") if claims else None
    if not isinstance(name, str):
        return None
    if settings.is_pod and name == MIGRATION_USER:
        return name
    user = db.scalar(select(User).where(User.email == name, User.role == "admin"))
    return user.email if user else None
