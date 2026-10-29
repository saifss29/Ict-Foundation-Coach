from datetime import datetime, timezone

from extensions import db


class LearningAssignmentSubmission(db.Model):
    __tablename__ = "learning_assignment_submissions"

    __table_args__ = (
        db.UniqueConstraint(
            "recipient_id",
            name="unique_learning_assignment_recipient_submission",
        ),
        db.CheckConstraint(
            "length(trim(answer_text)) > 0 "
            "OR length(trim(code_text)) > 0",
            name="nonempty_learning_assignment_submission",
        ),
        db.CheckConstraint(
            "obtained_marks IS NULL OR obtained_marks >= 0",
            name="nonnegative_learning_assignment_submission_marks",
        ),
        db.CheckConstraint(
            "(reviewed_at IS NULL "
            "AND reviewed_by IS NULL "
            "AND obtained_marks IS NULL) "
            "OR "
            "(reviewed_at IS NOT NULL "
            "AND reviewed_by IS NOT NULL "
            "AND obtained_marks IS NOT NULL)",
            name="consistent_learning_assignment_submission_review",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    recipient_id = db.Column(
        db.Integer,
        db.ForeignKey("learning_assignment_recipients.id"),
        nullable=False,
    )

    answer_text = db.Column(
        db.Text,
        nullable=False,
        default="",
        server_default="",
    )

    code_text = db.Column(
        db.Text,
        nullable=False,
        default="",
        server_default="",
    )

    submitted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    obtained_marks = db.Column(
        db.Numeric(6, 2),
        nullable=True,
    )

    feedback = db.Column(
        db.Text,
        nullable=False,
        default="",
        server_default="",
    )
    ai_feedback = db.Column(
        db.JSON,
        nullable=True,
    )

    ai_feedback_generated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    reviewed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    def __init__(
        self,
        recipient_id: int,
        answer_text: str = "",
        code_text: str = "",
    ):
        self.recipient_id = recipient_id
        self.answer_text = answer_text
        self.code_text = code_text
        self.feedback = ""