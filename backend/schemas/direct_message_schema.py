from marshmallow import RAISE, Schema, fields, validate


class CreateDirectConversationSchema(Schema):
    class Meta:
        unknown = RAISE

    recipient_id = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )


class SendDirectMessageSchema(Schema):
    class Meta:
        unknown = RAISE

    content = fields.String(
        required=True,
        validate=validate.Length(min=1, max=2000),
    )