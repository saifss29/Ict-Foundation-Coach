import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=4)

    SMTP_HOST = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

    MAIL_FROM_EMAIL = os.getenv("MAIL_FROM_EMAIL", "")
    MAIL_FROM_NAME = os.getenv(
        "MAIL_FROM_NAME",
        "ICT Foundation Coach",
    )

    FRONTEND_URL = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    ).rstrip("/")
    TOPIC_CACHE_ENABLED = (
        os.getenv("TOPIC_CACHE_ENABLED", "false").strip().lower()
        == "true"
    )

    TOPIC_CACHE_REDIS_URL = os.getenv(
        "TOPIC_CACHE_REDIS_URL",
        "redis://127.0.0.1:6379/1",
    )

    TOPIC_CACHE_TTL_SECONDS = 300
    PASSWORD_RESET_TOKEN_EXPIRES = timedelta(minutes=30)
    EMAIL_VERIFICATION_TOKEN_EXPIRES = timedelta(hours=24)
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://",
    )
    RATELIMIT_HEADERS_ENABLED = True
    TOPIC_CACHE_ENABLED = (
        os.getenv("TOPIC_CACHE_ENABLED", "false").strip().lower()
        == "true"
    )

    TOPIC_CACHE_REDIS_URL = os.getenv(
        "TOPIC_CACHE_REDIS_URL",
        "redis://127.0.0.1:6379/1",
    )

    TOPIC_CACHE_TTL_SECONDS = 300
