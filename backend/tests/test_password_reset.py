from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from extensions import db
from models.password_reset_token import PasswordResetToken
from routes.password_reset import hash_reset_token
from services.email_service import EmailDeliveryError


EMAIL = "reset.student@example.com"
OLD_PASSWORD = "SecurePass123!"
NEW_PASSWORD = "Cedar river lantern 47"


def register_verified_account(client, *, name, email, password):
    with patch(
        "services.email_verification_service.send_email"
    ) as verification_email_mock:
        response = client.post(
            "/api/auth/register",
            json={
                "name": name,
                "email": email,
                "password": password,
                "academic_level": "hsc",
            },
        )

        assert response.status_code == 201
        verification_email_mock.assert_called_once()

        body = verification_email_mock.call_args.kwargs["body"]

    verification_link = next(
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    verification_token = parse_qs(
        urlsplit(verification_link).query
    )["token"][0]

    verification_response = client.post(
        "/api/auth/verify-email",
        json={"token": verification_token},
    )

    assert verification_response.status_code == 200

@pytest.fixture()
def reset_setup(client, app, monkeypatch):
    monkeypatch.setitem(
        app.config,
        "FRONTEND_URL",
        "http://localhost:5173",
    )
    monkeypatch.setitem(
        app.config,
        "PASSWORD_RESET_TOKEN_EXPIRES",
        timedelta(minutes=30),
    )

    register_verified_account(
        client,
        name="Reset Student",
        email=EMAIL,
        password=OLD_PASSWORD,
    )

    email_mock = Mock()
    monkeypatch.setattr(
        "routes.password_reset.send_email",
        email_mock,
    )

    return email_mock


def request_reset(client, email_mock):
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": EMAIL},
    )

    assert response.status_code == 200

    body = email_mock.call_args.kwargs["body"]
    link = next(
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/reset-password?"
        )
    )

    return parse_qs(urlsplit(link).query)["token"][0]


def submit_reset(client, token):
    return client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "password": NEW_PASSWORD,
        },
    )


def login_with(client, password):
    return client.post(
        "/api/auth/login",
        json={
            "email": EMAIL,
            "password": password,
        },
    )


def test_reset_request_saves_only_token_hash(
    client,
    app,
    reset_setup,
):
    raw_token = request_reset(client, reset_setup)

    reset_setup.assert_called_once()
    assert reset_setup.call_args.kwargs["recipient"] == EMAIL

    with app.app_context():
        token = db.session.scalar(
            db.select(PasswordResetToken)
        )

        assert token is not None
        assert token.token_hash == hash_reset_token(raw_token)
        assert token.token_hash != raw_token
        assert token.used_at is None

    assert raw_token not in client.post(
        "/api/auth/forgot-password",
        json={"email": "unknown@example.com"},
    ).get_data(as_text=True)


def test_unknown_email_returns_same_message(
    client,
    app,
    reset_setup,
):
    known_response = client.post(
        "/api/auth/forgot-password",
        json={"email": EMAIL},
    )

    reset_setup.reset_mock()

    unknown_response = client.post(
        "/api/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )

    assert known_response.status_code == 200
    assert unknown_response.status_code == 200
    assert known_response.get_json() == unknown_response.get_json()
    reset_setup.assert_not_called()

    with app.app_context():
        tokens = db.session.scalars(
            db.select(PasswordResetToken)
        ).all()

        assert len(tokens) == 1


def test_reset_changes_password_and_consumes_link(
    client,
    app,
    reset_setup,
):
    raw_token = request_reset(client, reset_setup)

    response = submit_reset(client, raw_token)

    assert response.status_code == 200
    assert login_with(client, OLD_PASSWORD).status_code == 401
    assert login_with(client, NEW_PASSWORD).status_code == 200

    with app.app_context():
        token = db.session.scalar(
            db.select(PasswordResetToken).where(
                PasswordResetToken.token_hash
                == hash_reset_token(raw_token)
            )
        )

        assert token is not None
        assert token.used_at is not None

    assert submit_reset(client, raw_token).status_code == 400


def test_expired_link_cannot_change_password(
    client,
    app,
    reset_setup,
):
    raw_token = request_reset(client, reset_setup)

    with app.app_context():
        token = db.session.scalar(
            db.select(PasswordResetToken)
        )

        assert token is not None

        token.expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        db.session.commit()

    assert submit_reset(client, raw_token).status_code == 400
    assert login_with(client, OLD_PASSWORD).status_code == 200


def test_new_request_invalidates_previous_link(
    client,
    reset_setup,
):
    first_token = request_reset(client, reset_setup)
    second_token = request_reset(client, reset_setup)

    assert first_token != second_token
    assert submit_reset(client, first_token).status_code == 400
    assert submit_reset(client, second_token).status_code == 200


def test_email_failure_preserves_previous_link(
    client,
    app,
    reset_setup,
):
    first_token = request_reset(client, reset_setup)

    reset_setup.side_effect = EmailDeliveryError(
        "Email sending failed"
    )

    response = client.post(
        "/api/auth/forgot-password",
        json={"email": EMAIL},
    )

    assert response.status_code == 503

    with app.app_context():
        tokens = db.session.scalars(
            db.select(PasswordResetToken)
        ).all()

        assert len(tokens) == 1
        assert tokens[0].used_at is None

    assert submit_reset(client, first_token).status_code == 200


def test_unknown_token_is_rejected(client, reset_setup):
    response = submit_reset(client, "unknown-reset-token")

    assert response.status_code == 400
    assert login_with(client, OLD_PASSWORD).status_code == 200


def test_weak_password_does_not_consume_link(
    client,
    reset_setup,
):
    raw_token = request_reset(client, reset_setup)

    response = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "password": "Password123!",
        },
    )

    assert response.status_code == 400
    assert login_with(client, OLD_PASSWORD).status_code == 200
    assert submit_reset(client, raw_token).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
    ],
)
def test_reset_routes_reject_non_object_json(client, path):
    response = client.post(path, json=[])

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Request body must be a JSON object"
    )


def test_password_reset_invalidates_old_login_token(
    client,
    app,
    monkeypatch,
):
    email = "token-reset@example.com"
    old_password = "SecurePass123!"
    new_password = "Cedar river lantern47"

    monkeypatch.setitem(
        app.config,
        "FRONTEND_URL",
        "http://localhost:5173",
    )
    monkeypatch.setitem(
        app.config,
        "PASSWORD_RESET_TOKEN_EXPIRES",
        timedelta(minutes=30),
    )

    register_verified_account(
        client,
        name="Token Reset Student",
        email=email,
        password=old_password,
    )

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": old_password,
        },
    )

    assert login_response.status_code == 200

    old_headers = {
        "Authorization": (
            f"Bearer {login_response.get_json()['access_token']}"
        ),
    }

    assert client.get(
        "/api/auth/me",
        headers=old_headers,
    ).status_code == 200

    mock_send_email = Mock()
    monkeypatch.setattr(
        "routes.password_reset.send_email",
        mock_send_email,
    )

    forgot_response = client.post(
        "/api/auth/forgot-password",
        json={"email": email},
    )

    assert forgot_response.status_code == 200
    mock_send_email.assert_called_once()

    email_body = mock_send_email.call_args.kwargs["body"]
    reset_link = next(
        line.strip()
        for line in email_body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/reset-password?"
        )
    )

    reset_token = parse_qs(
        urlsplit(reset_link).query
    )["token"][0]

    reset_response = client.post(
        "/api/auth/reset-password",
        json={
            "token": reset_token,
            "password": new_password,
        },
    )

    assert reset_response.status_code == 200

    # Password reset must revoke the previously valid JWT.
    assert client.get(
        "/api/auth/me",
        headers=old_headers,
    ).status_code == 401

    new_login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": new_password,
        },
    )

    assert new_login_response.status_code == 200

    new_headers = {
        "Authorization": (
            f"Bearer {new_login_response.get_json()['access_token']}"
        ),
    }

    assert client.get(
        "/api/auth/me",
        headers=new_headers,
    ).status_code == 200