from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from extensions import db
from models.email_verification_token import EmailVerificationToken
from models.user import User
from services.email_service import EmailDeliveryError
from services.email_verification_service import hash_verification_token


@pytest.fixture()
def verification_user(app, monkeypatch):
    app.config.update(
        FRONTEND_URL="http://localhost:5173",
        EMAIL_VERIFICATION_TOKEN_EXPIRES=timedelta(hours=24),
    )

    mock_send_email = Mock()
    monkeypatch.setattr(
        "services.email_verification_service.send_email",
        mock_send_email,
    )

    with app.app_context():
        user = User(
            name="Verification Student",
            email="verification@example.com",
            password_hash="unused-test-hash",
        )
        db.session.add(user)
        db.session.commit()

        return user.id, user.email, mock_send_email


def request_verification(client, email):
    return client.post(
        "/api/auth/resend-verification",
        json={"email": email},
    )


def get_sent_token(mock_send_email):
    body = mock_send_email.call_args.kwargs["body"]

    link = next(
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    return parse_qs(urlsplit(link).query)["token"][0]


def verify_token(client, token):
    return client.post(
        "/api/auth/verify-email",
        json={"token": token},
    )


def test_resend_sends_link_and_verification_updates_user(
    client, app, verification_user,
):
    user_id, email, mock_send_email = verification_user

    response = request_verification(
        client, f"  {email.upper()}  "
    )

    assert response.status_code == 200
    mock_send_email.assert_called_once()

    token = get_sent_token(mock_send_email)

    with app.app_context():
        saved_token = db.session.scalar(
            db.select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id
            )
        )
        assert saved_token is not None
        assert saved_token.token_hash == hash_verification_token(token)
        assert saved_token.token_hash != token

    verify_response = verify_token(client, token)

    assert verify_response.status_code == 200

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        assert user.is_email_verified is True

        saved_token = db.session.scalar(
            db.select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id
            )
        )
        assert saved_token is not None
        assert saved_token.used_at is not None

    assert verify_token(client, token).status_code == 400


def test_unknown_and_verified_emails_receive_same_response(
    client, app, verification_user,
):
    user_id, email, mock_send_email = verification_user

    unknown_response = request_verification(
        client, "unknown@example.com"
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        user.is_email_verified = True
        db.session.commit()

    verified_response = request_verification(client, email)

    assert unknown_response.status_code == 200
    assert verified_response.status_code == 200
    assert unknown_response.get_json() == verified_response.get_json()
    mock_send_email.assert_not_called()


def test_expired_link_does_not_verify_user(
    client, app, verification_user,
):
    user_id, email, mock_send_email = verification_user

    assert request_verification(client, email).status_code == 200
    token = get_sent_token(mock_send_email)

    with app.app_context():
        saved_token = db.session.scalar(
            db.select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id
            )
        )
        assert saved_token is not None
        saved_token.expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        db.session.commit()

    assert verify_token(client, token).status_code == 400

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        assert user.is_email_verified is False


def test_resend_replaces_old_link(
    client, verification_user,
):
    _, email, mock_send_email = verification_user

    assert request_verification(client, email).status_code == 200
    first_token = get_sent_token(mock_send_email)

    assert request_verification(client, email).status_code == 200
    second_token = get_sent_token(mock_send_email)

    assert first_token != second_token
    assert verify_token(client, first_token).status_code == 400
    assert verify_token(client, second_token).status_code == 200


def test_email_failure_preserves_previous_link(
    client, verification_user,
):
    _, email, mock_send_email = verification_user

    assert request_verification(client, email).status_code == 200
    first_token = get_sent_token(mock_send_email)

    mock_send_email.side_effect = EmailDeliveryError(
        "Test delivery failure"
    )

    response = request_verification(client, email)

    assert response.status_code == 503
    assert verify_token(client, first_token).status_code == 200


def test_unknown_token_is_rejected(client):
    response = verify_token(client, "unknown-token")

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "This verification link is invalid or expired."
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"token": ""},
        {"token": None},
        {"token": 123},
        {"token": "x" * 257},
    ],
)
def test_verify_rejects_invalid_input(client, payload):
    response = client.post(
        "/api/auth/verify-email",
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Validation failed"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": ""},
        {"email": "not-an-email"},
        {"email": None},
        {"email": 123},
    ],
)
def test_resend_rejects_invalid_input(client, payload):
    response = client.post(
        "/api/auth/resend-verification",
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Validation failed"


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/verify-email",
        "/api/auth/resend-verification",
    ],
)
def test_verification_routes_reject_non_object_json(client, path):
    response = client.post(path, json=[])

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Request body must be a JSON object"
    )