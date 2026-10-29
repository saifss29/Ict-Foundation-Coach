from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from extensions import db
from models.user import User
from services.email_service import EmailDeliveryError
from services.parent_report_token_service import (
    create_parent_unsubscribe_token,
)


BASE_URL = "/api/parent-reports"


@pytest.fixture()
def parent_mail(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("routes.parent_reports.send_email", mock)
    return mock


@pytest.fixture()
def student_account(client, app):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Report Student",
            "email": "parent-report-student@example.com",
            "password": "SecurePass123!",
            "role": "student",
            "academic_level": "ssc",
        },
    )
    assert response.status_code == 201

    student_id = response.get_json()["user"]["id"]

    with app.app_context():
        student = db.session.get(User, student_id)
        assert student is not None
        student.is_email_verified = True
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "parent-report-student@example.com",
            "password": "SecurePass123!",
        },
    )
    assert response.status_code == 200

    return {
        "id": student_id,
        "headers": {
            "Authorization": (
                f"Bearer {response.get_json()['access_token']}"
            )
        },
    }


def request_link(client, student_account, parent_mail, email="parent@example.com"):
    response = client.post(
        f"{BASE_URL}/request-verification",
        headers=student_account["headers"],
        json={"parent_email": email},
    )
    assert response.status_code == 200

    body = parent_mail.call_args.kwargs["body"]

    link = next(
        line.strip()
        for line in body.splitlines()
        if "/parent-reports/verify?" in line
    )

    return parse_qs(urlsplit(link).query)["token"][0]


def preferences(client, student_account):
    response = client.get(
        BASE_URL,
        headers=student_account["headers"],
    )
    assert response.status_code == 200
    return response.get_json()


def test_preferences_require_authentication(client):
    assert client.get(BASE_URL).status_code == 401
    assert client.delete(BASE_URL).status_code == 401


def test_parent_verification_requires_consent_and_is_single_use(
    client, student_account, parent_mail
):
    token = request_link(client, student_account, parent_mail)

    assert preferences(client, student_account) == {
        "parent_email": "parent@example.com",
        "verified": False,
        "enabled": False,
    }

    response = client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": False},
    )
    assert response.status_code == 400
    assert preferences(client, student_account)["enabled"] is False

    response = client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    )
    assert response.status_code == 200
    assert preferences(client, student_account)["enabled"] is True
    assert preferences(client, student_account)["verified"] is True

    response = client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    )
    assert response.status_code == 400


def test_parent_email_change_invalidates_previous_link(
    client, student_account, parent_mail
):
    old_token = request_link(client, student_account, parent_mail)
    new_token = request_link(
        client, student_account, parent_mail, "other-parent@example.com"
    )

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": old_token, "consent": True},
    ).status_code == 400

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": new_token, "consent": True},
    ).status_code == 200

    assert preferences(client, student_account)["parent_email"] == (
        "other-parent@example.com"
    )


def test_student_cannot_disable_parent_reports(
    client, student_account, parent_mail
):
    token = request_link(client, student_account, parent_mail)

    response = client.delete(
        BASE_URL,
        headers=student_account["headers"],
    )
    assert response.status_code == 403

    # The blocked request must not invalidate the parent's link.
    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    ).status_code == 200

    response = client.delete(
        BASE_URL,
        headers=student_account["headers"],
    )
    assert response.status_code == 403

    assert preferences(client, student_account) == {
        "parent_email": "parent@example.com",
        "verified": True,
        "enabled": True,
    }


def test_student_cannot_change_or_resend_verified_parent_email(
    client, student_account, parent_mail
):
    token = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    ).status_code == 200

    parent_mail.reset_mock()

    for email in ("parent@example.com", "other-parent@example.com"):
        response = client.post(
            f"{BASE_URL}/request-verification",
            headers=student_account["headers"],
            json={"parent_email": email},
        )
        assert response.status_code == 403

    parent_mail.assert_not_called()

    assert preferences(client, student_account) == {
        "parent_email": "parent@example.com",
        "verified": True,
        "enabled": True,
    }

def test_expired_parent_link_is_rejected(
    client, app, student_account, parent_mail
):
    token = request_link(client, student_account, parent_mail)

    with app.app_context():
        tokens = db.metadata.tables["parent_email_verification_tokens"]
        now = datetime.now(timezone.utc)

        db.session.execute(
            tokens.update()
            .where(tokens.c.student_id == student_account["id"])
            .values(
                created_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1),
            )
        )
        db.session.commit()

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    ).status_code == 400

    assert preferences(client, student_account)["enabled"] is False


def test_mail_failure_rolls_back_parent_preferences(
    client, app, student_account, parent_mail
):
    parent_mail.side_effect = EmailDeliveryError("Test delivery failure")

    response = client.post(
        f"{BASE_URL}/request-verification",
        headers=student_account["headers"],
        json={"parent_email": "parent@example.com"},
    )
    assert response.status_code == 502
    assert preferences(client, student_account)["parent_email"] is None

    with app.app_context():
        tokens = db.metadata.tables["parent_email_verification_tokens"]
        saved_token = db.session.execute(
            select(tokens.c.id)
            .where(tokens.c.student_id == student_account["id"])
        ).first()

        assert saved_token is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"parent_email": "invalid"},
        {"parent_email": None},
        {"parent_email": "parent@example.com", "student_id": 999},
    ],
)
def test_invalid_parent_email_request_is_rejected(
    client, student_account, parent_mail, payload
):
    response = client.post(
        f"{BASE_URL}/request-verification",
        headers=student_account["headers"],
        json=payload,
    )

    assert response.status_code == 400
    parent_mail.assert_not_called()

def unsubscribe_token(app, student_id):
    with app.app_context():
        users = db.metadata.tables["users"]

        student = db.session.execute(
            select(users).where(users.c.id == student_id)
        ).mappings().one()

        return create_parent_unsubscribe_token(
            student_id=student_id,
            parent_email=student["parent_email"],
            verified_at=student["parent_email_verified_at"],
        )


def test_parent_can_unsubscribe_without_login(
    client, app, student_account, parent_mail
):
    verification = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": verification, "consent": True},
    ).status_code == 200

    token = unsubscribe_token(app, student_account["id"])

    # Opening a link alone cannot stop reports.
    assert client.get(
        f"{BASE_URL}/unsubscribe",
        query_string={"token": token},
    ).status_code == 405

    assert preferences(client, student_account)["enabled"] is True

    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": token, "confirm": False},
    ).status_code == 400

    response = client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": token, "confirm": True},
    )
    assert response.status_code == 200

    assert preferences(client, student_account) == {
        "parent_email": "parent@example.com",
        "verified": True,
        "enabled": False,
    }

    # Repeating unsubscribe is harmless.
    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": token, "confirm": True},
    ).status_code == 200


def test_modified_unsubscribe_token_is_rejected(
    client, app, student_account, parent_mail
):
    verification = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": verification, "consent": True},
    ).status_code == 200

    token = unsubscribe_token(app, student_account["id"])

    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": "changed-" + token, "confirm": True},
    ).status_code == 400

    assert preferences(client, student_account)["enabled"] is True


def test_old_unsubscribe_token_cannot_control_new_parent_email(
    client, app, student_account, parent_mail
):
    verification = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": verification, "consent": True},
    ).status_code == 200

    token = unsubscribe_token(app, student_account["id"])

    # Simulate an authorised email change outside the student API.
    with app.app_context():
        users = db.metadata.tables["users"]

        db.session.execute(
            users.update()
            .where(users.c.id == student_account["id"])
            .values(parent_email="new-parent@example.com")
        )
        db.session.commit()

    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": token, "confirm": True},
    ).status_code == 400

    assert preferences(client, student_account)["enabled"] is True

def create_teacher_account(client, app, email):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Parent Report Teacher",
            "email": email,
            "password": "SecurePass123!",
            "role": "teacher",
        },
    )
    assert response.status_code == 201

    teacher_id = response.get_json()["user"]["id"]

    with app.app_context():
        users = db.metadata.tables["users"]
        db.session.execute(
            users.update()
            .where(users.c.id == teacher_id)
            .values(is_email_verified=True)
        )
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert response.status_code == 200

    return {
        "id": teacher_id,
        "headers": {
            "Authorization": (
                f"Bearer {response.get_json()['access_token']}"
            )
        },
    }


@pytest.fixture()
def correction_setup(client, app, student_account):
    teacher = create_teacher_account(
        client, app, "correction-owner@example.com"
    )
    other_teacher = create_teacher_account(
        client, app, "correction-other@example.com"
    )

    with app.app_context():
        classes = db.metadata.tables["classrooms"]
        memberships = db.metadata.tables["class_memberships"]

        classroom_id = db.session.execute(
            classes.insert().values(
                name="Correction Class",
                teacher_id=teacher["id"],
                join_code="CORRECT01",
            ).returning(classes.c.id)
        ).scalar_one()

        db.session.execute(
            memberships.insert().values(
                classroom_id=classroom_id,
                student_id=student_account["id"],
            )
        )
        db.session.commit()

    return {
        "teacher": teacher,
        "other_teacher": other_teacher,
        "classroom_id": classroom_id,
    }


def correction_url(setup, student_id):
    return (
        f"{BASE_URL}/classes/{setup['classroom_id']}"
        f"/students/{student_id}/email"
    )


def test_teacher_corrects_email_and_requires_new_parent_consent(
    client, app, student_account, parent_mail, correction_setup
):
    old_verification = request_link(
        client, student_account, parent_mail
    )
    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": old_verification, "consent": True},
    ).status_code == 200

    old_unsubscribe = unsubscribe_token(app, student_account["id"])

    response = client.post(
        correction_url(correction_setup, student_account["id"]),
        headers=correction_setup["teacher"]["headers"],
        json={"parent_email": "new-parent@example.com"},
    )
    assert response.status_code == 200

    assert preferences(client, student_account) == {
        "parent_email": "new-parent@example.com",
        "verified": False,
        "enabled": False,
    }

    mail = parent_mail.call_args.kwargs
    assert mail["recipient"] == "new-parent@example.com"

    link = next(
        line.strip()
        for line in mail["body"].splitlines()
        if "/parent-reports/verify?" in line
    )
    token = parse_qs(urlsplit(link).query)["token"][0]

    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": old_unsubscribe, "confirm": True},
    ).status_code == 400

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    ).status_code == 200

    assert preferences(client, student_account)["enabled"] is True


@pytest.mark.parametrize(
    ("actor", "expected_status"),
    [
        ("student", 403),
        ("other_teacher", 404),
    ],
)
def test_parent_correction_rejects_unauthorised_actor(
    client,
    student_account,
    parent_mail,
    correction_setup,
    actor,
    expected_status,
):
    headers = (
        student_account["headers"]
        if actor == "student"
        else correction_setup["other_teacher"]["headers"]
    )

    response = client.post(
        correction_url(correction_setup, student_account["id"]),
        headers=headers,
        json={"parent_email": "new-parent@example.com"},
    )

    assert response.status_code == expected_status
    parent_mail.assert_not_called()


def test_teacher_cannot_correct_former_members_parent_email(
    client, app, student_account, parent_mail, correction_setup
):
    with app.app_context():
        memberships = db.metadata.tables["class_memberships"]
        db.session.execute(
            memberships.delete().where(
                memberships.c.classroom_id
                == correction_setup["classroom_id"],
                memberships.c.student_id == student_account["id"],
            )
        )
        db.session.commit()

    response = client.post(
        correction_url(correction_setup, student_account["id"]),
        headers=correction_setup["teacher"]["headers"],
        json={"parent_email": "new-parent@example.com"},
    )

    assert response.status_code == 404
    parent_mail.assert_not_called()


def test_failed_teacher_correction_preserves_verified_parent(
    client, student_account, parent_mail, correction_setup
):
    token = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": token, "consent": True},
    ).status_code == 200

    parent_mail.side_effect = EmailDeliveryError("Test failure")

    response = client.post(
        correction_url(correction_setup, student_account["id"]),
        headers=correction_setup["teacher"]["headers"],
        json={"parent_email": "new-parent@example.com"},
    )

    assert response.status_code == 502

    assert preferences(client, student_account) == {
        "parent_email": "parent@example.com",
        "verified": True,
        "enabled": True,
    }

def test_parent_can_resume_reports_after_unsubscribe(
    client, app, student_account, parent_mail
):
    verification = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": verification, "consent": True},
    ).status_code == 200

    token = unsubscribe_token(app, student_account["id"])

    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": token, "confirm": True},
    ).status_code == 200

    assert client.post(
        f"{BASE_URL}/resume",
        json={"token": token, "confirm": False},
    ).status_code == 400
    assert preferences(client, student_account)["enabled"] is False

    assert client.post(
        f"{BASE_URL}/resume",
        json={"token": token, "confirm": True},
    ).status_code == 200
    assert preferences(client, student_account)["enabled"] is True


def test_modified_parent_link_cannot_resume_reports(
    client, app, student_account, parent_mail
):
    verification = request_link(client, student_account, parent_mail)

    assert client.post(
        f"{BASE_URL}/verify",
        json={"token": verification, "consent": True},
    ).status_code == 200

    token = unsubscribe_token(app, student_account["id"])

    assert client.post(
        f"{BASE_URL}/unsubscribe",
        json={"token": token, "confirm": True},
    ).status_code == 200

    assert client.post(
        f"{BASE_URL}/resume",
        json={"token": "changed-" + token, "confirm": True},
    ).status_code == 400
    assert preferences(client, student_account)["enabled"] is False