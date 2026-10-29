from decimal import Decimal
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


def validate_marks(value: Decimal):
    if not value.is_finite():
        raise ValidationError("Marks must be a finite number.")

    if value < 0 or value > Decimal("9999.99"):
        raise ValidationError(
            "Marks must be between 0 and 9999.99."
        )

    if value != value.quantize(Decimal("0.01")):
        raise ValidationError(
            "Marks can have at most two decimal places."
        )


def validate_timezone(value: str):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("Use a valid timezone name.")


class CreateClassExamSchema(Schema):
    class Meta:
        unknown = RAISE

    title = fields.String(
        required=True,
        validate=validate.Length(min=3, max=150),
    )

    description = fields.String(
        load_default="",
        validate=validate.Length(max=2000),
    )

    total_marks = fields.Decimal(
        required=True,
        allow_nan=False,
        validate=validate_marks,
    )

    starts_at = fields.AwareDateTime(required=True)
    ends_at = fields.AwareDateTime(required=True)

    timezone_name = fields.String(
        required=True,
        validate=[
            validate.Length(min=1, max=100),
            validate_timezone,
        ],
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()

        for field in ("title", "description", "timezone_name"):
            value = cleaned.get(field)

            if isinstance(value, str):
                cleaned[field] = value.strip()

        if isinstance(cleaned.get("total_marks"), bool):
            raise ValidationError({
                "total_marks": ["Marks must be a number."]
            })

        return cleaned

    @validates_schema
    def validate_exam(self, data, **kwargs):
        errors = {}

        if data["total_marks"] <= 0:
            errors["total_marks"] = [
                "Total marks must be greater than zero."
            ]

        if data["ends_at"] <= data["starts_at"]:
            errors["ends_at"] = [
                "End time must be after start time."
            ]

        if errors:
            raise ValidationError(errors)


class ClassExamMarkSchema(Schema):
    class Meta:
        unknown = RAISE

    student_id = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )

    obtained_marks = fields.Decimal(
        load_default=None,
        allow_none=True,
        allow_nan=False,
        validate=validate_marks,
    )

    is_absent = fields.Boolean(load_default=False)

    @pre_load
    def validate_input_types(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Each result must be a JSON object."
            )

        errors = {}

        if isinstance(data.get("obtained_marks"), bool):
            errors["obtained_marks"] = [
                "Marks must be a number."
            ]

        if (
            "is_absent" in data
            and not isinstance(data["is_absent"], bool)
        ):
            errors["is_absent"] = [
                "Absent status must be true or false."
            ]

        if errors:
            raise ValidationError(errors)

        return data

    @validates_schema
    def validate_result(self, data, **kwargs):
        marks = data["obtained_marks"]

        if data["is_absent"] and marks is not None:
            raise ValidationError({
                "obtained_marks": [
                    "An absent student cannot have marks."
                ]
            })

        if not data["is_absent"] and marks is None:
            raise ValidationError({
                "obtained_marks": [
                    "Enter marks or mark the student absent."
                ]
            })


class UpdateClassExamResultsSchema(Schema):
    class Meta:
        unknown = RAISE

    results = fields.List(
        fields.Nested(ClassExamMarkSchema),
        required=True,
        validate=validate.Length(min=1, max=1000),
    )

    @pre_load
    def validate_body(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        return data

    @validates_schema
    def validate_unique_students(self, data, **kwargs):
        student_ids = [
            result["student_id"]
            for result in data["results"]
        ]

        if len(student_ids) != len(set(student_ids)):
            raise ValidationError({
                "results": [
                    "Include each student only once."
                ]
            })