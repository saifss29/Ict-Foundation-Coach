from marshmallow import Schema, fields, validate


class CreateClassroomSchema(Schema):
    name = fields.String(
        required=True,
        validate=validate.Length(min=2, max=100),
    )


class JoinClassroomSchema(Schema):
    join_code = fields.String(
        required=True,
        validate=validate.Regexp(
            r"^[A-Z0-9]{8}$",
            error="Join code must contain 8 uppercase letters or numbers.",
        ),
    )