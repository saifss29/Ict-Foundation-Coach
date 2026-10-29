from marshmallow import Schema, fields, validate


class CreateTeacherFeedbackSchema(Schema):
    message = fields.String(
        required=True,
        validate=validate.Length(min=1, max=2000),
    )

    attempt_id = fields.Integer(
        load_default=None,
        allow_none=True,
        strict=True,
        validate=validate.Range(min=1),
    )