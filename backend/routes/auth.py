from typing import cast

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models.token_blocklist import TokenBlocklist
from models.user import User
from schemas.auth_schema import LoginSchema, RegisterSchema
from services.email_service import EmailDeliveryError
from services.email_verification_service import send_verification_email


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

register_schema = RegisterSchema()
login_schema = LoginSchema()

REGISTRATION_ERROR = (
    "Registration could not be completed. "
    "Please check your details."
)


def serialize_user(user: User) -> dict[str, int | str | bool | None]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "academic_level": user.academic_level,
        "is_email_verified": user.is_email_verified,
    }


@auth_bp.errorhandler(429)
def handle_rate_limit_exceeded(error):
    return jsonify({
        "error": "Too many requests. Please wait and try again.",
    }), 429


@auth_bp.post("/register")
@limiter.limit("10 per hour")
def register():
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    request_data = request_data.copy()

    for field in ("name", "email"):
        if isinstance(request_data.get(field), str):
            request_data[field] = request_data[field].strip()

    try:
        user_data = cast(
            dict[str, str],
            register_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    email = user_data["email"].lower()

    try:
        existing_user = db.session.scalar(
            db.select(User).where(User.email == email)
        )

        if existing_user is not None:
            db.session.rollback()
            return jsonify({
                "error": REGISTRATION_ERROR
            }), 400

        user = User(
            name=user_data["name"],
            email=email,
            password_hash=generate_password_hash(
                user_data["password"]
            ),
            role=user_data["role"],
            academic_level=user_data.get("academic_level"),
        )

        db.session.add(user)

        # Assign the user ID without committing the registration.
        db.session.flush()

        send_verification_email(user)

        # Save the account and verification token together.
        db.session.commit()

    except EmailDeliveryError:
        db.session.rollback()
        return jsonify({
            "error": (
                "Registration email could not be sent. "
                "Please try registering again later."
            )
        }), 503

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": REGISTRATION_ERROR
        }), 400

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not register account. Try again later."
        }), 500

    return jsonify({
        "message": (
            "Registration successful. "
            "Check your email to verify your account."
        ),
        "requires_email_verification": True,
        "user": serialize_user(user),
    }), 201


@auth_bp.post("/login")
@limiter.limit("5 per minute")
def login():
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    request_data = request_data.copy()

    if isinstance(request_data.get("email"), str):
        request_data["email"] = request_data["email"].strip()

    try:
        login_data = cast(
            dict[str, str],
            login_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    user = db.session.scalar(
        db.select(User).where(
            User.email == login_data["email"].lower()
        )
    )

    if user is None or not check_password_hash(
        user.password_hash,
        login_data["password"],
    ):
        return jsonify({
            "error": "Invalid email or password"
        }), 401

    # Reveal verification status only after checking the password.
    if not user.is_email_verified:
        return jsonify({
            "error": "Verify your email before logging in.",
            "code": "EMAIL_NOT_VERIFIED",
        }), 403

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "token_version": user.token_version,
        },
    )

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "user": serialize_user(user),
    }), 200


@auth_bp.get("/me")
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    return jsonify({
        "user": serialize_user(user),
    }), 200


@auth_bp.patch("/me/academic-level")
@jwt_required()
def set_academic_level():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if user.role != "student":
        return jsonify({
            "error": "Only students can select a study level"
        }), 403

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    if set(request_data) != {"academic_level"}:
        return jsonify({
            "error": "Include only academic_level"
        }), 400

    academic_level = request_data["academic_level"]

    if (
        not isinstance(academic_level, str)
        or academic_level not in ("ssc", "hsc")
    ):
        return jsonify({
            "error": "Study level must be SSC or HSC."
        }), 400

    try:
        users_table = db.metadata.tables["users"]

        # Only update accounts whose study level is still unset.
        updated_user_id = db.session.execute(
            users_table.update()
            .where(
                users_table.c["id"] == user.id,
                users_table.c["role"] == "student",
                users_table.c["academic_level"].is_(None),
            )
            .values(academic_level=academic_level)
            .returning(users_table.c["id"])
        ).scalar_one_or_none()

        if updated_user_id is None:
            db.session.rollback()
            db.session.refresh(user)

            # Repeating the same selection is allowed.
            if user.academic_level != academic_level:
                return jsonify({
                    "error": "Your study level has already been selected.",
                    "code": "ACADEMIC_LEVEL_ALREADY_SET",
                }), 409
        else:
            db.session.commit()
            db.session.refresh(user)

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not save study level. Try again later."
        }), 500

    return jsonify({
        "message": "Study level saved",
        "user": serialize_user(user),
    }), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    token_jti = get_jwt()["jti"]

    revoked_token = TokenBlocklist(  # type: ignore
        jti=token_jti
    )

    db.session.add(revoked_token)
    db.session.commit()

    return jsonify({
        "message": "Logout successful"
    }), 200