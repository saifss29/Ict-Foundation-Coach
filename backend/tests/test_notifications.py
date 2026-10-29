from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.notification import Notification
from models.teacher_feedback import TeacherFeedback
from models.user import User


def login_as(client, app, *, role, email):
    registration_data = {
        "name": f"Test {role.title()}",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = "hsc"

    register_response = client.post(
        "/api/auth/register",
        json=registration_data,
    )

    assert register_response.status_code == 201

    user_id = register_response.get_json()["user"]["id"]

    # These tests focus on notifications.
    # Email verification has its own test suite.
    with app.app_context():
        user = db.session.get(User, user_id)

        assert user is not None

        user.is_email_verified = True
        db.session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.get_json()["access_token"]

    return {
        "id": user_id,
        "headers": {
            "Authorization": f"Bearer {token}",
        },
    }

@pytest.fixture()
def notification_setup(client, app):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="notification.teacher@example.com",
    )

    student = login_as(
        client,
        app,
        role="student",
        email="notification.student@example.com",
    )

    class_response = client.post(
        "/api/classes",
        headers=teacher["headers"],
        json={"name": "Notification Test Class"},
    )

    assert class_response.status_code == 201

    classroom = class_response.get_json()["classroom"]

    join_response = client.post(
        "/api/classes/join",
        headers=student["headers"],
        json={"join_code": classroom["join_code"]},
    )

    assert join_response.status_code == 201

    return {
        "teacher": teacher,
        "student": student,
        "classroom": classroom,
        "feedback_path": (
            f"/api/feedback/classes/{classroom['id']}"
            f"/students/{student['id']}"
        ),
    }


def send_feedback(client, setup):
    response = client.post(
        setup["feedback_path"],
        headers=setup["teacher"]["headers"],
        json={"message": "Practice binary conversion again."},
    )

    assert response.status_code == 201

    return response.get_json()["feedback"]


def create_notification(app, user_id, *, read=False):
    with app.app_context():
        notification = Notification(
            user_id=user_id,
            notification_type="teacher_feedback",
            title="New teacher feedback",
            message="Your teacher sent feedback.",
        )

        if read:
            notification.read_at = datetime.now(timezone.utc)

        db.session.add(notification)
        db.session.commit()

        return notification.id


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/notifications"),
        ("GET", "/api/notifications/unread-count"),
        ("PATCH", "/api/notifications/1/read"),
    ],
)
def test_notification_routes_require_login(client, method, path):
    response = client.open(path, method=method)

    assert response.status_code == 401


def test_new_user_has_no_notifications(client, app):
    student = login_as(
        client,
        app,
        role="student",
        email="empty.notifications@example.com",
    )

    response = client.get(
        "/api/notifications",
        headers=student["headers"],
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "notifications": [],
        "unread_count": 0,
        "pagination": {
            "page": 1,
            "page_size": 20,
            "has_more": False,
        },
    }

    count_response = client.get(
        "/api/notifications/unread-count",
        headers=student["headers"],
    )

    assert count_response.status_code == 200
    assert count_response.get_json()["unread_count"] == 0


def test_feedback_creates_one_unread_notification(
    client,
    app,
    notification_setup,
):
    setup = notification_setup
    feedback = send_feedback(client, setup)

    with app.app_context():
        notifications = db.session.scalars(
            db.select(Notification)
        ).all()

        assert len(notifications) == 1

        notification = notifications[0]

        assert notification.user_id == setup["student"]["id"]
        assert notification.feedback_id == feedback["id"]
        assert notification.notification_type == "teacher_feedback"
        assert notification.title == "New teacher feedback"
        assert notification.read_at is None

    response = client.get(
        "/api/notifications",
        headers=setup["student"]["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["unread_count"] == 1
    assert len(data["notifications"]) == 1

    item = data["notifications"][0]

    assert item["feedback_id"] == feedback["id"]
    assert item["is_read"] is False
    assert item["read_at"] is None
    assert item["created_at"]
    assert "Test Teacher" in item["message"]


def test_user_cannot_see_another_users_notifications(
    client,
    app,
    notification_setup,
):
    setup = notification_setup
    send_feedback(client, setup)

    outsider = login_as(
        client,
        app,
        role="student",
        email="notification.outsider@example.com",
    )

    for user in (outsider, setup["teacher"]):
        response = client.get(
            "/api/notifications",
            headers=user["headers"],
        )

        assert response.status_code == 200
        assert response.get_json()["notifications"] == []
        assert response.get_json()["unread_count"] == 0

        count_response = client.get(
            "/api/notifications/unread-count",
            headers=user["headers"],
        )

        assert count_response.status_code == 200
        assert count_response.get_json()["unread_count"] == 0


def test_owner_can_mark_notification_read(client, app):
    student = login_as(
        client,
        app,
        role="student",
        email="mark.read@example.com",
    )

    notification_id = create_notification(app, student["id"])

    response = client.patch(
        f"/api/notifications/{notification_id}/read",
        headers=student["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["notification"]["id"] == notification_id
    assert data["notification"]["is_read"] is True
    assert data["notification"]["read_at"]
    assert data["unread_count"] == 0

    with app.app_context():
        notification = db.session.get(
            Notification,
            notification_id,
        )

        assert notification is not None
        assert notification.read_at is not None

    list_response = client.get(
        "/api/notifications",
        headers=student["headers"],
    )

    assert list_response.get_json()["notifications"][0]["is_read"] is True


def test_marking_read_twice_preserves_original_timestamp(client, app):
    student = login_as(
        client,
        app,
        role="student",
        email="read.twice@example.com",
    )

    notification_id = create_notification(app, student["id"])
    path = f"/api/notifications/{notification_id}/read"

    first_response = client.patch(
        path,
        headers=student["headers"],
    )
    second_response = client.patch(
        path,
        headers=student["headers"],
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_data = first_response.get_json()
    second_data = second_response.get_json()

    assert (
        first_data["notification"]["read_at"]
        == second_data["notification"]["read_at"]
    )
    assert second_data["unread_count"] == 0


def test_user_cannot_mark_another_users_notification_read(client, app):
    owner = login_as(
        client,
        app,
        role="student",
        email="notification.owner@example.com",
    )
    outsider = login_as(
        client,
        app,
        role="student",
        email="notification.other@example.com",
    )

    notification_id = create_notification(app, owner["id"])

    response = client.patch(
        f"/api/notifications/{notification_id}/read",
        headers=outsider["headers"],
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Notification not found"

    with app.app_context():
        notification = db.session.get(
            Notification,
            notification_id,
        )

        assert notification is not None
        assert notification.read_at is None


def test_unknown_notification_is_rejected(client, app):
    student = login_as(
        client,
        app,
        role="student",
        email="unknown.notification@example.com",
    )

    response = client.patch(
        "/api/notifications/999999/read",
        headers=student["headers"],
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Notification not found"


def test_unread_count_excludes_read_notifications(client, app):
    student = login_as(
        client,
        app,
        role="student",
        email="notification.count@example.com",
    )

    create_notification(app, student["id"])
    create_notification(app, student["id"])
    create_notification(app, student["id"], read=True)

    response = client.get(
        "/api/notifications/unread-count",
        headers=student["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["unread_count"] == 2


@pytest.mark.parametrize("page", ["0", "-1", "abc", "10001"])
def test_notification_list_rejects_invalid_page(client, app, page):
    student = login_as(
        client,
        app,
        role="student",
        email="notification.page@example.com",
    )

    response = client.get(
        f"/api/notifications?page={page}",
        headers=student["headers"],
    )

    assert response.status_code == 400


def test_notification_list_is_paginated_newest_first(client, app):
    student = login_as(
        client,
        app,
        role="student",
        email="notification.pagination@example.com",
    )

    with app.app_context():
        start_time = datetime.now(timezone.utc)
        saved = []

        for index in range(21):
            notification = Notification(
                user_id=student["id"],
                notification_type="teacher_feedback",
                title=f"Feedback {index}",
                message=f"Practice advice {index}",
            )
            notification.created_at = start_time + timedelta(
                seconds=index
            )

            db.session.add(notification)
            saved.append(notification)

        db.session.commit()

        expected_ids = [
            notification.id
            for notification in reversed(saved)
        ]

    first_response = client.get(
        "/api/notifications?page=1",
        headers=student["headers"],
    )
    second_response = client.get(
        "/api/notifications?page=2",
        headers=student["headers"],
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_data = first_response.get_json()
    second_data = second_response.get_json()

    assert [
        item["id"] for item in first_data["notifications"]
    ] == expected_ids[:20]
    assert [
        item["id"] for item in second_data["notifications"]
    ] == expected_ids[20:]

    assert first_data["pagination"]["has_more"] is True
    assert second_data["pagination"]["has_more"] is False

    # The count covers all unread notifications, not just this page.
    assert first_data["unread_count"] == 21
    assert second_data["unread_count"] == 21


def test_notification_failure_rolls_back_feedback(
    client,
    app,
    monkeypatch,
    notification_setup,
):
    setup = notification_setup

    # Fail after feedback.flush(), before the final commit.
    monkeypatch.setattr(
        "routes.teacher_feedback.Notification",
        Mock(side_effect=SQLAlchemyError("Notification creation failed")),
    )

    response = client.post(
        setup["feedback_path"],
        headers=setup["teacher"]["headers"],
        json={"message": "This feedback must not be saved."},
    )

    assert response.status_code == 500

    with app.app_context():
        feedback = db.session.scalars(
            db.select(TeacherFeedback)
        ).all()
        notifications = db.session.scalars(
            db.select(Notification)
        ).all()

        assert feedback == []
        assert notifications == []


def test_invalid_feedback_does_not_create_notification(
    client,
    app,
    notification_setup,
):
    setup = notification_setup

    response = client.post(
        setup["feedback_path"],
        headers=setup["teacher"]["headers"],
        json={"message": "   "},
    )

    assert response.status_code == 400

    with app.app_context():
        notifications = db.session.scalars(
            db.select(Notification)
        ).all()

        assert notifications == []