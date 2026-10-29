from marshmallow import (
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


class CreateTeacherQuizSchema(Schema):
    class Meta:
        unknown = RAISE

    topic_id = fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    )

    title = fields.String(
        required=True,
        validate=validate.Length(min=3, max=150),
    )

    question_count = fields.Integer(
        load_default=5,
        strict=True,
        validate=validate.Range(min=1, max=20),
    )

    response_language = fields.String(
        load_default="banglish",
        validate=validate.OneOf(
            ["banglish", "english"],
            error="Response language must be banglish or english.",
        ),
    )

    learning_mode = fields.String(
        load_default="personal_growth",
        validate=validate.OneOf(
            ["exam_preparation", "personal_growth"],
            error=(
                "Learning mode must be exam_preparation "
                "or personal_growth."
            ),
        ),
    )

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()

        for field in ("title", "response_language"):
            value = cleaned.get(field)

            if isinstance(value, str):
                cleaned[field] = value.strip()

        return cleaned


class TeacherQuizQuestionSchema(Schema):
    class Meta:
        unknown = RAISE

    id = fields.String(
        required=True,
        validate=validate.OneOf(
            [str(index) for index in range(1, 21)]
        ),
    )

    question_text = fields.String(
        required=True,
        validate=validate.Length(min=1, max=1000),
    )

    option_a = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )

    option_b = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )

    option_c = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )

    option_d = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )

    correct_option = fields.String(
        required=True,
        validate=validate.OneOf(
            ["A", "B", "C", "D"],
            error="Correct option must be A, B, C, or D.",
        ),
    )

    explanation = fields.String(
        required=True,
        validate=validate.Length(min=1, max=2000),
    )

    @pre_load
    def normalize_question(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Each question must be a JSON object."
            )

        cleaned = data.copy()

        for field, value in cleaned.items():
            if isinstance(value, str):
                cleaned[field] = value.strip()

        return cleaned

    @validates_schema
    def validate_distinct_options(self, data, **kwargs):
        options = [
            data[field].casefold()
            for field in (
                "option_a",
                "option_b",
                "option_c",
                "option_d",
            )
        ]

        if len(set(options)) != 4:
            raise ValidationError({
                "options": [
                    "All four answer options must be different."
                ]
            })


class UpdateTeacherQuizSchema(Schema):
    class Meta:
        unknown = RAISE

    title = fields.String(
        required=True,
        validate=validate.Length(min=3, max=150),
    )

    questions = fields.List(
        fields.Nested(TeacherQuizQuestionSchema),
        required=True,
        validate=validate.Length(min=1, max=20),
    )

    def __init__(
        self,
        *args,
        expected_question_count=5,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if (
            isinstance(expected_question_count, bool)
            or not isinstance(expected_question_count, int)
            or not 1 <= expected_question_count <= 20
        ):
            raise ValueError(
                "Expected question count must be an integer "
                "between 1 and 20."
            )

        self.expected_question_count = expected_question_count

    @pre_load
    def normalize_input(self, data, **kwargs):
        if not isinstance(data, dict):
            raise ValidationError(
                "Request body must be a JSON object."
            )

        cleaned = data.copy()
        title = cleaned.get("title")

        if isinstance(title, str):
            cleaned["title"] = title.strip()

        return cleaned

    @validates_schema
    def validate_questions(self, data, **kwargs):
        questions = data["questions"]
        expected_count = self.expected_question_count

        if len(questions) != expected_count:
            raise ValidationError({
                "questions": [
                    f"Include exactly {expected_count} questions."
                ]
            })

        question_ids = [
            question["id"]
            for question in questions
        ]

        expected_ids = {
            str(index)
            for index in range(1, expected_count + 1)
        }

        if set(question_ids) != expected_ids:
            raise ValidationError({
                "questions": [
                    f"Include each question ID from 1 to "
                    f"{expected_count} exactly once."
                ]
            })

        question_texts = [
            question["question_text"].casefold()
            for question in questions
        ]

        if len(set(question_texts)) != len(question_texts):
            raise ValidationError({
                "questions": [
                    "Duplicate questions are not allowed."
                ]
            })