from datetime import timezone
from decimal import Decimal

from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


def validate_marks(value):
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


class CreateLearningAssignmentSchema(Schema):
    class Meta:
        unknown = RAISE

    classroom_id = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )

    title = fields.String(
        required=True,
        validate=validate.Length(min=3, max=150),
    )

    instructions = fields.String(
        required=True,
        validate=validate.Length(min=1, max=10000),
    )
    reference_answer = fields.String(
        load_default="",
        validate=validate.Length(max=10000),
    )

    task_type = fields.String(
        required=True,
        validate=validate.OneOf(["written", "practical"]),
    )

    audience = fields.String(
        load_default="all",
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

    total_marks = fields.Decimal(
        required=True,
        allow_nan=False,
        validate=validate_marks,
    )

    available_at = fields.DateTime(required=True)
    deadline_at = fields.DateTime(required=True)

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()

        for field in (
            "title",
            "instructions",
            "reference_answer",
            "task_type",
            "audience",
        ):
            value = cleaned.get(field)

            if isinstance(value, str):
                cleaned[field] = value.strip()

        return cleaned

    @validates_schema
    def validate_assignment(self, data, **kwargs):
        errors = {}

        if data["total_marks"] <= 0:
            errors["total_marks"] = [
                "Total marks must be greater than zero."
            ]

        student_ids = data["student_ids"]

        if len(student_ids) != len(set(student_ids)):
            errors["student_ids"] = [
                "Duplicate student IDs are not allowed."
            ]

        if data["audience"] == "selected" and not student_ids:
            errors["student_ids"] = [
                "Select at least one student."
            ]

        if data["audience"] == "all" and student_ids:
            errors["student_ids"] = [
                "Do not include student IDs when assigning to all."
            ]

        for field in ("available_at", "deadline_at"):
            value = data[field]

            if (
                value.tzinfo is None
                or value.utcoffset() is None
            ):
                errors[field] = [
                    "Include a timezone, such as Z or +06:00."
                ]
            else:
                data[field] = value.astimezone(timezone.utc)

        if (
            "available_at" not in errors
            and "deadline_at" not in errors
            and data["deadline_at"] <= data["available_at"]
        ):
            errors["deadline_at"] = [
                "Deadline must be after the available time."
            ]

        if errors:
            raise ValidationError(errors)


class SubmitLearningAssignmentSchema(Schema):
    class Meta:
        unknown = RAISE

    answer_text = fields.String(
        load_default="",
        validate=validate.Length(max=20000),
    )

    code_text = fields.String(
        load_default="",
        validate=validate.Length(max=50000),
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()
        answer_text = cleaned.get("answer_text")

        if isinstance(answer_text, str):
            cleaned["answer_text"] = answer_text.strip()

        # Preserve code indentation and line breaks.
        return cleaned

    @validates_schema
    def validate_submission(self, data, **kwargs):
        if (
            not data["answer_text"].strip()
            and not data["code_text"].strip()
        ):
            raise ValidationError({
                "answer_text": [
                    "Write an answer or include code before submitting."
                ]
            })


class ReviewLearningAssignmentSchema(Schema):
    class Meta:
        unknown = RAISE

    obtained_marks = fields.Decimal(
        required=True,
        allow_nan=False,
        validate=validate_marks,
    )

    feedback = fields.String(
        load_default="",
        validate=validate.Length(max=5000),
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()
        feedback = cleaned.get("feedback")

        if isinstance(feedback, str):
            cleaned["feedback"] = feedback.strip()

        return cleaned