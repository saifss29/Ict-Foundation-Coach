from extensions import db


class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        db.UniqueConstraint(
            "topic_id",
            "display_order",
            name="unique_question_order_per_topic",
        ),
        db.CheckConstraint(
            "correct_option IN ('A', 'B', 'C', 'D')",
            name="valid_correct_option",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey("topics.id"),
        nullable=False,
        index=True,
    )
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    display_order = db.Column(db.Integer, nullable=False)

    def __init__(
        self,
        topic_id: int,
        question_text: str,
        option_a: str,
        option_b: str,
        option_c: str,
        option_d: str,
        correct_option: str,
        explanation: str,
        display_order: int,
    ):
        self.topic_id = topic_id
        self.question_text = question_text
        self.option_a = option_a
        self.option_b = option_b
        self.option_c = option_c
        self.option_d = option_d
        self.correct_option = correct_option
        self.explanation = explanation
        self.display_order = display_order