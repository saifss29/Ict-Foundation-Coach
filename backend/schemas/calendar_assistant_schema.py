from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


def validate_timezone_name(value: str):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValidationError("Provide a valid timezone name.") from error


class CalendarAssistantRequestSchema(Schema):
    class Meta:
        unknown = RAISE

    message = fields.String(
        required=True,
        validate=validate.Length(min=1, max=1000),
    )

    timezone_name = fields.String(
        required=True,
        validate=[
            validate.Length(min=1, max=100),
            validate_timezone_name,
        ],
    )

    action = fields.String(
        required=True,
        validate=validate.OneOf(["create", "update"]),
    )

    event_id = fields.UUID(
        load_default=None,
        allow_none=True,
    )

    version = fields.Integer(
        load_default=None,
        allow_none=True,
        strict=True,
        validate=validate.Range(min=1),
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object.")

        cleaned = data.copy()

        for field in ("message", "timezone_name", "action", "event_id"):
            value = cleaned.get(field)

            if isinstance(value, str):
                cleaned[field] = value.strip()

        return cleaned

    @validates_schema
    def validate_action_target(self, data, **kwargs):
        if data["action"] == "update":
            errors = {}

            if data["event_id"] is None:
                errors["event_id"] = [
                    "Select a personal calendar event to update."
                ]

            if data["version"] is None:
                errors["version"] = [
                    "Provide the selected event's current version."
                ]

            if errors:
                raise ValidationError(errors)

        elif data["event_id"] is not None or data["version"] is not None:
            raise ValidationError(
                "Create requests must not include an event ID or version."
            )