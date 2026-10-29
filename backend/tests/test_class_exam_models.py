from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.class_exam import ClassExam
from models.class_exam_result import ClassExamResult
from models.classroom import Classroom
from models.user import User


@pytest.fixture()
def exam_records(app):
    with app.app_context():
        teacher = User(
            name="Exam Teacher",
            email="exam-teacher@example.com",
            password_hash="unused",
            role="teacher",
        )
        student = User(
            name="Exam Student",
            email="exam-student@example.com",
            password_hash="unused",
            role="student",
            academic_level="hsc",
        )

        db.session.add_all([teacher, student])
        db.session.flush()

        classroom = Classroom(
            name="Exam Test Class",
            teacher_id=teacher.id,
            join_code="EXAM1234",
        )
        db.session.add(classroom)
        db.session.flush()

        start = datetime(2026, 11, 1, 4, tzinfo=timezone.utc)

        exam = ClassExam(
            classroom_id=classroom.id,
            title="1st Term ICT",
            total_marks=Decimal("30.00"),
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            timezone_name="Asia/Dhaka",
        )
        db.session.add(exam)
        db.session.flush()

        result = ClassExamResult(
            exam_id=exam.id,
            student_id=student.id,
        )
        db.session.add(result)
        db.session.commit()

        return {
            "exam_id": exam.id,
            "result_id": result.id,
            "student_id": student.id,
            "classroom_id": classroom.id,
        }


def test_exam_and_recipient_persist_with_defaults(app, exam_records):
    with app.app_context():
        db.session.expire_all()

        exam = db.session.get(ClassExam, exam_records["exam_id"])
        result = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )

        assert exam is not None
        assert len(exam.id) == 36
        assert exam.classroom_id == exam_records["classroom_id"]
        assert exam.title == "1st Term ICT"
        assert exam.total_marks == Decimal("30.00")
        assert exam.ends_at > exam.starts_at
        assert exam.timezone_name == "Asia/Dhaka"
        assert exam.description == ""
        assert exam.results_published_at is None
        assert exam.created_at is not None
        assert exam.updated_at is not None

        assert result is not None
        assert result.exam_id == exam.id
        assert result.student_id == exam_records["student_id"]
        assert result.obtained_marks is None
        assert result.is_absent is False
        assert result.created_at is not None


@pytest.mark.parametrize("minutes", [0, -30])
def test_exam_rejects_invalid_date_order(app, exam_records, minutes):
    with app.app_context():
        exam = db.session.get(ClassExam, exam_records["exam_id"])
        assert exam is not None

        exam.ends_at = exam.starts_at + timedelta(minutes=minutes)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        saved = db.session.get(ClassExam, exam_records["exam_id"])
        assert saved is not None
        assert saved.ends_at > saved.starts_at


@pytest.mark.parametrize("marks", [Decimal("0"), Decimal("-1")])
def test_exam_rejects_nonpositive_total(app, exam_records, marks):
    with app.app_context():
        exam = db.session.get(ClassExam, exam_records["exam_id"])
        assert exam is not None
        exam.total_marks = marks

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_duplicate_exam_recipient_is_rejected(app, exam_records):
    with app.app_context():
        db.session.add(
            ClassExamResult(
                exam_id=exam_records["exam_id"],
                student_id=exam_records["student_id"],
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        assert db.session.scalar(
            db.select(db.func.count())
            .select_from(ClassExamResult)
        ) == 1


def test_negative_obtained_marks_are_rejected(app, exam_records):
    with app.app_context():
        result = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )
        assert result is not None
        result.obtained_marks = Decimal("-0.50")

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_absent_student_cannot_also_have_marks(app, exam_records):
    with app.app_context():
        result = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )
        assert result is not None
        result.is_absent = True
        result.obtained_marks = Decimal("0")

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_decimal_marks_and_publication_persist(app, exam_records):
    with app.app_context():
        exam = db.session.get(ClassExam, exam_records["exam_id"])
        result = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )
        assert exam is not None
        assert result is not None

        result.obtained_marks = Decimal("22.50")
        exam.results_published_at = datetime.now(timezone.utc)
        db.session.commit()
        db.session.expire_all()

        saved_exam = db.session.get(
            ClassExam,
            exam_records["exam_id"],
        )
        saved_result = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )

        assert saved_exam is not None
        assert saved_exam.results_published_at is not None
        assert saved_result is not None
        assert saved_result.obtained_marks == Decimal("22.50")


def test_absent_status_persists_without_marks(app, exam_records):
    with app.app_context():
        result = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )
        assert result is not None
        result.is_absent = True
        db.session.commit()
        db.session.expire_all()

        saved = db.session.get(
            ClassExamResult,
            exam_records["result_id"],
        )
        assert saved is not None
        assert saved.is_absent is True
        assert saved.obtained_marks is None