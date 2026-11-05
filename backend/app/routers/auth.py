import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PasswordResetToken, User
from app.schemas import (
    ForgotPassword,
    ResetPasswordRequest,
    ThemeUpdate,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.auth.utils import verify_password, get_password_hash, create_access_token
from app.auth.deps import get_current_user
from app.services.email import (
    EmailDeliveryError,
    EmailNotConfigured,
    ensure_email_configured,
    send_password_reset_email,
)
from app.services.password_reset import (
    build_reset_link,
    generate_reset_token,
    hash_reset_token,
    token_ttl_minutes,
)
from app.services.rate_limit import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_FORGOT_MESSAGE = (
    "Si el correo está registrado, vas a recibir un enlace para restablecer tu contraseña."
)
INVALID_RESET_TOKEN_MESSAGE = "El enlace de recuperación es inválido o venció."


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if email exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    # Check if username exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        birth_date=user.birth_date,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos"
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": db_user.email, "ver": db_user.token_version or 0},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer", "theme_accent": db_user.theme_accent}


@router.post("/forgot-password")
def forgot_password(request: ForgotPassword, http_request: Request, db: Session = Depends(get_db)):
    """Request a recovery link.

    The response is always the same generic message for registered and
    unregistered emails. Rate limits are applied per IP and per email.
    """
    ip = _client_ip(http_request)
    enforce_rate_limit(
        f"forgot:ip:{ip}",
        limit_env="PASSWORD_RESET_RATE_LIMIT_FORGOT_IP",
        default_limit=5,
        window_env="PASSWORD_RESET_RATE_LIMIT_FORGOT_IP_WINDOW",
        default_window_seconds=900,
    )
    normalized_email = str(request.email).strip().lower()
    enforce_rate_limit(
        f"forgot:email:{normalized_email}",
        limit_env="PASSWORD_RESET_RATE_LIMIT_FORGOT_EMAIL",
        default_limit=3,
        window_env="PASSWORD_RESET_RATE_LIMIT_FORGOT_EMAIL_WINDOW",
        default_window_seconds=900,
    )

    # Fail loudly when no real email can be sent instead of pretending success.
    try:
        ensure_email_configured()
    except EmailNotConfigured:
        logger.error("SMTP is not configured; password recovery emails cannot be sent")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de recuperación por correo no está disponible en este momento.",
        )

    db_user = db.query(User).filter(User.email == request.email).first()
    if not db_user:
        # Same response as the registered case, so existence is not revealed.
        return {"message": GENERIC_FORGOT_MESSAGE}

    now = datetime.utcnow()
    # Only the newest link stays valid: previous unused tokens are burned.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == db_user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now})

    ttl_minutes = token_ttl_minutes()
    raw_token = generate_reset_token()
    reset_token = PasswordResetToken(
        user_id=db_user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=now + timedelta(minutes=ttl_minutes),
        created_at=now,
    )
    db.add(reset_token)
    db.commit()

    try:
        send_password_reset_email(
            to_email=db_user.email,
            reset_link=build_reset_link(raw_token),
            expires_minutes=ttl_minutes,
        )
    except EmailDeliveryError:
        # The delivery failed, so the token must not stay usable. The response
        # stays generic to avoid revealing whether the account exists.
        reset_token.used_at = datetime.utcnow()
        db.commit()
        logger.error(
            "Password recovery email delivery failed for user id=%s", db_user.id
        )

    return {"message": GENERIC_FORGOT_MESSAGE}


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """Consume a single-use token and replace the account password."""
    enforce_rate_limit(
        f"reset:ip:{_client_ip(http_request)}",
        limit_env="PASSWORD_RESET_RATE_LIMIT_RESET_IP",
        default_limit=10,
        window_env="PASSWORD_RESET_RATE_LIMIT_RESET_IP_WINDOW",
        default_window_seconds=900,
    )

    now = datetime.utcnow()
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_reset_token(request.token))
        .first()
    )
    if (
        not reset_token
        or reset_token.used_at is not None
        or reset_token.expires_at is None
        or reset_token.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_MESSAGE,
        )

    db_user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_MESSAGE,
        )

    db_user.hashed_password = get_password_hash(request.new_password)
    # Bumping the version invalidates every access token minted before this
    # reset, including the one the user may still have open in another tab.
    db_user.token_version = (db_user.token_version or 0) + 1

    # Burn this token and any other pending recovery links for the account.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == db_user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now})

    db.commit()
    return {"message": "Contraseña actualizada correctamente. Iniciá sesión con tu nueva contraseña."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/theme")
def update_theme(theme: ThemeUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.theme_accent = theme.theme_accent
    db.commit()
    db.refresh(current_user)
    return {"theme_accent": current_user.theme_accent}
