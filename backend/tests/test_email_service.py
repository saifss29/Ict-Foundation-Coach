import smtplib
from unittest.mock import MagicMock

import pytest

from services.email_service import (
    EmailDeliveryError,
    send_email,
)


@pytest.fixture()
def email_app(app, monkeypatch):
    settings = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "test-smtp-user",
        "SMTP_PASSWORD": "test-smtp-key",
        "MAIL_FROM_EMAIL": "coach@example.com",
        "MAIL_FROM_NAME": "ICT Foundation Coach",
    }

    for key, value in settings.items():
        monkeypatch.setitem(app.config, key, value)

    return app


@pytest.fixture()
def smtp_mock(monkeypatch):
    factory = MagicMock()
    smtp = factory.return_value.__enter__.return_value
    smtp.send_message.return_value = {}

    monkeypatch.setattr(
        "services.email_service.smtplib.SMTP",
        factory,
    )

    return factory, smtp


def test_email_uses_tls_before_login(email_app, smtp_mock):
    factory, smtp = smtp_mock

    with email_app.app_context():
        send_email(
            "student@example.com",
            "Reset your password",
            "This is a test message.",
        )

    factory.assert_called_once_with(
        "smtp.example.com",
        587,
        timeout=15,
    )

    smtp.starttls.assert_called_once()

    smtp.login.assert_called_once_with(
        "test-smtp-user",
        "test-smtp-key",
    )

    method_names = [
        call[0]
        for call in smtp.method_calls
    ]

    assert method_names == [
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "send_message",
    ]

    tls_context = smtp.starttls.call_args.kwargs["context"]

    assert tls_context.check_hostname is True


def test_email_contains_correct_headers_and_body(
    email_app,
    smtp_mock,
):
    _, smtp = smtp_mock

    with email_app.app_context():
        send_email(
            "student@example.com",
            "Reset your password",
            "Follow your reset link.",
        )

    smtp.send_message.assert_called_once()

    message = smtp.send_message.call_args.args[0]

    assert str(message["From"]) == (
        "ICT Foundation Coach <coach@example.com>"
    )
    assert str(message["To"]) == "student@example.com"
    assert str(message["Subject"]) == "Reset your password"
    assert message.get_content().strip() == (
        "Follow your reset link."
    )

    assert smtp.send_message.call_args.kwargs == {
        "from_addr": "coach@example.com",
        "to_addrs": ["student@example.com"],
    }


@pytest.mark.parametrize(
    "setting",
    [
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "MAIL_FROM_EMAIL",
    ],
)
def test_missing_configuration_prevents_smtp_connection(
    email_app,
    smtp_mock,
    monkeypatch,
    setting,
):
    factory, _ = smtp_mock
    monkeypatch.setitem(email_app.config, setting, "")

    with email_app.app_context():
        with pytest.raises(
            EmailDeliveryError,
            match="Email configuration is incomplete",
        ):
            send_email(
                "student@example.com",
                "Test",
                "Test body",
            )

    factory.assert_not_called()


@pytest.mark.parametrize(
    "port",
    [None, "587", 0, 65536],
)
def test_invalid_port_prevents_smtp_connection(
    email_app,
    smtp_mock,
    monkeypatch,
    port,
):
    factory, _ = smtp_mock
    monkeypatch.setitem(email_app.config, "SMTP_PORT", port)

    with email_app.app_context():
        with pytest.raises(
            EmailDeliveryError,
            match="SMTP port configuration is invalid",
        ):
            send_email(
                "student@example.com",
                "Test",
                "Test body",
            )

    factory.assert_not_called()


def test_authentication_failure_prevents_sending(
    email_app,
    smtp_mock,
):
    _, smtp = smtp_mock

    smtp.login.side_effect = smtplib.SMTPAuthenticationError(
        535,
        b"Authentication failed",
    )

    with email_app.app_context():
        with pytest.raises(
            EmailDeliveryError,
            match="Could not send email",
        ):
            send_email(
                "student@example.com",
                "Test",
                "Test body",
            )

    smtp.send_message.assert_not_called()


def test_tls_failure_prevents_login(email_app, smtp_mock):
    _, smtp = smtp_mock

    smtp.starttls.side_effect = smtplib.SMTPNotSupportedError(
        "TLS unavailable"
    )

    with email_app.app_context():
        with pytest.raises(EmailDeliveryError):
            send_email(
                "student@example.com",
                "Test",
                "Test body",
            )

    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()


def test_connection_failure_is_handled(email_app, smtp_mock):
    factory, _ = smtp_mock
    factory.side_effect = OSError("Connection failed")

    with email_app.app_context():
        with pytest.raises(
            EmailDeliveryError,
            match="Could not send email",
        ):
            send_email(
                "student@example.com",
                "Test",
                "Test body",
            )


def test_rejected_recipient_is_handled(email_app, smtp_mock):
    _, smtp = smtp_mock

    smtp.send_message.return_value = {
        "student@example.com": (
            550,
            b"Recipient rejected",
        ),
    }

    with email_app.app_context():
        with pytest.raises(
            EmailDeliveryError,
            match="Email recipient was rejected",
        ):
            send_email(
                "student@example.com",
                "Test",
                "Test body",
            )