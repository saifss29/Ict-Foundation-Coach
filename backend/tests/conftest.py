import os
from datetime import timedelta
from unittest.mock import Mock

import pytest

# Tests use an in-memory database, not the real PostgreSQL database.
TEST_JWT_SECRET = "test-jwt-secret-key-with-at-least-32-bytes"

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = TEST_JWT_SECRET

from app import app as flask_app
from extensions import db, limiter


@pytest.fixture()
def app(monkeypatch):
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        JWT_SECRET_KEY=TEST_JWT_SECRET,
        FRONTEND_URL="http://localhost:5173",
        EMAIL_VERIFICATION_TOKEN_EXPIRES=timedelta(hours=24),
    )

    # Ordinary feature tests should not hit request limits.
    # monkeypatch restores the original value after the test.
    monkeypatch.setattr(limiter, "enabled", False)

    with flask_app.app_context():
        limiter.reset()
        db.drop_all()
        db.create_all()

        try:
            yield flask_app
        finally:
            db.session.remove()
            db.drop_all()
            limiter.reset()


@pytest.fixture()
def rate_limited_client(app, monkeypatch):
    # Dedicated rate-limit tests use the real limiter.
    monkeypatch.setattr(limiter, "enabled", True)

    with app.app_context():
        limiter.reset()

    return app.test_client()


@pytest.fixture(autouse=True)
def verification_email_mock(monkeypatch):
    mock_send_email = Mock()

    monkeypatch.setattr(
        "services.email_verification_service.send_email",
        mock_send_email,
    )

    return mock_send_email


@pytest.fixture()
def client(app):
    return app.test_client()