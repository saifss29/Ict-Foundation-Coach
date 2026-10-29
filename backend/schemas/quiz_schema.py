from marshmallow import Schema, fields, validate


class QuizAnswerSchema(Schema):
    question_id = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )
    selected_option = fields.String(
        required=True,
        validate=validate.OneOf(["A", "B", "C", "D"]),
    )


class QuizSubmissionSchema(Schema):
    answers = fields.List(
        fields.Nested(QuizAnswerSchema),
        required=True,
        validate=validate.Length(min=1),
    )