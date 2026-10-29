from marshmallow import Schema, fields, validate


class VerifyEmailSchema(Schema):
    token = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=1, max=256),
    )


class ResendVerificationSchema(Schema):
    email = fields.Email(required=True)