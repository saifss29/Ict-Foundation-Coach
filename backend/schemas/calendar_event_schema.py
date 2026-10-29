from datetime import timezone
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
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(
            "Use a valid timezone name, such as Asia/Dhaka."
        ) from None


class CalendarEventInputSchema(Schema):
    class Meta:
        unknown = RAISE

    title = fields.String(
        required=True,
        validate=validate.Length(min=1, max=150),
    )

    description = fields.String(
        load_default="",
        validate=validate.Length(max=2000),
    )

    starts_at = fields.AwareDateTime(
        required=True,
        format="iso",
    )

    ends_at = fields.AwareDateTime(
        required=True,
        format="iso",
    )

    timezone_name = fields.String(
        required=True,
        validate=[
            validate.Length(min=1, max=100),
            validate_timezone_name,
        ],
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()

        for field in (
            "title",
            "description",
            "starts_at",
            "ends_at",
            "timezone_name",
        ):
            value = cleaned.get(field)

            if isinstance(value, str):
                cleaned[field] = value.strip()

        return cleaned

    @validates_schema
    def validate_event_times(self, data, **kwargs):
        starts_at = data["starts_at"].astimezone(timezone.utc)
        ends_at = data["ends_at"].astimezone(timezone.utc)

        if ends_at <= starts_at:
            raise ValidationError({
                "ends_at": [
                    "End time must be after start time."
                ]
            })

        data["starts_at"] = starts_at
        data["ends_at"] = ends_at


class CreateCalendarEventSchema(CalendarEventInputSchema):
    request_id = fields.UUID(
        required=False,
        allow_none=False,
    )


class UpdateCalendarEventSchema(CalendarEventInputSchema):
    # Update sends the full event and the version last read by the client.
    version = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )