from extensions import db


class Topic(db.Model):
    __tablename__ = "topics"

    __table_args__ = (
        db.CheckConstraint(
            "subject IN ('ict', 'math', 'english')",
            name="valid_topic_subject",
        ),
        db.CheckConstraint(
            "academic_level IN ('ssc', 'hsc')",
            name="valid_topic_academic_level",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    title = db.Column(
        db.String(100),
        nullable=False,
        unique=True,
    )

    slug = db.Column(
        db.String(100),
        nullable=False,
        unique=True,
    )

    description = db.Column(
        db.Text,
        nullable=False,
    )

    display_order = db.Column(
        db.Integer,
        nullable=False,
    )

    subject = db.Column(
        db.String(10),
        nullable=False,
        default="ict",
        server_default="ict",
        index=True,
    )

    academic_level = db.Column(
        db.String(10),
        nullable=False,
        default="hsc",
        server_default="hsc",
        index=True,
    )

    def __init__(
        self,
        title: str,
        slug: str,
        description: str,
        display_order: int,
        subject: str = "ict",
        academic_level: str = "hsc",
    ):
        self.title = title
        self.slug = slug
        self.description = description
        self.display_order = display_order
        self.subject = subject
        self.academic_level = academic_level