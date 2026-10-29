from app import app


def test_health_check():
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "ICT Foundation Coach backend is running"
    }