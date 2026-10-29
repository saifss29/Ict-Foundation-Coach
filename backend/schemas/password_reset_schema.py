from marshmallow import Schema, fields, validate

from schemas.auth_schema import validate_registration_password


class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    token = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=1, max=256),
    )

    password = fields.String(
        required=True,
        load_only=True,
        validate=[
            validate.Length(
                min=8,
                max=128,
                error="Password must be between 8 and 128 characters.",
            ),
            validate_registration_password,
        ],
    )