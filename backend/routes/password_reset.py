import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import urlencode, urlsplit

from flask import Blueprint, current_app, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from extensions import db, limiter
from models.password_reset_token import PasswordResetToken
from models.user import User
from schemas.password_reset_schema import (
    ForgotPasswordSchema,
    ResetPasswordSchema,
)
from services.email_service import EmailDeliveryError, send_email


password_reset_bp = Blueprint(
    "password_reset",
    __name__,
    url_prefix="/api/auth",
)

forgot_password_schema = ForgotPasswordSchema()
reset_password_schema = ResetPasswordSchema()

RESET_REQUEST_MESSAGE = (
    "If an account exists with this email, "
    "you will receive a password reset link."
)

INVALID_TOKEN_MESSAGE = (
    "This password reset link is invalid or expired."
)


@password_reset_bp.errorhandler(429)
def handle_rate_limit_exceeded(error):
    return jsonify({
        "error": "Too many requests. Please wait and try again.",
    }), 429


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    # SQLite tests may return timestamps without timezone information.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


@password_reset_bp.post("/forgot-password")
@limiter.limit("3 per minute; 10 per hour")
def forgot_password():
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    request_data = request_data.copy()

    if isinstance(request_data.get("email"), str):
        request_data["email"] = request_data["email"].strip()

    try:
        data = cast(
            dict[str, str],
            forgot_password_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        # Lock the user row to serialize reset requests for this user.
        user = db.session.scalar(
            db.select(User)
            .where(User.email == data["email"].lower())
            .with_for_update()
        )

        if user is None:
            db.session.rollback()
            return jsonify({
                "message": RESET_REQUEST_MESSAGE
            }), 200

        frontend_url = current_app.config.get("FRONTEND_URL")
        lifetime = current_app.config.get(
            "PASSWORD_RESET_TOKEN_EXPIRES"
        )

        if (
            not isinstance(frontend_url, str)
            or not isinstance(lifetime, timedelta)
            or lifetime.total_seconds() <= 0
        ):
            db.session.rollback()
            return jsonify({
                "error": "Password reset configuration is incomplete."
            }), 503

        parsed_url = urlsplit(frontend_url)

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.query
            or parsed_url.fragment
        ):
            db.session.rollback()
            return jsonify({
                "error": "Password reset configuration is invalid."
            }), 503

        now = datetime.now(timezone.utc)
        raw_token = secrets.token_urlsafe(32)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=now + lifetime,
        )

        # Invalidate earlier unused links for this user.
        db.session.execute(
            db.update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        db.session.add(reset_token)
        db.session.flush()

        reset_link = (
            f"{frontend_url.rstrip('/')}/reset-password?"
            f"{urlencode({'token': raw_token})}"
        )

        expiry_minutes = lifetime.total_seconds() / 60

        send_email(
            recipient=user.email,
            subject="Reset your ICT Foundation Coach password",
            body=(
                "We received a request to reset your password.\n\n"
                f"Open this link to choose a new password:\n{reset_link}\n\n"
                f"This link expires in {expiry_minutes:g} minutes "
                "and can be used only once.\n\n"
                "If you did not request this, ignore this email. "
                "Your password has not changed."
            ),
        )

        db.session.commit()

    except EmailDeliveryError:
        db.session.rollback()
        return jsonify({
            "error": "Password reset email could not be sent. Try again later."
        }), 503

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not process password reset. Try again later."
        }), 500

    return jsonify({
        "message": RESET_REQUEST_MESSAGE
    }), 200


@password_reset_bp.post("/reset-password")
def reset_password():
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        data = cast(
            dict[str, str],
            reset_password_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        token_hash = hash_reset_token(data["token"])

        # Find the owner, then use the same user lock as reset requests.
        owner_id = db.session.scalar(
            db.select(PasswordResetToken.user_id).where(
                PasswordResetToken.token_hash == token_hash
            )
        )

        if owner_id is None:
            db.session.rollback()
            return jsonify({
                "error": INVALID_TOKEN_MESSAGE
            }), 400

        user = db.session.scalar(
            db.select(User)
            .where(User.id == owner_id)
            .with_for_update()
        )

        reset_token = db.session.scalar(
            db.select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash
            )
            .with_for_update()
        )

        now = datetime.now(timezone.utc)

        if (
            user is None
            or reset_token is None
            or reset_token.used_at is not None
            or as_utc(reset_token.expires_at) <= now
        ):
            db.session.rollback()
            return jsonify({
                "error": INVALID_TOKEN_MESSAGE
            }), 400

        user.password_hash = generate_password_hash(
            data["password"]
        )
        user.token_version += 1

        # Consume this link and invalidate any other unused reset links.
        db.session.execute(
            db.update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not reset password. Try again later."
        }), 500

    return jsonify({
        "message": "Password reset successful. Please log in."
    }), 200