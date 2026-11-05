"""Real SMTP delivery for password recovery emails.

Nothing here fakes a send: if SMTP is not configured the caller gets an
explicit ``EmailNotConfigured`` error, and if the server rejects the message an
``EmailDeliveryError`` is raised. Neither error carries the token or password.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailNotConfigured(RuntimeError):
    """SMTP settings are missing, so no real email can be sent."""


class EmailDeliveryError(RuntimeError):
    """SMTP is configured but the message could not be delivered."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _smtp_settings() -> dict | None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    from_email = (os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_FROM") or "").strip()
    if not host or not from_email:
        return None
    return {
        "host": host,
        "port": _env_int("SMTP_PORT", 587),
        "username": (os.getenv("SMTP_USERNAME") or "").strip(),
        "password": os.getenv("SMTP_PASSWORD") or "",
        "from_email": from_email,
        "from_name": (os.getenv("SMTP_FROM_NAME") or "ReeStack").strip(),
        "use_tls": _env_bool("SMTP_USE_TLS", True),
        "use_ssl": _env_bool("SMTP_USE_SSL", False),
        "timeout": _env_int("SMTP_TIMEOUT", 10),
    }


def ensure_email_configured() -> None:
    if _smtp_settings() is None:
        raise EmailNotConfigured(
            "SMTP_HOST and SMTP_FROM_EMAIL must be configured to send recovery emails"
        )


def _build_message(settings: dict, to_email: str, reset_link: str, expires_minutes: int) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Recuperá tu contraseña de ReeStack"
    message["From"] = f"{settings['from_name']} <{settings['from_email']}>"
    message["To"] = to_email
    message.set_content(
        "Hola:\n\n"
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta en ReeStack.\n\n"
        f"Abrí este enlace para elegir una nueva contraseña. Vence en {expires_minutes} minutos "
        "y solo puede usarse una vez:\n\n"
        f"{reset_link}\n\n"
        "Si no solicitaste este cambio, ignorá este correo. Tu contraseña actual sigue funcionando.\n\n"
        "— Equipo de ReeStack\n"
    )
    return message


def send_password_reset_email(to_email: str, reset_link: str, expires_minutes: int) -> None:
    """Deliver the recovery link through SMTP.

    The token lives only inside ``reset_link`` and is never logged. Errors are
    re-raised with a sanitized message so callers can log the failure class
    without leaking the link.
    """
    settings = _smtp_settings()
    if settings is None:
        raise EmailNotConfigured(
            "SMTP_HOST and SMTP_FROM_EMAIL must be configured to send recovery emails"
        )

    message = _build_message(settings, to_email, reset_link, expires_minutes)

    try:
        if settings["use_ssl"]:
            with smtplib.SMTP_SSL(
                settings["host"], settings["port"], timeout=settings["timeout"]
            ) as smtp:
                if settings["username"]:
                    smtp.login(settings["username"], settings["password"])
                smtp.send_message(message)
        else:
            with smtplib.SMTP(
                settings["host"], settings["port"], timeout=settings["timeout"]
            ) as smtp:
                smtp.ehlo()
                if settings["use_tls"]:
                    smtp.starttls()
                    smtp.ehlo()
                if settings["username"]:
                    smtp.login(settings["username"], settings["password"])
                smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Do not include the SMTP body, link or token in the raised message.
        raise EmailDeliveryError(f"SMTP delivery failed ({type(exc).__name__})") from exc
