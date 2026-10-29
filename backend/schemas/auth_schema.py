from marshmallow import (
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)


# A small starter blocklist, not a complete breached-password database.
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "password123!",
    "12345678",
    "123456789",
    "1234567890",
    "qwerty123",
    "qwerty123!",
    "abcdefgh",
    "abcdefgh123",
    "letmein123",
    "welcome123",
    "welcome123!",
    "admin123",
    "admin1234",
    "iloveyou",
}


def validate_registration_password(password: str) -> None:
    # Normalize only for comparison; preserve the actual password.
    comparison = password.strip().casefold()

    if not comparison:
        raise ValidationError(
            "Password cannot contain only spaces."
        )

    if comparison in COMMON_PASSWORDS:
        raise ValidationError(
            "This password is too common. Choose a less predictable password."
        )

    if len(set(comparison)) == 1:
        raise ValidationError(
            "Password cannot consist of one repeated character."
        )


class RegisterSchema(Schema):
    name = fields.String(
        required=True,
        validate=validate.Length(min=2, max=100),
    )

    email = fields.Email(required=True)

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

    role = fields.String(
        load_default="student",
        validate=validate.OneOf(
            ["student", "teacher"],
            error="Role must be student or teacher.",
        ),
    )

    academic_level = fields.String(
        validate=validate.OneOf(
            ["ssc", "hsc"],
            error="Study level must be SSC or HSC.",
        ),
    )

    @validates_schema
    def validate_academic_level(self, data, **kwargs):
        if data["role"] == "student":
            if "academic_level" not in data:
                raise ValidationError({
                    "academic_level": [
                        "Select SSC or HSC."
                    ],
                })

        elif "academic_level" in data:
            raise ValidationError({
                "academic_level": [
                    "Study level applies only to students."
                ],
            })

class LoginSchema(Schema):
    email = fields.Email(required=True)

    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128),
    )