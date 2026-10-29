from datetime import timedelta
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from extensions import db
from models.email_verification_token import EmailVerificationToken
from models.user import User
from services.email_service import EmailDeliveryError
from services.email_verification_service import (
    hash_verification_token,
    send_verification_email,
)


@pytest.fixture()
def verification_setup(app, monkeypatch):
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
            email="verify.student@example.com",
            password_hash="unused-test-hash",
        )
        db.session.add(user)
        db.session.commit()

        yield user, mock_send_email


def get_email_token(mock_send_email):
    body = mock_send_email.call_args.kwargs["body"]

    link = next(
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    return parse_qs(urlsplit(link).query)["token"][0]


def test_verification_service_stores_hash_and_sends_link(
    verification_setup,
):
    user, mock_send_email = verification_setup

    send_verification_email(user)
    db.session.commit()

    mock_send_email.assert_called_once()
    assert mock_send_email.call_args.kwargs["recipient"] == user.email

    raw_token = get_email_token(mock_send_email)

    token = db.session.scalar(
        db.select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        )
    )

    assert token is not None
    assert token.token_hash == hash_verification_token(raw_token)
    assert token.token_hash != raw_token
    assert len(token.token_hash) == 64
    assert token.used_at is None
    assert token.expires_at - token.created_at == pytest.approx(
        timedelta(hours=24),
        abs=timedelta(seconds=2),
    )
    assert user.is_email_verified is False


def test_new_verification_link_invalidates_previous_link(
    verification_setup,
):
    user, mock_send_email = verification_setup

    send_verification_email(user)
    db.session.commit()
    first_hash = hash_verification_token(
        get_email_token(mock_send_email)
    )

    send_verification_email(user)
    db.session.commit()
    second_hash = hash_verification_token(
        get_email_token(mock_send_email)
    )

    tokens = db.session.scalars(
        db.select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        )
    ).all()

    tokens_by_hash = {
        token.token_hash: token
        for token in tokens
    }

    assert len(tokens) == 2
    assert first_hash != second_hash
    assert tokens_by_hash[first_hash].used_at is not None
    assert tokens_by_hash[second_hash].used_at is None


def test_email_failure_rollback_preserves_previous_link(
    verification_setup,
):
    user, mock_send_email = verification_setup

    send_verification_email(user)
    db.session.commit()

    first_hash = hash_verification_token(
        get_email_token(mock_send_email)
    )

    mock_send_email.side_effect = EmailDeliveryError(
        "Test delivery failure"
    )

    with pytest.raises(EmailDeliveryError):
        send_verification_email(user)

    db.session.rollback()

    tokens = db.session.scalars(
        db.select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id
        )
    ).all()

    assert len(tokens) == 1
    assert tokens[0].token_hash == first_hash
    assert tokens[0].used_at is None


def test_verified_user_does_not_receive_verification_link(
    verification_setup,
):
    user, mock_send_email = verification_setup

    user.is_email_verified = True
    db.session.commit()

    with pytest.raises(ValueError, match="already verified"):
        send_verification_email(user)

    mock_send_email.assert_not_called()

    assert db.session.scalar(
        db.select(EmailVerificationToken.id)
    ) is None


@pytest.mark.parametrize(
    "frontend_url",
    [
        "",
        None,
        "not-a-url",
        "ftp://localhost:5173",
        "http://localhost:5173?unexpected=true",
        "http://localhost:5173#unexpected",
    ],
)
def test_invalid_frontend_url_does_not_send_or_save_token(
    app, verification_setup, frontend_url,
):
    user, mock_send_email = verification_setup
    app.config["FRONTEND_URL"] = frontend_url

    with pytest.raises(EmailDeliveryError):
        send_verification_email(user)

    mock_send_email.assert_not_called()

    assert db.session.scalar(
        db.select(EmailVerificationToken.id)
    ) is None