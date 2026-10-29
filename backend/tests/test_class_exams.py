from decimal import Decimal

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.class_exam import ClassExam
from models.class_exam_result import ClassExamResult
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.notification import Notification
from models.user import User


@pytest.fixture()
def exam_setup(app):
    with app.app_context():
        accounts = {}

        for key, role in (
            ("teacher", "teacher"),
            ("other_teacher", "teacher"),
            ("student", "student"),
            ("second_student", "student"),
            ("outsider", "student"),
        ):
            user = User(
                name=f"Exam {key}",
                email=f"{key}@exam-tests.example.com",
                password_hash="unused",
                role=role,
                academic_level="hsc" if role == "student" else None,
            )
            user.is_email_verified = True
            db.session.add(user)
            db.session.flush()

            token = create_access_token(
                identity=str(user.id),
                additional_claims={
                    "token_version": user.token_version,
                },
            )

            accounts[key] = {
                "id": user.id,
                "headers": {
                    "Authorization": f"Bearer {token}",
                },
            }

        classroom = Classroom(
            name="ICT Exam Class",
            teacher_id=accounts["teacher"]["id"],
            join_code="EXAM5678",
        )
        db.session.add(classroom)
        db.session.flush()

        for key in ("student", "second_student"):
            db.session.add(
                ClassMembership(
                    classroom_id=classroom.id,
                    student_id=accounts[key]["id"],
                )
            )

        db.session.commit()

        return {
            "classroom_id": classroom.id,
            **accounts,
        }


def exam_payload():
    return {
        "title": "1st Term ICT",
        "description": "Bring a pen.",
        "total_marks": 30,
        "starts_at": "2026-11-01T10:00:00+06:00",
        "ends_at": "2026-11-01T11:00:00+06:00",
        "timezone_name": "Asia/Dhaka",
    }


def create_exam(client, setup, **overrides):
    payload = exam_payload()
    payload.update(overrides)

    return client.post(
        f"/api/class-exams/classes/{setup['classroom_id']}",
        headers=setup["teacher"]["headers"],
        json=payload,
    )


def assert_nothing_saved(app):
    with app.app_context():
        for model in (ClassExam, ClassExamResult, Notification):
            count = db.session.scalar(
                db.select(db.func.count()).select_from(model)
            )
            assert count == 0


def test_teacher_creates_exam_and_notifies_only_recipients(
    app, client, exam_setup
):
    response = create_exam(client, exam_setup)

    assert response.status_code == 201

    data = response.get_json()

    assert data["recipient_count"] == 2
    assert data["exam"]["title"] == "1st Term ICT"
    assert data["exam"]["results_published_at"] is None
    assert Decimal(data["exam"]["total_marks"]) == Decimal("30")

    expected_students = {
        exam_setup["student"]["id"],
        exam_setup["second_student"]["id"],
    }

    with app.app_context():
        saved = db.session.get(ClassExam, data["exam"]["id"])

        assert saved is not None
        assert saved.classroom_id == exam_setup["classroom_id"]
        assert saved.total_marks == Decimal("30.00")

        results = db.session.scalars(
            db.select(ClassExamResult)
        ).all()

        assert len(results) == 2
        assert {item.student_id for item in results} == expected_students
        assert all(item.exam_id == saved.id for item in results)
        assert all(item.obtained_marks is None for item in results)

        notifications = db.session.scalars(
            db.select(Notification)
        ).all()

        assert len(notifications) == 2
        assert {
            item.user_id for item in notifications
        } == expected_students

        for notification in notifications:
            assert notification.notification_type == "class_exam_scheduled"
            assert notification.read_at is None
            assert "1st Term ICT" in notification.message
            assert "01 Nov 2026, 10:00 AM" in notification.message
            assert "Asia/Dhaka" in notification.message


def test_exam_creation_requires_login(app, client, exam_setup):
    response = client.post(
        f"/api/class-exams/classes/{exam_setup['classroom_id']}",
        json=exam_payload(),
    )

    assert response.status_code == 401
    assert_nothing_saved(app)


@pytest.mark.parametrize("account", ["student", "other_teacher"])
def test_unauthorized_account_cannot_create_exam(
    app, client, exam_setup, account
):
    response = client.post(
        f"/api/class-exams/classes/{exam_setup['classroom_id']}",
        headers=exam_setup[account]["headers"],
        json=exam_payload(),
    )

    assert response.status_code == 403
    assert_nothing_saved(app)


def test_missing_class_is_rejected(app, client, exam_setup):
    response = client.post(
        "/api/class-exams/classes/999999",
        headers=exam_setup["teacher"]["headers"],
        json=exam_payload(),
    )

    assert response.status_code == 404
    assert_nothing_saved(app)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("total_marks", 0),
        ("total_marks", True),
        ("ends_at", "2026-11-01T09:00:00+06:00"),
        ("starts_at", "2026-11-01T10:00:00"),
        ("timezone_name", "Wrong/Timezone"),
        ("student_ids", [123]),
        ("teacher_id", 123),
    ],
)
def test_invalid_exam_input_saves_nothing(
    app, client, exam_setup, field, value
):
    response = create_exam(
        client,
        exam_setup,
        **{field: value},
    )

    assert response.status_code == 400
    assert_nothing_saved(app)


def test_non_object_body_is_rejected(app, client, exam_setup):
    response = client.post(
        f"/api/class-exams/classes/{exam_setup['classroom_id']}",
        headers=exam_setup["teacher"]["headers"],
        json=["exam"],
    )

    assert response.status_code == 400
    assert_nothing_saved(app)


def test_empty_class_cannot_schedule_exam(app, client, exam_setup):
    with app.app_context():
        db.session.execute(db.delete(ClassMembership))
        db.session.commit()

    response = create_exam(client, exam_setup)

    assert response.status_code == 400
    assert_nothing_saved(app)


def test_later_join_does_not_change_saved_recipients(
    app, client, exam_setup
):
    response = create_exam(client, exam_setup)
    assert response.status_code == 201

    with app.app_context():
        db.session.add(
            ClassMembership(
                classroom_id=exam_setup["classroom_id"],
                student_id=exam_setup["outsider"]["id"],
            )
        )
        db.session.commit()

        recipients = db.session.scalars(
            db.select(ClassExamResult)
        ).all()

        assert len(recipients) == 2
        assert exam_setup["outsider"]["id"] not in {
            item.student_id for item in recipients
        }


def test_failed_commit_rolls_back_exam_and_notifications(
    app, client, exam_setup, monkeypatch
):
    def fail_commit():
        raise SQLAlchemyError("Test commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)

        response = create_exam(client, exam_setup)

    assert response.status_code == 500
    assert_nothing_saved(app)

def test_exam_list_requires_login(client):
    response = client.get("/api/class-exams")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("account", "expected_count"),
    [
        ("teacher", 1),
        ("student", 1),
        ("second_student", 1),
        ("other_teacher", 0),
        ("outsider", 0),
    ],
)
def test_exam_list_is_limited_to_owner_or_recipients(
    client, exam_setup, account, expected_count
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201

    response = client.get(
        "/api/class-exams",
        headers=exam_setup[account]["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()
    assert len(data["exams"]) == expected_count
    assert data["pagination"]["has_more"] is False

    if expected_count:
        exam = data["exams"][0]

        assert exam["id"] == created.get_json()["exam"]["id"]
        assert exam["classroom_name"] == "ICT Exam Class"
        assert exam["kind"] == "class_exam"
        assert exam["read_only"] is True
        assert "obtained_marks" not in exam
        assert "student_id" not in exam
        assert "results" not in exam


def test_student_can_still_see_assigned_exam_after_leaving(
    app, client, exam_setup
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201

    with app.app_context():
        memberships = db.metadata.tables["class_memberships"]

        db.session.execute(
            db.delete(memberships).where(
                memberships.c["classroom_id"]
                == exam_setup["classroom_id"],
                memberships.c["student_id"]
                == exam_setup["student"]["id"],
            )
        )
        db.session.commit()

    response = client.get(
        "/api/class-exams",
        headers=exam_setup["student"]["headers"],
    )

    assert response.status_code == 200
    assert len(response.get_json()["exams"]) == 1


def test_later_join_does_not_grant_exam_list_access(
    app, client, exam_setup
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201

    with app.app_context():
        db.session.add(
            ClassMembership(
                classroom_id=exam_setup["classroom_id"],
                student_id=exam_setup["outsider"]["id"],
            )
        )
        db.session.commit()

    response = client.get(
        "/api/class-exams",
        headers=exam_setup["outsider"]["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["exams"] == []


@pytest.mark.parametrize(
    ("start", "end", "expected_count"),
    [
        (
            "2026-11-01T10:30:00+06:00",
            "2026-11-01T12:00:00+06:00",
            1,
        ),
        (
            "2026-11-01T09:00:00+06:00",
            "2026-11-01T10:00:00+06:00",
            0,
        ),
        (
            "2026-11-01T11:00:00+06:00",
            "2026-11-01T12:00:00+06:00",
            0,
        ),
        (
            "2026-11-01T04:00:00+00:00",
            "2026-11-01T05:00:00+00:00",
            1,
        ),
    ],
)
def test_calendar_range_uses_overlap_and_timezone(
    client, exam_setup, start, end, expected_count
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201

    response = client.get(
        "/api/class-exams",
        headers=exam_setup["student"]["headers"],
        query_string={
            "starts_at": start,
            "ends_at": end,
        },
    )

    assert response.status_code == 200
    assert len(response.get_json()["exams"]) == expected_count


@pytest.mark.parametrize(
    "query",
    [
        {"starts_at": "2026-11-01T10:00:00+06:00"},
        {"ends_at": "2026-11-01T11:00:00+06:00"},
        {
            "starts_at": "2026-11-01T10:00:00",
            "ends_at": "2026-11-01T11:00:00",
        },
        {
            "starts_at": "bad-date",
            "ends_at": "2026-11-01T11:00:00+06:00",
        },
        {
            "starts_at": "2026-11-01T11:00:00+06:00",
            "ends_at": "2026-11-01T10:00:00+06:00",
        },
        {
            "starts_at": "2026-01-01T00:00:00+00:00",
            "ends_at": "2026-12-01T00:00:00+00:00",
        },
        {"page": "0"},
        {"page": "10001"},
        {"page": "abc"},
    ],
)
def test_exam_list_rejects_invalid_query(client, exam_setup, query):
    response = client.get(
        "/api/class-exams",
        headers=exam_setup["student"]["headers"],
        query_string=query,
    )

    assert response.status_code == 400


def test_exam_list_pagination_has_no_duplicate_records(
    app, client, exam_setup
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201

    with app.app_context():
        original = db.session.get(
            ClassExam,
            created.get_json()["exam"]["id"],
        )
        assert original is not None

        for index in range(20):
            exam = ClassExam(
                classroom_id=original.classroom_id,
                title=f"Extra Exam {index}",
                total_marks=30,
                starts_at=original.starts_at,
                ends_at=original.ends_at,
                timezone_name="Asia/Dhaka",
            )
            db.session.add(exam)
            db.session.flush()

            db.session.add(
                ClassExamResult(
                    exam_id=exam.id,
                    student_id=exam_setup["student"]["id"],
                )
            )

        db.session.commit()

    pages = []

    for page in (1, 2):
        response = client.get(
            "/api/class-exams",
            headers=exam_setup["student"]["headers"],
            query_string={"page": page},
        )

        assert response.status_code == 200
        pages.append(response.get_json())

    assert len(pages[0]["exams"]) == 20
    assert pages[0]["pagination"]["has_more"] is True
    assert len(pages[1]["exams"]) == 1
    assert pages[1]["pagination"]["has_more"] is False

    ids = [
        exam["id"]
        for page in pages
        for exam in page["exams"]
    ]

    assert len(ids) == len(set(ids)) == 21

def save_marks(client, setup, exam_id, entries, account="teacher"):
    return client.patch(
        f"/api/class-exams/{exam_id}/results",
        headers=setup[account]["headers"],
        json={"results": entries},
    )


def saved_marks(app, exam_id):
    with app.app_context():
        table = db.metadata.tables["class_exam_results"]

        results = db.session.scalars(
            db.select(ClassExamResult).where(
                table.c["exam_id"] == exam_id,
            )
        ).all()

        return {
            result.student_id: (
                result.obtained_marks,
                result.is_absent,
            )
            for result in results
        }


def test_teacher_saves_decimal_marks_and_absent_as_draft(
    app, client, exam_setup
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    response = save_marks(
        client,
        exam_setup,
        exam_id,
        [
            {
                "student_id": exam_setup["student"]["id"],
                "obtained_marks": "22.50",
            },
            {
                "student_id": exam_setup["second_student"]["id"],
                "is_absent": True,
            },
        ],
    )

    assert response.status_code == 200
    assert response.get_json()["updated_count"] == 2

    marks = saved_marks(app, exam_id)

    assert marks[exam_setup["student"]["id"]] == (
        Decimal("22.50"),
        False,
    )
    assert marks[exam_setup["second_student"]["id"]] == (
        None,
        True,
    )

    with app.app_context():
        exam = db.session.get(ClassExam, exam_id)
        assert exam is not None
        assert exam.results_published_at is None

        # Only the original schedule notifications exist.
        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 2


@pytest.mark.parametrize("marks", ["0", "30"])
def test_zero_and_full_marks_are_accepted(
    app, client, exam_setup, marks
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    response = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": marks,
        }],
    )

    assert response.status_code == 200
    assert saved_marks(app, exam_id)[exam_setup["student"]["id"]] == (
        Decimal(marks),
        False,
    )


def test_partial_save_preserves_other_student_marks(
    app, client, exam_setup
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    first = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": 20,
        }],
    )
    assert first.status_code == 200

    second = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["second_student"]["id"],
            "obtained_marks": 25,
        }],
    )
    assert second.status_code == 200

    marks = saved_marks(app, exam_id)
    assert marks[exam_setup["student"]["id"]] == (
        Decimal("20"),
        False,
    )
    assert marks[exam_setup["second_student"]["id"]] == (
        Decimal("25"),
        False,
    )


@pytest.mark.parametrize(
    "invalid_case",
    ["over_total", "outsider", "duplicate", "absent_with_marks"],
)
def test_invalid_batch_does_not_save_valid_entry(
    app, client, exam_setup, invalid_case
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    valid_entry = {
        "student_id": exam_setup["student"]["id"],
        "obtained_marks": 20,
    }
    invalid_entry = {
        "student_id": exam_setup["second_student"]["id"],
        "obtained_marks": 25,
    }

    if invalid_case == "over_total":
        invalid_entry["obtained_marks"] = 31
    elif invalid_case == "outsider":
        invalid_entry["student_id"] = exam_setup["outsider"]["id"]
    elif invalid_case == "duplicate":
        invalid_entry["student_id"] = exam_setup["student"]["id"]
    else:
        invalid_entry["is_absent"] = True

    response = save_marks(
        client,
        exam_setup,
        exam_id,
        [valid_entry, invalid_entry],
    )

    assert response.status_code == 400
    assert all(
        value == (None, False)
        for value in saved_marks(app, exam_id).values()
    )


@pytest.mark.parametrize("account", ["student", "other_teacher"])
def test_unauthorized_account_cannot_save_marks(
    app, client, exam_setup, account
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    response = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": 20,
        }],
        account=account,
    )

    assert response.status_code == 403
    assert all(
        value == (None, False)
        for value in saved_marks(app, exam_id).values()
    )


def test_marks_save_requires_login(client):
    response = client.patch(
        "/api/class-exams/unknown/results",
        json={"results": []},
    )

    assert response.status_code == 401


def test_missing_exam_cannot_receive_marks(client, exam_setup):
    response = save_marks(
        client,
        exam_setup,
        "unknown",
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": 20,
        }],
    )

    assert response.status_code == 404


def test_published_results_cannot_be_edited(
    app, client, exam_setup
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    with app.app_context():
        exam = db.session.get(ClassExam, exam_id)
        assert exam is not None
        exam.results_published_at = exam.starts_at
        db.session.commit()

    response = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": 20,
        }],
    )

    assert response.status_code == 409
    assert all(
        value == (None, False)
        for value in saved_marks(app, exam_id).values()
    )


def test_failed_marks_commit_preserves_previous_values(
    app, client, exam_setup, monkeypatch
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    original = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": 10,
        }],
    )
    assert original.status_code == 200

    def fail_commit():
        db.session.flush()
        raise SQLAlchemyError("Test marks commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)

        response = save_marks(
            client,
            exam_setup,
            exam_id,
            [{
                "student_id": exam_setup["student"]["id"],
                "obtained_marks": 25,
            }],
        )

    assert response.status_code == 500
    assert saved_marks(app, exam_id)[exam_setup["student"]["id"]] == (
        Decimal("10"),
        False,
    )

def prepare_completed_exam(client, setup):
    created = create_exam(client, setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    saved = save_marks(
        client,
        setup,
        exam_id,
        [
            {
                "student_id": setup["student"]["id"],
                "obtained_marks": 22,
            },
            {
                "student_id": setup["second_student"]["id"],
                "is_absent": True,
            },
        ],
    )
    assert saved.status_code == 200

    return exam_id


def publish_exam(client, setup, exam_id, account="teacher"):
    return client.post(
        f"/api/class-exams/{exam_id}/publish",
        headers=setup[account]["headers"],
        json={},
    )


def publication_notifications(app):
    with app.app_context():
        table = db.metadata.tables["notifications"]

        notifications = db.session.scalars(
            db.select(Notification).where(
                table.c["notification_type"]
                == "class_exam_results_published",
            )
        ).all()

        return [
            {
                "user_id": item.user_id,
                "message": item.message,
                "read_at": item.read_at,
            }
            for item in notifications
        ]


def test_teacher_publishes_completed_results_and_notifies_recipients(
    app, client, exam_setup
):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = publish_exam(client, exam_setup, exam_id)

    assert response.status_code == 200
    assert response.get_json()["recipient_count"] == 2
    assert response.get_json()["exam"]["results_published_at"]

    with app.app_context():
        exam = db.session.get(ClassExam, exam_id)
        assert exam is not None
        assert exam.results_published_at is not None

    notifications = publication_notifications(app)

    assert len(notifications) == 2
    assert {item["user_id"] for item in notifications} == {
        exam_setup["student"]["id"],
        exam_setup["second_student"]["id"],
    }

    for item in notifications:
        assert item["read_at"] is None
        assert "1st Term ICT" in item["message"]
        assert "22" not in item["message"]


def test_publish_retry_keeps_timestamp_and_avoids_duplicate_notifications(
    app, client, exam_setup
):
    exam_id = prepare_completed_exam(client, exam_setup)

    first = publish_exam(client, exam_setup, exam_id)
    second = publish_exam(client, exam_setup, exam_id)

    assert first.status_code == 200
    assert second.status_code == 200

    first_timestamp = first.get_json()["exam"]["results_published_at"]
    second_timestamp = second.get_json()["exam"]["results_published_at"]

    assert first_timestamp == second_timestamp
    assert len(publication_notifications(app)) == 2


@pytest.mark.parametrize("save_one_student", [False, True])
def test_incomplete_results_cannot_be_published(
    app, client, exam_setup, save_one_student
):
    created = create_exam(client, exam_setup)
    assert created.status_code == 201
    exam_id = created.get_json()["exam"]["id"]

    if save_one_student:
        saved = save_marks(
            client,
            exam_setup,
            exam_id,
            [{
                "student_id": exam_setup["student"]["id"],
                "obtained_marks": 20,
            }],
        )
        assert saved.status_code == 200

    response = publish_exam(client, exam_setup, exam_id)

    assert response.status_code == 409
    assert publication_notifications(app) == []

    with app.app_context():
        exam = db.session.get(ClassExam, exam_id)
        assert exam is not None
        assert exam.results_published_at is None


@pytest.mark.parametrize("account", ["student", "other_teacher"])
def test_unauthorized_account_cannot_publish(
    app, client, exam_setup, account
):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = publish_exam(
        client, exam_setup, exam_id, account=account
    )

    assert response.status_code == 403
    assert publication_notifications(app) == []


def test_publish_requires_login(client):
    response = client.post(
        "/api/class-exams/unknown/publish",
        json={},
    )

    assert response.status_code == 401


def test_publish_unknown_exam_returns_not_found(client, exam_setup):
    response = publish_exam(client, exam_setup, "unknown")

    assert response.status_code == 404


@pytest.mark.parametrize("body", [[], {"student_id": 123}])
def test_publish_rejects_nonempty_or_nonobject_body(
    app, client, exam_setup, body
):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = client.post(
        f"/api/class-exams/{exam_id}/publish",
        headers=exam_setup["teacher"]["headers"],
        json=body,
    )

    assert response.status_code == 400
    assert publication_notifications(app) == []


def test_published_exam_rejects_further_marks_save(
    app, client, exam_setup
):
    exam_id = prepare_completed_exam(client, exam_setup)
    published = publish_exam(client, exam_setup, exam_id)
    assert published.status_code == 200

    response = save_marks(
        client,
        exam_setup,
        exam_id,
        [{
            "student_id": exam_setup["student"]["id"],
            "obtained_marks": 30,
        }],
    )

    assert response.status_code == 409
    assert saved_marks(app, exam_id)[exam_setup["student"]["id"]] == (
        Decimal("22"),
        False,
    )


def test_failed_publish_rolls_back_timestamp_and_notifications(
    app, client, exam_setup, monkeypatch
):
    exam_id = prepare_completed_exam(client, exam_setup)

    def fail_commit():
        db.session.flush()
        raise SQLAlchemyError("Test publication failure")

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        response = publish_exam(client, exam_setup, exam_id)

    assert response.status_code == 500
    assert publication_notifications(app) == []

    with app.app_context():
        exam = db.session.get(ClassExam, exam_id)
        assert exam is not None
        assert exam.results_published_at is None

    # A later successful retry publishes normally.
    retry = publish_exam(client, exam_setup, exam_id)

    assert retry.status_code == 200
    assert len(publication_notifications(app)) == 2

def test_teacher_reads_saved_draft_results(client, exam_setup):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = client.get(
        f"/api/class-exams/{exam_id}/results",
        headers=exam_setup["teacher"]["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["recipient_count"] == 2
    assert data["exam"]["results_published_at"] is None
    assert data["classroom_name"] == "ICT Exam Class"

    results = {
        item["student_id"]: item
        for item in data["results"]
    }

    student = results[exam_setup["student"]["id"]]
    absent = results[exam_setup["second_student"]["id"]]

    assert Decimal(student["obtained_marks"]) == Decimal("22")
    assert student["is_absent"] is False
    assert student["student_name"]

    assert absent["obtained_marks"] is None
    assert absent["is_absent"] is True


@pytest.mark.parametrize("account", ["student", "other_teacher"])
def test_class_result_list_rejects_unauthorized_account(
    client, exam_setup, account
):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = client.get(
        f"/api/class-exams/{exam_id}/results",
        headers=exam_setup[account]["headers"],
    )

    assert response.status_code == 403
    assert "results" not in response.get_json()


def test_student_cannot_read_draft_marks(client, exam_setup):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = client.get(
        f"/api/class-exams/{exam_id}/my-result",
        headers=exam_setup["student"]["headers"],
    )

    assert response.status_code == 409

    data = response.get_json()

    assert data["code"] == "EXAM_RESULTS_NOT_PUBLISHED"
    assert "result" not in data
    assert "obtained_marks" not in data


@pytest.mark.parametrize(
    ("account", "expected_marks", "expected_absent"),
    [
        ("student", Decimal("22"), False),
        ("second_student", None, True),
    ],
)
def test_student_reads_only_own_published_result(
    client, exam_setup, account, expected_marks, expected_absent
):
    exam_id = prepare_completed_exam(client, exam_setup)
    published = publish_exam(client, exam_setup, exam_id)
    assert published.status_code == 200

    response = client.get(
        f"/api/class-exams/{exam_id}/my-result",
        headers=exam_setup[account]["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()
    result = data["result"]

    assert set(result) == {"obtained_marks", "is_absent"}
    assert result["is_absent"] is expected_absent

    if expected_marks is None:
        assert result["obtained_marks"] is None
    else:
        assert Decimal(result["obtained_marks"]) == expected_marks

    assert "results" not in data
    assert data["exam"]["results_published_at"]


def test_student_query_cannot_select_another_students_result(
    client, exam_setup
):
    exam_id = prepare_completed_exam(client, exam_setup)
    published = publish_exam(client, exam_setup, exam_id)
    assert published.status_code == 200

    response = client.get(
        f"/api/class-exams/{exam_id}/my-result",
        headers=exam_setup["second_student"]["headers"],
        query_string={
            "student_id": exam_setup["student"]["id"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["result"] == {
        "obtained_marks": None,
        "is_absent": True,
    }


def test_outsider_cannot_read_published_result(client, exam_setup):
    exam_id = prepare_completed_exam(client, exam_setup)
    published = publish_exam(client, exam_setup, exam_id)
    assert published.status_code == 200

    response = client.get(
        f"/api/class-exams/{exam_id}/my-result",
        headers=exam_setup["outsider"]["headers"],
    )

    assert response.status_code == 404
    assert "result" not in response.get_json()


def test_teacher_cannot_use_student_result_endpoint(client, exam_setup):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = client.get(
        f"/api/class-exams/{exam_id}/my-result",
        headers=exam_setup["teacher"]["headers"],
    )

    assert response.status_code == 403


@pytest.mark.parametrize("suffix", ["results", "my-result"])
def test_result_endpoints_require_login(client, suffix):
    response = client.get(
        f"/api/class-exams/unknown/{suffix}"
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("suffix", "account"),
    [
        ("results", "teacher"),
        ("my-result", "student"),
    ],
)
def test_result_endpoints_reject_unknown_exam(
    client, exam_setup, suffix, account
):
    response = client.get(
        f"/api/class-exams/unknown/{suffix}",
        headers=exam_setup[account]["headers"],
    )

    assert response.status_code == 404


@pytest.mark.parametrize("page", ["0", "10001", "abc"])
def test_teacher_results_reject_invalid_page(
    client, exam_setup, page
):
    exam_id = prepare_completed_exam(client, exam_setup)

    response = client.get(
        f"/api/class-exams/{exam_id}/results",
        headers=exam_setup["teacher"]["headers"],
        query_string={"page": page},
    )

    assert response.status_code == 400


def test_student_keeps_own_published_result_after_leaving(
    app, client, exam_setup
):
    exam_id = prepare_completed_exam(client, exam_setup)
    published = publish_exam(client, exam_setup, exam_id)
    assert published.status_code == 200

    with app.app_context():
        memberships = db.metadata.tables["class_memberships"]

        db.session.execute(
            db.delete(memberships).where(
                memberships.c["classroom_id"]
                == exam_setup["classroom_id"],
                memberships.c["student_id"]
                == exam_setup["student"]["id"],
            )
        )
        db.session.commit()

    response = client.get(
        f"/api/class-exams/{exam_id}/my-result",
        headers=exam_setup["student"]["headers"],
    )

    assert response.status_code == 200
    assert Decimal(
        response.get_json()["result"]["obtained_marks"]
    ) == Decimal("22")


def test_teacher_results_pagination(client, app, exam_setup):
    exam_id = prepare_completed_exam(client, exam_setup)

    with app.app_context():
        for index in range(19):
            student = User(
                name=f"Additional Student {index}",
                email=f"extra-{index}@exam-results.example.com",
                password_hash="unused",
                role="student",
                academic_level="hsc",
            )
            db.session.add(student)
            db.session.flush()

            db.session.add(
                ClassExamResult(
                    exam_id=exam_id,
                    student_id=student.id,
                )
            )

        db.session.commit()

    pages = []

    for page in (1, 2):
        response = client.get(
            f"/api/class-exams/{exam_id}/results",
            headers=exam_setup["teacher"]["headers"],
            query_string={"page": page},
        )
        assert response.status_code == 200
        pages.append(response.get_json())

    assert pages[0]["recipient_count"] == 21
    assert len(pages[0]["results"]) == 20
    assert pages[0]["pagination"]["has_more"] is True

    assert len(pages[1]["results"]) == 1
    assert pages[1]["pagination"]["has_more"] is False

    student_ids = [
        item["student_id"]
        for page in pages
        for item in page["results"]
    ]

    assert len(student_ids) == len(set(student_ids)) == 21