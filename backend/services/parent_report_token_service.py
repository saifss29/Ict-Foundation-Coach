import hashlib
from datetime import datetime, timezone

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer


TOKEN_SALT = "ict-coach-parent-report-unsubscribe-v1"


def verification_fingerprint(
    parent_email: str,
    verified_at: datetime,
) -> str:
    if not isinstance(parent_email, str) or not parent_email:
        raise ValueError("A parent email is required.")

    if not isinstance(verified_at, datetime):
        raise ValueError("Parent verification time is required.")

    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)

    verification_time = verified_at.astimezone(timezone.utc).isoformat()

    value = f"{parent_email}\n{verification_time}"

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def token_serializer():
    secret = current_app.config.get("JWT_SECRET_KEY")

    if not isinstance(secret, str) or not secret:
        raise ValueError("Token signing configuration is missing.")

    return URLSafeSerializer(
        secret_key=secret,
        salt=TOKEN_SALT,
    )


def create_parent_unsubscribe_token(
    *,
    student_id: int,
    parent_email: str,
    verified_at: datetime,
) -> str:
    return token_serializer().dumps({
        "student_id": student_id,
        "fingerprint": verification_fingerprint(
            parent_email,
            verified_at,
        ),
    })


def read_parent_unsubscribe_token(token: str) -> dict:
    if not isinstance(token, str) or not 20 <= len(token) <= 1000:
        raise ValueError("Invalid unsubscribe link.")

    try:
        payload = token_serializer().loads(token)
    except BadSignature as error:
        raise ValueError("Invalid unsubscribe link.") from error

    if not isinstance(payload, dict):
        raise ValueError("Invalid unsubscribe link.")

    student_id = payload.get("student_id")
    fingerprint = payload.get("fingerprint")

    if (
        set(payload) != {"student_id", "fingerprint"}
        or isinstance(student_id, bool)
        or not isinstance(student_id, int)
        or student_id < 1
        or not isinstance(fingerprint, str)
        or len(fingerprint) != 64
    ):
        raise ValueError("Invalid unsubscribe link.")

    return payload