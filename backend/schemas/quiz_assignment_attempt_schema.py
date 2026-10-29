from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
)


class QuizAssignmentAnswersSchema(Schema):
    class Meta:
        unknown = RAISE

    answers = fields.Dict(
        keys=fields.String(
            validate=validate.OneOf(
                [str(number) for number in range(1, 21)],
                error="Question ID must be between 1 and 20.",
            ),
        ),
        values=fields.String(
            validate=validate.OneOf(
                ["A", "B", "C", "D"],
                error="Answer must be A, B, C, or D.",
            ),
        ),
        required=True,
        validate=validate.Length(max=20),
    )

    @pre_load
    def validate_request_object(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        return data