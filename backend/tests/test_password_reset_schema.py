import pytest
from marshmallow import ValidationError

from schemas.password_reset_schema import (
    ForgotPasswordSchema,
    ResetPasswordSchema,
)


def test_forgot_password_accepts_valid_email():
    data = ForgotPasswordSchema().load({
        "email": "student@example.com",
    })

    assert data == {"email": "student@example.com"}


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
def test_forgot_password_rejects_invalid_email(payload):
    with pytest.raises(ValidationError) as error:
        ForgotPasswordSchema().load(payload)

    assert "email" in error.value.messages


def test_reset_password_accepts_valid_input():
    payload = {
        "token": "example-reset-token",
        "password": "Cedar river lantern 47",
    }

    data = ResetPasswordSchema().load(payload)

    assert data == payload


@pytest.mark.parametrize(
    "token",
    ["", None, 123, "a" * 257],
)
def test_reset_password_rejects_invalid_token(token):
    with pytest.raises(ValidationError) as error:
        ResetPasswordSchema().load({
            "token": token,
            "password": "Cedar river lantern 47",
        })

    assert "token" in error.value.messages


def test_reset_password_requires_token():
    with pytest.raises(ValidationError) as error:
        ResetPasswordSchema().load({
            "password": "Cedar river lantern 47",
        })

    assert "token" in error.value.messages


@pytest.mark.parametrize(
    "password",
    [
        "Ab3!",
        "Password123!",
        "aaaaaaaa",
        "        ",
        "a" * 129,
        None,
        123,
    ],
)
def test_reset_password_rejects_invalid_password(password):
    with pytest.raises(ValidationError) as error:
        ResetPasswordSchema().load({
            "token": "example-reset-token",
            "password": password,
        })

    assert "password" in error.value.messages


def test_reset_password_requires_password():
    with pytest.raises(ValidationError) as error:
        ResetPasswordSchema().load({
            "token": "example-reset-token",
        })

    assert "password" in error.value.messages


def test_reset_password_preserves_password_spaces():
    password = "  Cedar river lantern 47  "

    data = ResetPasswordSchema().load({
        "token": "example-reset-token",
        "password": password,
    })

    assert isinstance(data, dict)
    assert data["password"] == password


def test_reset_schema_does_not_serialize_secrets():
    output = ResetPasswordSchema().dump({
        "token": "example-reset-token",
        "password": "Cedar river lantern 47",
    })

    assert output == {}