import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

from flask import current_app

from extensions import db
from models.email_verification_token import EmailVerificationToken
from models.user import User
from services.email_service import EmailDeliveryError, send_email


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_verification_email(user: User) -> None:
    """Prepare a token and send its link within the caller's transaction.

    The caller must lock an existing user before calling this function,
    commit on success, and roll back on failure.
    """
    if user.is_email_verified:
        raise ValueError("This email is already verified.")

    frontend_url = current_app.config.get("FRONTEND_URL")
    lifetime = current_app.config.get(
        "EMAIL_VERIFICATION_TOKEN_EXPIRES"
    )

    if (
        not isinstance(frontend_url, str)
        or not frontend_url.strip()
        or not isinstance(lifetime, timedelta)
        or lifetime <= timedelta(0)
    ):
        raise EmailDeliveryError(
            "Email verification configuration is incomplete."
        )

    frontend_url = frontend_url.strip().rstrip("/")
    parsed_url = urlsplit(frontend_url)

    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise EmailDeliveryError(
            "Frontend URL configuration is invalid."
        )

    # Registration must flush the new user before calling this service.
    if user.id is None:
        raise ValueError(
            "Save the user with db.session.flush() before sending verification."
        )

    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)

    # A new link replaces earlier unused links for this account.
    db.session.execute(
        db.update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    verification_token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_verification_token(raw_token),
        expires_at=now + lifetime,
    )

    db.session.add(verification_token)
    db.session.flush()

    verification_link = (
        f"{frontend_url}/verify-email?"
        f"{urlencode({'token': raw_token})}"
    )

    expiry_hours = lifetime.total_seconds() / 3600

    send_email(
        recipient=user.email,
        subject="Verify your ICT Foundation Coach email",
        body=(
            "Welcome to ICT Foundation Coach!\n\n"
            "Open this link to verify your email address:\n\n"
            f"{verification_link}\n\n"
            f"This link expires in {expiry_hours:g} hours.\n\n"
            "If you did not request this account, ignore this email.\n"
        ),
    )