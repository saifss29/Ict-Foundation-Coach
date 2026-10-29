from datetime import datetime, timezone
from typing import cast

from flask import Blueprint, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, limiter
from models.email_verification_token import EmailVerificationToken
from models.user import User
from schemas.email_verification_schema import (
    ResendVerificationSchema,
    VerifyEmailSchema,
)
from services.email_service import EmailDeliveryError
from services.email_verification_service import (
    hash_verification_token,
    send_verification_email,
)


email_verification_bp = Blueprint(
    "email_verification",
    __name__,
    url_prefix="/api/auth",
)

verify_email_schema = VerifyEmailSchema()
resend_verification_schema = ResendVerificationSchema()

VERIFICATION_REQUEST_MESSAGE = (
    "If an unverified account exists with this email, "
    "you will receive a verification link."
)

INVALID_TOKEN_MESSAGE = (
    "This verification link is invalid or expired."
)


@email_verification_bp.errorhandler(429)
def handle_rate_limit_exceeded(error):
    return jsonify({
        "error": "Too many requests. Please wait and try again.",
    }), 429


def as_utc(value: datetime) -> datetime:
    # SQLite tests may return timestamps without timezone information.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


@email_verification_bp.post("/verify-email")
def verify_email():
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        data = cast(
            dict[str, str],
            verify_email_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        token_hash = hash_verification_token(data["token"])

        owner_id = db.session.scalar(
            db.select(EmailVerificationToken.user_id).where(
                EmailVerificationToken.token_hash == token_hash
            )
        )

        if owner_id is None:
            db.session.rollback()
            return jsonify({
                "error": INVALID_TOKEN_MESSAGE
            }), 400

        # Use the same lock order as resend: user first, then token.
        user = db.session.scalar(
            db.select(User)
            .where(User.id == owner_id)
            .with_for_update()
        )

        verification_token = db.session.scalar(
            db.select(EmailVerificationToken)
            .where(
                EmailVerificationToken.token_hash == token_hash
            )
            .with_for_update()
        )

        now = datetime.now(timezone.utc)

        if (
            user is None
            or verification_token is None
            or verification_token.used_at is not None
            or as_utc(verification_token.expires_at) <= now
        ):
            db.session.rollback()
            return jsonify({
                "error": INVALID_TOKEN_MESSAGE
            }), 400

        user.is_email_verified = True

        # Consume this link and invalidate other unused verification links.
        db.session.execute(
            db.update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not verify email. Try again later."
        }), 500

    return jsonify({
        "message": "Email verified successfully. Please log in."
    }), 200


@email_verification_bp.post("/resend-verification")
@limiter.limit("3 per minute; 10 per hour")
def resend_verification():
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
            resend_verification_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        user = db.session.scalar(
            db.select(User)
            .where(User.email == data["email"].lower())
            .with_for_update()
        )

        if user is None or user.is_email_verified:
            db.session.rollback()
            return jsonify({
                "message": VERIFICATION_REQUEST_MESSAGE
            }), 200

        send_verification_email(user)
        db.session.commit()

    except EmailDeliveryError:
        db.session.rollback()
        return jsonify({
            "error": (
                "Verification email could not be sent. "
                "Try again later."
            )
        }), 503

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not process verification. Try again later."
        }), 500

    return jsonify({
        "message": VERIFICATION_REQUEST_MESSAGE
    }), 200