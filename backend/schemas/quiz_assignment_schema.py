from datetime import timezone
from uuid import UUID

from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


class CreateQuizAssignmentSchema(Schema):
    class Meta:
        unknown = RAISE

    quiz_id = fields.UUID(required=True)

    classroom_id = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )

    audience = fields.String(
        required=True,
        validate=validate.OneOf(["all", "selected"]),
    )

    student_ids = fields.List(
        fields.Integer(
            strict=True,
            validate=validate.Range(min=1),
        ),
        load_default=list,
        validate=validate.Length(max=500),
    )

    available_at = fields.AwareDateTime(
        required=True,
        format="iso",
    )

    deadline_at = fields.AwareDateTime(
        required=True,
        format="iso",
    )

    time_limit_minutes = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1, max=180),
    )

    max_attempts = fields.Integer(
        load_default=1,
        strict=True,
        validate=validate.Range(min=1, max=5),
    )

    review_at = fields.AwareDateTime(
        required=True,
        format="iso",
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()

        for field in (
            "quiz_id",
            "audience",
            "available_at",
            "deadline_at",
            "review_at",
        ):
            value = cleaned.get(field)

            if isinstance(value, str):
                cleaned[field] = value.strip()

        return cleaned

    @validates_schema
    def validate_assignment(self, data, **kwargs):
        errors = {}
        student_ids = data["student_ids"]

        if data["audience"] == "all" and student_ids:
            errors["student_ids"] = [
                "Do not provide student IDs when assigning to the whole class."
            ]

        if data["audience"] == "selected" and not student_ids:
            errors["student_ids"] = [
                "Select at least one student."
            ]

        if len(student_ids) != len(set(student_ids)):
            errors.setdefault("student_ids", []).append(
                "Duplicate student IDs are not allowed."
            )

        available_at = data["available_at"].astimezone(timezone.utc)
        deadline_at = data["deadline_at"].astimezone(timezone.utc)
        review_at = data["review_at"].astimezone(timezone.utc)

        if deadline_at <= available_at:
            errors["deadline_at"] = [
                "Deadline must be after the availability time."
            ]

        if review_at < deadline_at:
            errors["review_at"] = [
                "Review time must be at or after the deadline."
            ]

        if errors:
            raise ValidationError(errors)

        # Store and compare all assignment times in UTC.
        data["available_at"] = available_at
        data["deadline_at"] = deadline_at
        data["review_at"] = review_at

        # fields.UUID returns a UUID object; the model uses String(36).
        quiz_id: UUID = data["quiz_id"]
        data["quiz_id"] = str(quiz_id)