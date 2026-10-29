import pytest


RATE_LIMIT_ERROR = (
    "Too many requests. Please wait and try again."
)


def test_login_blocks_sixth_request(rate_limited_client):
    for _ in range(5):
        response = rate_limited_client.post(
            "/api/auth/login",
            json={
                "email": "unknown@example.com",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 401

    response = rate_limited_client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 429
    assert response.get_json()["error"] == RATE_LIMIT_ERROR


def test_registration_blocks_eleventh_request(
    rate_limited_client,
    verification_email_mock,
):
    # Invalid input counts without creating accounts.
    for _ in range(10):
        response = rate_limited_client.post(
            "/api/auth/register",
            json={},
        )

        assert response.status_code == 400

    response = rate_limited_client.post(
        "/api/auth/register",
        json={},
    )

    assert response.status_code == 429
    assert response.get_json()["error"] == RATE_LIMIT_ERROR

    verification_email_mock.assert_not_called()


def test_login_limit_is_separate_for_each_ip(rate_limited_client):
    for _ in range(5):
        response = rate_limited_client.post(
            "/api/auth/login",
            json={
                "email": "unknown@example.com",
                "password": "SecurePass123!",
            },
            environ_overrides={"REMOTE_ADDR": "192.0.2.1"},
        )

        assert response.status_code == 401

    blocked_response = rate_limited_client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "SecurePass123!",
        },
        environ_overrides={"REMOTE_ADDR": "192.0.2.1"},
    )

    assert blocked_response.status_code == 429

    other_ip_response = rate_limited_client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "SecurePass123!",
        },
        environ_overrides={"REMOTE_ADDR": "192.0.2.2"},
    )

    assert other_ip_response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/forgot-password",
        "/api/auth/resend-verification",
    ],
)
def test_email_request_blocks_fourth_request(
    rate_limited_client,
    monkeypatch,
    verification_email_mock,
    path,
):
    def reject_unexpected_email(**kwargs):
        pytest.fail("Unexpected email delivery")

    # Prevent real password reset emails during this test.
    monkeypatch.setattr(
        "routes.password_reset.send_email",
        reject_unexpected_email,
    )

    for _ in range(3):
        response = rate_limited_client.post(
            path,
            json={"email": "unknown@example.com"},
        )

        assert response.status_code == 200

    response = rate_limited_client.post(
        path,
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 429
    assert response.get_json()["error"] == RATE_LIMIT_ERROR

    verification_email_mock.assert_not_called()