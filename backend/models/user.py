from datetime import datetime, timezone

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('student', 'teacher')",
            name="valid_user_role",
        ),
        db.CheckConstraint(
            "token_version >= 0",
            name="valid_user_token_version",
        ),
        db.CheckConstraint(
            "academic_level IS NULL OR "
            "academic_level IN ('ssc', 'hsc')",
            name="valid_user_academic_level",
        ),
        db.CheckConstraint(
            "role != 'teacher' OR academic_level IS NULL",
            name="teacher_has_no_academic_level",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    name = db.Column(
        db.String(100),
        nullable=False,
    )

    email = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="student",
        server_default="student",
    )

    academic_level = db.Column(
        db.String(10),
        nullable=True,
    )

    token_version = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    is_email_verified = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    parent_email = db.Column(
        db.String(255),
        nullable=True,
    )

    parent_email_verified_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    weekly_report_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )

    def __init__(
        self,
        name: str,
        email: str,
        password_hash: str,
        role: str = "student",
        academic_level: str | None = None,
    ):
        if academic_level is not None and (
            not isinstance(academic_level, str)
            or academic_level not in ("ssc", "hsc")
        ):
            raise ValueError(
                "Study level must be SSC or HSC."
            )

        if role == "teacher" and academic_level is not None:
            raise ValueError(
                "Study level applies only to students."
            )

        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.academic_level = academic_level
        self.token_version = 0
        self.is_email_verified = False