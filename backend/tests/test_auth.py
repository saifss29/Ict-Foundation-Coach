from urllib.parse import parse_qs, urlsplit

import pytest
from werkzeug.security import generate_password_hash

from extensions import db
from models.user import User


def register_user(client, academic_level="hsc"):
    return client.post(
        "/api/auth/register",
        json={
            "name": "Test Student",
            "email": "student@example.com",
            "password": "SecurePass123!",
            "academic_level": academic_level,
        },
    )


def verify_registration(client, verification_email_mock):
    verification_email_mock.assert_called()

    body = verification_email_mock.call_args.kwargs["body"]

    link = next(
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    token = parse_qs(urlsplit(link).query)["token"][0]

    response = client.post(
        "/api/auth/verify-email",
        json={"token": token},
    )

    assert response.status_code == 200


def register_and_login(client, verification_email_mock):
    register_response = register_user(client)
    assert register_response.status_code == 201

    verify_registration(client, verification_email_mock)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "student@example.com",
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    return login_response.get_json()["access_token"]


def test_user_can_register(client, verification_email_mock):
    response = register_user(client)

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Registration successful. "
        "Check your email to verify your account."
    )
    assert data["requires_email_verification"] is True
    assert data["user"]["name"] == "Test Student"
    assert data["user"]["email"] == "student@example.com"
    assert data["user"]["role"] == "student"
    assert data["user"]["is_email_verified"] is False
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

    verification_email_mock.assert_called_once()
    assert (
        verification_email_mock.call_args.kwargs["recipient"]
        == "student@example.com"
    )


def test_duplicate_email_cannot_register_twice(
    client, verification_email_mock
):
    first_response = register_user(client)
    assert first_response.status_code == 201

    second_response = register_user(client)

    assert second_response.status_code == 400
    assert second_response.get_json()["error"] == (
        "Registration could not be completed. Please check your details."
    )

    # Duplicate registration must not send another email.
    verification_email_mock.assert_called_once()


def test_user_can_login_with_correct_credentials(
    client, verification_email_mock
):
    register_response = register_user(client)
    assert register_response.status_code == 201

    verify_registration(client, verification_email_mock)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "student@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == "Login successful"
    assert data["user"]["email"] == "student@example.com"
    assert data["user"]["role"] == "student"
    assert data["user"]["is_email_verified"] is True
    assert data["access_token"]
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_login_fails_with_wrong_password(client):
    register_response = register_user(client)
    assert register_response.status_code == 201

    response = client.post(
        "/api/auth/login",
        json={
            "email": "student@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

    data = response.get_json()

    assert data["error"] == "Invalid email or password"
    assert "access_token" not in data
    assert "code" not in data


def test_logged_in_user_can_view_own_profile(
    client, verification_email_mock
):
    access_token = register_and_login(
        client, verification_email_mock
    )

    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["user"]["name"] == "Test Student"
    assert data["user"]["email"] == "student@example.com"
    assert data["user"]["role"] == "student"
    assert data["user"]["is_email_verified"] is True
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_logged_out_token_cannot_access_protected_route(
    client, verification_email_mock
):
    access_token = register_and_login(
        client, verification_email_mock
    )

    logout_response = client.post(
        "/api/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert logout_response.status_code == 200
    assert logout_response.get_json()["message"] == "Logout successful"

    profile_response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert profile_response.status_code == 401


def test_user_can_register_with_explicit_student_role(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test Student",
            "email": "student@example.com",
            "password": "SecurePass123!",
            "role": "student",
            "academic_level": "hsc",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["user"]["role"] == "student"
    assert response.get_json()["user"]["academic_level"] == "hsc"
    assert response.get_json()["user"]["is_email_verified"] is False


def test_teacher_role_is_preserved_in_login_and_profile(
    client, verification_email_mock
):
    register_response = client.post(
        "/api/auth/register",
        json={
            "name": "Test Teacher",
            "email": "teacher@example.com",
            "password": "SecurePass123!",
            "role": "teacher",
        },
    )

    assert register_response.status_code == 201
    assert register_response.get_json()["user"]["role"] == "teacher"
    assert register_response.get_json()["user"]["academic_level"] is None

    verify_registration(client, verification_email_mock)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "teacher@example.com",
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    login_data = login_response.get_json()

    assert login_data["user"]["role"] == "teacher"
    assert login_data["user"]["academic_level"] is None
    assert login_data["user"]["is_email_verified"] is True
    assert login_data["access_token"]

    profile_response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {login_data['access_token']}",
        },
    )

    assert profile_response.status_code == 200
    assert profile_response.get_json()["user"]["role"] == "teacher"
    assert profile_response.get_json()["user"]["academic_level"] is None


@pytest.mark.parametrize(
    "invalid_role",
    ["admin", "", None, 123],
)
def test_registration_rejects_invalid_role(client, invalid_role):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "invalid-role@example.com",
            "password": "SecurePass123!",
            "role": invalid_role,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Validation failed"
    assert "role" in data["messages"]

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "invalid-role@example.com",
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 401


@pytest.mark.parametrize(
    ("password", "expected_message"),
    [
        (
            "Password123!",
            "This password is too common. Choose a less predictable password.",
        ),
        (
            "PASSWORD123!",
            "This password is too common. Choose a less predictable password.",
        ),
        (
            "   password123!   ",
            "This password is too common. Choose a less predictable password.",
        ),
        (
            "aaaaaaaa",
            "Password cannot consist of one repeated character.",
        ),
        (
            "11111111",
            "Password cannot consist of one repeated character.",
        ),
        (
            "        ",
            "Password cannot contain only spaces.",
        ),
        (
            "Ab3!",
            "Password must be between 8 and 128 characters.",
        ),
        (
            "Ab3!" * 33,
            "Password must be between 8 and 128 characters.",
        ),
    ],
)
def test_registration_rejects_weak_or_invalid_password(
    client,
    password,
    expected_message,
):
    email = "password-test@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Password Test User",
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Validation failed"
    assert expected_message in data["messages"]["password"]

    # Rejected registration must not create an account.
    saved_user = db.session.scalar(
        db.select(User).where(User.email == email)
    )

    assert saved_user is None


def test_registration_preserves_password_spaces(
    client, verification_email_mock
):
    password = "  Cedar river lantern  "

    register_response = client.post(
        "/api/auth/register",
        json={
            "name": "Passphrase User",
            "email": "passphrase@example.com",
            "password": password,
            "academic_level": "hsc",
        },
    )

    assert register_response.status_code == 201

    verify_registration(client, verification_email_mock)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "passphrase@example.com",
            "password": password,
        },
    )

    assert login_response.status_code == 200

    # Password spaces must remain part of the actual password.
    trimmed_login_response = client.post(
        "/api/auth/login",
        json={
            "email": "passphrase@example.com",
            "password": password.strip(),
        },
    )

    assert trimmed_login_response.status_code == 401


def test_existing_account_can_login_with_previously_allowed_password(
    client,
):
    # Simulate an existing account marked verified by the migration.
    user = User(
        name="Existing Student",
        email="existing@example.com",
        password_hash=generate_password_hash("Password123!"),
        role="student",
    )
    user.is_email_verified = True

    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "existing@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["access_token"]


def test_unverified_account_cannot_login(client):
    register_response = register_user(client)
    assert register_response.status_code == 201

    response = client.post(
        "/api/auth/login",
        json={
            "email": "student@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 403

    data = response.get_json()

    assert data["error"] == "Verify your email before logging in."
    assert data["code"] == "EMAIL_NOT_VERIFIED"
    assert "access_token" not in data


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_student_level_is_saved_and_returned(
    client,
    verification_email_mock,
    academic_level,
):
    register_response = register_user(client, academic_level)

    assert register_response.status_code == 201

    registered_user = register_response.get_json()["user"]
    assert registered_user["academic_level"] == academic_level

    saved_user = db.session.get(User, registered_user["id"])
    assert saved_user is not None
    assert saved_user.academic_level == academic_level

    verify_registration(client, verification_email_mock)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "student@example.com",
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    login_data = login_response.get_json()
    assert login_data["user"]["academic_level"] == academic_level

    profile_response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {login_data['access_token']}",
        },
    )

    assert profile_response.status_code == 200
    assert (
        profile_response.get_json()["user"]["academic_level"]
        == academic_level
    )


@pytest.mark.parametrize(
    "invalid_level",
    ["", "SSC", "HSC", "college", None, 123, True, [], {}],
)
def test_student_registration_rejects_invalid_level(
    client,
    verification_email_mock,
    invalid_level,
):
    response = register_user(client, invalid_level)

    assert response.status_code == 400
    assert "academic_level" in response.get_json()["messages"]

    saved_user = db.session.scalar(
        db.select(User).where(User.email == "student@example.com")
    )

    assert saved_user is None
    verification_email_mock.assert_not_called()


def test_student_registration_requires_level(
    client,
    verification_email_mock,
):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test Student",
            "email": "missing-level@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 400
    assert "academic_level" in response.get_json()["messages"]

    saved_user = db.session.scalar(
        db.select(User).where(
            User.email == "missing-level@example.com"
        )
    )

    assert saved_user is None
    verification_email_mock.assert_not_called()


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_teacher_registration_rejects_student_level(
    client,
    verification_email_mock,
    academic_level,
):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test Teacher",
            "email": "teacher-level@example.com",
            "password": "SecurePass123!",
            "role": "teacher",
            "academic_level": academic_level,
        },
    )

    assert response.status_code == 400
    assert "academic_level" in response.get_json()["messages"]

    saved_user = db.session.scalar(
        db.select(User).where(
            User.email == "teacher-level@example.com"
        )
    )

    assert saved_user is None
    verification_email_mock.assert_not_called()


def login_level_test_user(client, role="student", academic_level=None):
    user = User(
        name="Level Test User",
        email="level-test@example.com",
        password_hash=generate_password_hash("SecurePass123!"),
        role=role,
        academic_level=academic_level,
    )
    user.is_email_verified = True

    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "level-test@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 200

    token = response.get_json()["access_token"]

    return user.id, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_existing_student_can_save_level(client, academic_level):
    user_id, headers = login_level_test_user(client)

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
        json={"academic_level": academic_level},
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["academic_level"] == academic_level

    db.session.expire_all()
    saved_user = db.session.get(User, user_id)

    assert saved_user is not None
    assert saved_user.academic_level == academic_level

    profile_response = client.get("/api/auth/me", headers=headers)

    assert profile_response.status_code == 200
    assert (
        profile_response.get_json()["user"]["academic_level"]
        == academic_level
    )


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_repeating_same_level_succeeds(client, academic_level):
    user_id, headers = login_level_test_user(
        client,
        academic_level=academic_level,
    )

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
        json={"academic_level": academic_level},
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["academic_level"] == academic_level

    db.session.expire_all()
    saved_user = db.session.get(User, user_id)

    assert saved_user is not None
    assert saved_user.academic_level == academic_level


@pytest.mark.parametrize(
    ("saved_level", "requested_level"),
    [("ssc", "hsc"), ("hsc", "ssc")],
)
def test_student_cannot_switch_saved_level(
    client,
    saved_level,
    requested_level,
):
    user_id, headers = login_level_test_user(
        client,
        academic_level=saved_level,
    )

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
        json={"academic_level": requested_level},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACADEMIC_LEVEL_ALREADY_SET"

    db.session.expire_all()
    saved_user = db.session.get(User, user_id)

    assert saved_user is not None
    assert saved_user.academic_level == saved_level


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"academic_level": ""},
        {"academic_level": "SSC"},
        {"academic_level": "college"},
        {"academic_level": None},
        {"academic_level": 123},
        {"academic_level": True},
        {"academic_level": []},
        {"academic_level": {}},
        {"academic_level": "ssc", "role": "teacher"},
        {"academic_level": "ssc", "user_id": 999},
        [],
        "ssc",
    ],
)
def test_level_selection_rejects_invalid_payload(client, payload):
    user_id, headers = login_level_test_user(client)

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 400

    db.session.expire_all()
    saved_user = db.session.get(User, user_id)

    assert saved_user is not None
    assert saved_user.academic_level is None
    assert saved_user.role == "student"


def test_teacher_cannot_select_student_level(client):
    user_id, headers = login_level_test_user(client, role="teacher")

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
        json={"academic_level": "ssc"},
    )

    assert response.status_code == 403

    db.session.expire_all()
    saved_user = db.session.get(User, user_id)

    assert saved_user is not None
    assert saved_user.academic_level is None


def test_level_selection_requires_authentication(client):
    response = client.patch(
        "/api/auth/me/academic-level",
        json={"academic_level": "ssc"},
    )

    assert response.status_code == 401


def test_level_selection_rejects_missing_body(client):
    user_id, headers = login_level_test_user(client)

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
    )

    assert response.status_code == 400

    db.session.expire_all()
    saved_user = db.session.get(User, user_id)

    assert saved_user is not None
    assert saved_user.academic_level is None


def test_selecting_level_updates_only_current_student(client):
    user_id, headers = login_level_test_user(client)

    other_user = User(
        name="Other Student",
        email="other-level-test@example.com",
        password_hash=generate_password_hash("SecurePass123!"),
        role="student",
    )

    db.session.add(other_user)
    db.session.commit()
    other_user_id = other_user.id

    response = client.patch(
        "/api/auth/me/academic-level",
        headers=headers,
        json={"academic_level": "ssc"},
    )

    assert response.status_code == 200

    db.session.expire_all()
    current_student = db.session.get(User, user_id)
    other_student = db.session.get(User, other_user_id)

    assert current_student is not None
    assert other_student is not None
    assert current_student.academic_level == "ssc"
    assert other_student.academic_level is None