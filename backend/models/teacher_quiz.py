from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class TeacherQuiz(db.Model):
    __tablename__ = "teacher_quizzes"

    __table_args__ = (
        db.CheckConstraint(
            "response_language IN ('banglish', 'english')",
            name="valid_teacher_quiz_language",
        ),
        db.CheckConstraint(
            "status IN ('draft', 'published')",
            name="valid_teacher_quiz_status",
        ),
        db.CheckConstraint(
            "question_count BETWEEN 1 AND 20",
            name="valid_teacher_quiz_question_count",
        ),
        db.CheckConstraint(
            "learning_mode IN ('exam_preparation', 'personal_growth')",
            name="valid_teacher_quiz_learning_mode",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    topic_id = db.Column(
        db.Integer,
        db.ForeignKey("topics.id"),
        nullable=False,
        index=True,
    )

    title = db.Column(
        db.String(150),
        nullable=False,
    )

    response_language = db.Column(
        db.String(10),
        nullable=False,
    )

    question_count = db.Column(
        db.Integer,
        nullable=False,
        default=5,
        server_default="5",
    )
    learning_mode = db.Column(
        db.String(20),
        nullable=False,
        default="personal_growth",
        server_default="personal_growth",
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    questions = db.Column(
        db.JSON,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    removed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    published_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    def __init__(
        self,
        teacher_id: int,
        topic_id: int,
        title: str,
        response_language: str,
        questions: list[dict[str, str]],
        question_count: int = 5,
        learning_mode: str = "personal_growth",
    ):
        if (
            isinstance(question_count, bool)
            or not isinstance(question_count, int)
            or not 1 <= question_count <= 20
        ):
            raise ValueError(
                "Question count must be an integer between 1 and 20."
            )

        if learning_mode not in (
            "exam_preparation",
            "personal_growth",
        ):
            raise ValueError(
                "Learning mode must be exam_preparation or personal_growth."
            )

        self.teacher_id = teacher_id
        self.topic_id = topic_id
        self.title = title
        self.response_language = response_language
        self.question_count = question_count
        self.learning_mode = learning_mode
        self.questions = questions
        self.status = "draft"