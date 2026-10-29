import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app


class EmailDeliveryError(Exception):
    """Raised when email configuration or delivery fails."""


def send_email(
    recipient: str,
    subject: str,
    body: str,
) -> None:
    config = current_app.config

    host = config.get("SMTP_HOST")
    port = config.get("SMTP_PORT")
    username = config.get("SMTP_USERNAME")
    password = config.get("SMTP_PASSWORD")
    sender_email = config.get("MAIL_FROM_EMAIL")
    sender_name = config.get(
        "MAIL_FROM_NAME",
        "ICT Foundation Coach",
    )

    required_values = (
        host,
        username,
        password,
        sender_email,
    )

    if any(
        not isinstance(value, str) or not value.strip()
        for value in required_values
    ):
        raise EmailDeliveryError(
            "Email configuration is incomplete."
        )

    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise EmailDeliveryError(
            "SMTP port configuration is invalid."
        )

    # Explicit checks also narrow the types for Pylance.
    if not isinstance(host, str):
        raise EmailDeliveryError("SMTP host is invalid.")

    if not isinstance(username, str):
        raise EmailDeliveryError("SMTP username is invalid.")

    if not isinstance(password, str):
        raise EmailDeliveryError("SMTP password is invalid.")

    if not isinstance(sender_email, str):
        raise EmailDeliveryError("Sender email is invalid.")

    if not isinstance(sender_name, str):
        raise EmailDeliveryError("Sender name is invalid.")

    message = EmailMessage()
    message["From"] = formataddr(
        (sender_name, sender_email)
    )
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(
            host,
            port,
            timeout=15,
        ) as smtp:
            smtp.ehlo()

            smtp.starttls(
                context=ssl.create_default_context()
            )

            smtp.ehlo()
            smtp.login(username, password)

            refused_recipients = smtp.send_message(
                message,
                from_addr=sender_email,
                to_addrs=[recipient],
            )

            if refused_recipients:
                raise EmailDeliveryError(
                    "Email recipient was rejected."
                )

    except (smtplib.SMTPException, OSError) as error:
        raise EmailDeliveryError(
            "Could not send email. Please try again later."
        ) from error