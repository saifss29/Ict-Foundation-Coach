from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from extensions import db
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from datetime import datetime, timedelta, timezone

import pytest
from models.user import User


def register_and_get_user(
    client,
    email="progress.student@example.com",
    *,
    academic_level="hsc",
):
    with patch(
        "services.email_verification_service.send_email"
    ) as mock_send_email:
        register_response = client.post(
            "/api/auth/register",
            json={
                "name": "Progress Student",
                "email": email,
                "password": "SecurePass123!",
                "academic_level": academic_level,
            },
        )

        assert register_response.status_code == 201
        mock_send_email.assert_called_once()

        email_body = mock_send_email.call_args.kwargs["body"]

    verification_link = next(
        line.strip()
        for line in email_body.splitlines()
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

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    login_data = login_response.get_json()

    assert login_data["user"]["email"] == email
    assert login_data["user"]["academic_level"] == academic_level

    return {
        "user_id": login_data["user"]["id"],
        "headers": {
            "Authorization": f"Bearer {login_data['access_token']}",
        },
    }

def create_topics(app):
    with app.app_context():
        first_topic = Topic(
            title="Number Systems",
            slug="number-systems",
            description="Learn binary and decimal.",
            display_order=1,
        )

        second_topic = Topic(
            title="Boolean Algebra",
            slug="boolean-algebra",
            description="Learn Boolean logic.",
            display_order=2,
        )

        third_topic = Topic(
            title="Logic Gates",
            slug="logic-gates",
            description="Learn AND, OR, and NOT gates.",
            display_order=3,
        )

        db.session.add_all([
            first_topic,
            second_topic,
            third_topic,
        ])
        db.session.commit()

        return {
            "number_systems_id": first_topic.id,
            "boolean_algebra_id": second_topic.id,
            "logic_gates_id": third_topic.id,
        }


def create_attempt(app, user_id, topic_id, score, total_questions):
    with app.app_context():
        attempt = QuizAttempt(
            user_id=user_id,
            topic_id=topic_id,
            score=score,
            total_questions=total_questions,
        )

        db.session.add(attempt)
        db.session.commit()


def test_progress_route_requires_login(client):
    response = client.get("/api/progress")

    assert response.status_code == 401


def test_progress_shows_completed_and_unattempted_topics(client, app):
    user = register_and_get_user(client)
    
    topics = create_topics(app)

    create_attempt(
        app,
        user["user_id"],
        topics["number_systems_id"],
        score=3,
        total_questions=4,
    )

    response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["summary"] == {
        "completed_topics": 1,
        "total_topics": 3,
    }

    number_systems = data["topics"][0]
    boolean_algebra = data["topics"][1]

    assert number_systems["title"] == "Number Systems"
    assert number_systems["attempt_count"] == 1
    assert number_systems["latest_score"] == 3
    assert number_systems["total_questions"] == 4
    assert number_systems["percentage"] == 75

    assert boolean_algebra["title"] == "Boolean Algebra"
    assert boolean_algebra["attempt_count"] == 0
    assert boolean_algebra["latest_score"] is None
    assert boolean_algebra["percentage"] is None


def test_recommendation_suggests_first_unattempted_topic(client, app):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_attempt(
        app,
        user["user_id"],
        topics["number_systems_id"],
        score=4,
        total_questions=5,
    )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()["recommendation"]

    assert data["topic"] == "Boolean Algebra"
    assert data["slug"] == "boolean-algebra"
    assert data["reason"] == (
        "Ei topic ekhono quiz diye practice koro nai."
    )


def test_recommendation_suggests_weakest_topic_after_all_attempted(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_attempt(
        app,
        user["user_id"],
        topics["number_systems_id"],
        score=4,
        total_questions=5,
    )

    create_attempt(
        app,
        user["user_id"],
        topics["boolean_algebra_id"],
        score=1,
        total_questions=5,
    )

    create_attempt(
        app,
        user["user_id"],
        topics["logic_gates_id"],
        score=3,
        total_questions=5,
    )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()["recommendation"]

    assert data["topic"] == "Boolean Algebra"
    assert data["slug"] == "boolean-algebra"
    assert data["reason"] == (
        "Tomar latest quiz score 20% chilo. "
        "Ei topic arekbar practice koro."
    )

def create_dated_attempts(
    app,
    user_id,
    topic_id,
    results,
    *,
    same_timestamp=False,
):
    """Results are supplied oldest first."""
    base_time = datetime(2026, 10, 1, tzinfo=timezone.utc)

    with app.app_context():
        for index, (score, total_questions) in enumerate(results):
            attempt = QuizAttempt(
                user_id=user_id,
                topic_id=topic_id,
                score=score,
                total_questions=total_questions,
            )

            attempt.completed_at = (
                base_time
                if same_timestamp
                else base_time + timedelta(minutes=index)
            )

            db.session.add(attempt)

            # Make insertion order explicit for timestamp tie tests.
            db.session.flush()

        db.session.commit()


@pytest.mark.parametrize(
    ("results", "expected_status"),
    [
        ([], "not_started"),
        ([(0, 5)], "needs_support"),
        ([(49, 100)], "needs_support"),
        ([(1, 2)], "practicing"),
        ([(79, 100)], "practicing"),
        ([(4, 5)], "almost_mastered"),
        ([(5, 5)], "almost_mastered"),
        ([(1, 5), (4, 5)], "almost_mastered"),
        ([(4, 5), (4, 5)], "mastered"),
        ([(8, 10), (5, 5)], "mastered"),
        ([(5, 5), (5, 5), (1, 5)], "needs_support"),
        ([(5, 5), (1, 5), (5, 5)], "almost_mastered"),
        ([(5, 5), (3, 5)], "practicing"),
    ],
)
def test_progress_mastery_rules(
    client,
    app,
    results,
    expected_status,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_dated_attempts(
        app,
        user["user_id"],
        topics["number_systems_id"],
        results,
    )

    response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert response.status_code == 200

    data = response.get_json()
    topic = data["topics"][0]

    assert topic["mastery_status"] == expected_status
    assert topic["attempt_count"] == len(results)
    assert data["summary"]["completed_topics"] == (
        1 if results else 0
    )

    if results:
        latest_score, latest_total = results[-1]

        assert topic["latest_score"] == latest_score
        assert topic["total_questions"] == latest_total
        assert topic["percentage"] == round(
            latest_score / latest_total * 100
        )
    else:
        assert topic["latest_score"] is None
        assert topic["total_questions"] is None
        assert topic["percentage"] is None

    # Attempts in Number Systems do not affect other topics.
    assert data["topics"][1]["mastery_status"] == "not_started"
    assert data["topics"][2]["mastery_status"] == "not_started"


@pytest.mark.parametrize(
    ("score", "expected_percentage", "expected_status"),
    [
        (499, 50, "needs_support"),
        (799, 80, "practicing"),
    ],
)
def test_mastery_uses_actual_score_before_rounding(
    client,
    app,
    score,
    expected_percentage,
    expected_status,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_dated_attempts(
        app,
        user["user_id"],
        topics["number_systems_id"],
        [(score, 1000)],
    )

    response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert response.status_code == 200

    topic = response.get_json()["topics"][0]

    assert topic["percentage"] == expected_percentage
    assert topic["mastery_status"] == expected_status


def test_progress_uses_higher_id_when_timestamps_match(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_dated_attempts(
        app,
        user["user_id"],
        topics["number_systems_id"],
        [(5, 5), (5, 5), (1, 5)],
        same_timestamp=True,
    )

    response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert response.status_code == 200

    topic = response.get_json()["topics"][0]

    assert topic["attempt_count"] == 3
    assert topic["latest_score"] == 1
    assert topic["percentage"] == 20
    assert topic["mastery_status"] == "needs_support"


def test_progress_mastery_ignores_other_students_attempts(
    client,
    app,
):
    student = register_and_get_user(client)
    other_student = register_and_get_user(
        client,
        email="other.progress.student@example.com",
    )
    assert student["user_id"] != other_student["user_id"]
    topics = create_topics(app)

    create_dated_attempts(
        app,
        student["user_id"],
        topics["number_systems_id"],
        [(4, 5)],
    )

    create_dated_attempts(
        app,
        other_student["user_id"],
        topics["number_systems_id"],
        [(5, 5), (5, 5)],
    )

    response = client.get(
        "/api/progress",
        headers=student["headers"],
    )

    assert response.status_code == 200

    topic = response.get_json()["topics"][0]

    assert topic["attempt_count"] == 1
    assert topic["latest_score"] == 4
    assert topic["mastery_status"] == "almost_mastered"


def test_recommendation_returns_not_started_status(client, app):
    user = register_and_get_user(client)
    create_topics(app)

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    recommendation = response.get_json()["recommendation"]

    assert recommendation["slug"] == "number-systems"
    assert recommendation["mastery_status"] == "not_started"


def test_recommendation_prefers_almost_mastered_over_mastered(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    # Lower latest score, but two consecutive strong attempts.
    create_dated_attempts(
        app,
        user["user_id"],
        topics["number_systems_id"],
        [(4, 5), (4, 5)],
    )

    # Higher latest score, but only one strong attempt.
    create_dated_attempts(
        app,
        user["user_id"],
        topics["boolean_algebra_id"],
        [(5, 5)],
    )

    create_dated_attempts(
        app,
        user["user_id"],
        topics["logic_gates_id"],
        [(5, 5), (5, 5)],
    )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    recommendation = response.get_json()["recommendation"]

    assert recommendation["slug"] == "boolean-algebra"
    assert recommendation["mastery_status"] == "almost_mastered"
    assert "Arekbar 80%" in recommendation["reason"]


def test_recommendation_selects_lowest_score_within_same_status(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    for topic_id, score in [
        (topics["number_systems_id"], 7),
        (topics["boolean_algebra_id"], 5),
        (topics["logic_gates_id"], 6),
    ]:
        create_dated_attempts(
            app,
            user["user_id"],
            topic_id,
            [(score, 10)],
        )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    recommendation = response.get_json()["recommendation"]

    assert recommendation["slug"] == "boolean-algebra"
    assert recommendation["mastery_status"] == "practicing"


def test_recommendation_uses_topic_order_for_equal_priority(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    for topic_id in reversed(list(topics.values())):
        create_dated_attempts(
            app,
            user["user_id"],
            topic_id,
            [(3, 5)],
        )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    recommendation = response.get_json()["recommendation"]

    assert recommendation["slug"] == "number-systems"
    assert recommendation["mastery_status"] == "practicing"


def test_recommendation_suggests_revision_when_all_mastered(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    for topic_id in topics.values():
        create_dated_attempts(
            app,
            user["user_id"],
            topic_id,
            [(4, 5), (5, 5)],
        )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 200

    recommendation = response.get_json()["recommendation"]

    assert recommendation["slug"] == "number-systems"
    assert recommendation["mastery_status"] == "mastered"
    assert "Shob topic-e" in recommendation["reason"]
    assert "revise" in recommendation["reason"]


def test_recommendation_ignores_other_students_mastery(
    client,
    app,
):
    student = register_and_get_user(client)
    other_student = register_and_get_user(
        client,
        email="other.recommendation.student@example.com",
    )

    assert student["user_id"] != other_student["user_id"]

    topics = create_topics(app)

    # Own results: Boolean Algebra needs support.
    for topic_id, score in [
        (topics["number_systems_id"], 5),
        (topics["boolean_algebra_id"], 1),
        (topics["logic_gates_id"], 5),
    ]:
        create_dated_attempts(
            app,
            student["user_id"],
            topic_id,
            [(score, 5)],
        )

    # Another student's strong results must not replace these.
    for topic_id in topics.values():
        create_dated_attempts(
            app,
            other_student["user_id"],
            topic_id,
            [(5, 5), (5, 5)],
        )

    response = client.get(
        "/api/recommendations/next-topic",
        headers=student["headers"],
    )

    assert response.status_code == 200

    recommendation = response.get_json()["recommendation"]

    assert recommendation["slug"] == "boolean-algebra"
    assert recommendation["mastery_status"] == "needs_support"


def test_recommendation_returns_404_without_topics(client):
    user = register_and_get_user(client)

    response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "No learning topics found"


def test_recommendation_requires_login(client):
    response = client.get("/api/recommendations/next-topic")

    assert response.status_code == 401

@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_progress_and_recommendations_only_use_own_level(
    client,
    app,
    academic_level,
):
    user = register_and_get_user(
        client,
        academic_level=academic_level,
    )
    other_level = "hsc" if academic_level == "ssc" else "ssc"

    with app.app_context():
        own_topic = Topic(
            title="Own Level Topic",
            slug="own-level-topic",
            description="Topic for the student's study level.",
            display_order=2,
            academic_level=academic_level,
        )
        other_topic = Topic(
            title="Other Level Topic",
            slug="other-level-topic",
            description="Topic for a different study level.",
            display_order=1,
            academic_level=other_level,
        )
        db.session.add_all([own_topic, other_topic])
        db.session.commit()

        own_topic_id = own_topic.id
        other_topic_id = other_topic.id

    # An unattempted other-level topic must not be recommended first.
    recommendation_response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert recommendation_response.status_code == 200
    recommendation = recommendation_response.get_json()["recommendation"]
    assert recommendation["slug"] == "own-level-topic"
    assert recommendation["mastery_status"] == "not_started"

    # Simulate an older attempt on an other-level topic.
    create_attempt(
        app,
        user["user_id"],
        other_topic_id,
        score=0,
        total_questions=5,
    )

    progress_response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert progress_response.status_code == 200
    progress = progress_response.get_json()

    assert progress["summary"] == {
        "completed_topics": 0,
        "total_topics": 1,
    }
    assert len(progress["topics"]) == 1
    assert progress["topics"][0]["slug"] == "own-level-topic"
    assert progress["topics"][0]["attempt_count"] == 0

    create_attempt(
        app,
        user["user_id"],
        own_topic_id,
        score=4,
        total_questions=5,
    )

    progress_response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert progress_response.status_code == 200
    progress = progress_response.get_json()

    assert progress["summary"] == {
        "completed_topics": 1,
        "total_topics": 1,
    }
    assert len(progress["topics"]) == 1
    assert progress["topics"][0]["slug"] == "own-level-topic"
    assert progress["topics"][0]["attempt_count"] == 1
    assert progress["topics"][0]["latest_score"] == 4
    assert progress["topics"][0]["percentage"] == 80
    assert progress["topics"][0]["mastery_status"] == "almost_mastered"

    # The weaker other-level attempt must not become the recommendation.
    recommendation_response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert recommendation_response.status_code == 200
    recommendation = recommendation_response.get_json()["recommendation"]
    assert recommendation["slug"] == "own-level-topic"
    assert recommendation["mastery_status"] == "almost_mastered"


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_progress_and_recommendations_when_only_other_level_topics_exist(
    client,
    app,
    academic_level,
):
    user = register_and_get_user(
        client,
        academic_level=academic_level,
    )
    other_level = "hsc" if academic_level == "ssc" else "ssc"

    with app.app_context():
        topic = Topic(
            title="Unavailable Level Topic",
            slug="unavailable-level-topic",
            description="Topic outside the student's study level.",
            display_order=1,
            academic_level=other_level,
        )
        db.session.add(topic)
        db.session.commit()

    progress_response = client.get(
        "/api/progress",
        headers=user["headers"],
    )

    assert progress_response.status_code == 200
    assert progress_response.get_json() == {
        "summary": {
            "completed_topics": 0,
            "total_topics": 0,
        },
        "topics": [],
    }

    recommendation_response = client.get(
        "/api/recommendations/next-topic",
        headers=user["headers"],
    )

    assert recommendation_response.status_code == 404
    assert recommendation_response.get_json()["error"] == (
        "No learning topics found"
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/progress",
        "/api/recommendations/next-topic",
    ],
)
def test_learning_summary_requires_saved_study_level(
    client,
    app,
    endpoint,
):
    user_data = register_and_get_user(client)

    with app.app_context():
        user = db.session.get(User, user_data["user_id"])
        assert user is not None

        user.academic_level = None
        db.session.commit()

    response = client.get(
        endpoint,
        headers=user_data["headers"],
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACADEMIC_LEVEL_REQUIRED"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/progress",
        "/api/recommendations/next-topic",
    ],
)
def test_teacher_cannot_access_student_learning_summary(
    client,
    app,
    endpoint,
):
    user_data = register_and_get_user(client)

    # Simulate a teacher account using the existing authentication helper.
    with app.app_context():
        user = db.session.get(User, user_data["user_id"])
        assert user is not None

        user.role = "teacher"
        user.academic_level = None
        db.session.commit()

    response = client.get(
        endpoint,
        headers=user_data["headers"],
    )

    assert response.status_code == 403

def test_weak_topics_requires_login(client):
    response = client.get("/api/progress/weak-topics")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("role", "academic_level", "expected_status"),
    [
        ("teacher", None, 403),
        ("student", None, 409),
    ],
)
def test_weak_topics_rejects_unavailable_account_context(
    client,
    app,
    role,
    academic_level,
    expected_status,
):
    user_data = register_and_get_user(client)

    with app.app_context():
        user = db.session.get(User, user_data["user_id"])
        assert user is not None

        user.role = role
        user.academic_level = academic_level
        db.session.commit()

    response = client.get(
        "/api/progress/weak-topics",
        headers=user_data["headers"],
    )

    assert response.status_code == expected_status

    if expected_status == 409:
        assert response.get_json()["code"] == "ACADEMIC_LEVEL_REQUIRED"


def test_weak_topics_without_topics_returns_empty_report(client):
    user = register_and_get_user(client)

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["summary"] == {
        "total_topics": 0,
        "weak_topics": 0,
        "other_practised_topics": 0,
        "not_practised_topics": 0,
    }
    assert data["weak_topics"] == []
    assert data["other_practised_topics"] == []
    assert data["not_practised_topics"] == []


def test_unattempted_topics_are_not_classified_as_weak(client, app):
    user = register_and_get_user(client)
    topics = create_topics(app)

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["weak_topics"] == []
    assert data["other_practised_topics"] == []
    assert data["summary"] == {
        "total_topics": 3,
        "weak_topics": 0,
        "other_practised_topics": 0,
        "not_practised_topics": 3,
    }
    assert [
        item["topic_id"]
        for item in data["not_practised_topics"]
    ] == list(topics.values())
    assert all(
        item["mastery_status"] == "not_started"
        and item["attempt_count"] == 0
        for item in data["not_practised_topics"]
    )


@pytest.mark.parametrize(
    ("score", "total", "is_weak", "mastery_status"),
    [
        (0, 5, True, "needs_support"),
        (1, 2, True, "practicing"),
        (7999, 10000, True, "practicing"),
        (4, 5, False, "almost_mastered"),
        (5, 5, False, "almost_mastered"),
    ],
)
def test_weak_topics_uses_actual_eighty_percent_boundary(
    client,
    app,
    score,
    total,
    is_weak,
    mastery_status,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_attempt(
        app,
        user["user_id"],
        topics["number_systems_id"],
        score,
        total,
    )

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
    )

    assert response.status_code == 200
    data = response.get_json()

    bucket = (
        "weak_topics"
        if is_weak
        else "other_practised_topics"
    )
    other_bucket = (
        "other_practised_topics"
        if is_weak
        else "weak_topics"
    )

    assert len(data[bucket]) == 1
    assert data[other_bucket] == []

    item = data[bucket][0]
    assert item["latest_score"] == score
    assert item["total_questions"] == total
    assert item["latest_percentage"] == round(score / total * 100, 1)
    assert item["mastery_status"] == mastery_status
    assert item["previous_percentage"] is None
    assert item["trend"] == "not_enough_attempts"
    assert data["practice_threshold_percentage"] == 80


@pytest.mark.parametrize(
    ("results", "expected_trend", "expected_bucket"),
    [
        ([(1, 5), (3, 5)], "improving", "weak_topics"),
        ([(5, 5), (1, 5)], "declining", "weak_topics"),
        ([(3, 5), (6, 10)], "unchanged", "weak_topics"),
        ([(0, 5), (4, 5)], "improving", "other_practised_topics"),
    ],
)
def test_weak_topics_uses_latest_attempt_and_compares_percentages(
    client,
    app,
    results,
    expected_trend,
    expected_bucket,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_dated_attempts(
        app,
        user["user_id"],
        topics["number_systems_id"],
        results,
    )

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
    )

    assert response.status_code == 200
    data = response.get_json()
    item = data[expected_bucket][0]

    previous_score, previous_total = results[0]
    latest_score, latest_total = results[-1]

    assert item["attempt_count"] == 2
    assert item["latest_score"] == latest_score
    assert item["total_questions"] == latest_total
    assert item["previous_percentage"] == round(
        previous_score / previous_total * 100, 1
    )
    assert item["latest_percentage"] == round(
        latest_score / latest_total * 100, 1
    )
    assert item["trend"] == expected_trend


def test_weak_topics_timestamp_ties_use_higher_attempt_id(client, app):
    user = register_and_get_user(client)
    topics = create_topics(app)

    create_dated_attempts(
        app,
        user["user_id"],
        topics["number_systems_id"],
        [(5, 5), (1, 5)],
        same_timestamp=True,
    )

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
    )

    assert response.status_code == 200
    item = response.get_json()["weak_topics"][0]

    assert item["latest_score"] == 1
    assert item["previous_percentage"] == 100
    assert item["trend"] == "declining"


def test_weak_topics_orders_by_actual_percentage_before_rounding(
    client,
    app,
):
    user = register_and_get_user(client)
    topics = create_topics(app)

    # Both display as 60.0%, but Boolean Algebra is actually weaker.
    create_attempt(
        app,
        user["user_id"],
        topics["number_systems_id"],
        6004,
        10000,
    )
    create_attempt(
        app,
        user["user_id"],
        topics["boolean_algebra_id"],
        6001,
        10000,
    )

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
    )

    assert response.status_code == 200
    items = response.get_json()["weak_topics"]

    assert [item["slug"] for item in items] == [
        "boolean-algebra",
        "number-systems",
    ]
    assert [item["latest_percentage"] for item in items] == [60.0, 60.0]


def test_weak_topics_ignores_other_students_attempts(client, app):
    student = register_and_get_user(client)
    other = register_and_get_user(
        client,
        email="other.weak.student@example.com",
    )
    topics = create_topics(app)

    create_dated_attempts(
        app,
        student["user_id"],
        topics["number_systems_id"],
        [(1, 5)],
    )
    create_dated_attempts(
        app,
        other["user_id"],
        topics["number_systems_id"],
        [(5, 5), (5, 5)],
    )
    create_attempt(
        app,
        other["user_id"],
        topics["boolean_algebra_id"],
        0,
        5,
    )

    response = client.get(
        "/api/progress/weak-topics",
        headers=student["headers"],
    )

    assert response.status_code == 200
    data = response.get_json()

    assert len(data["weak_topics"]) == 1
    assert data["weak_topics"][0]["latest_score"] == 1
    assert data["weak_topics"][0]["attempt_count"] == 1
    assert data["summary"]["not_practised_topics"] == 2


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_weak_topics_filters_level_and_subject_from_saved_account(
    client,
    app,
    academic_level,
):
    user = register_and_get_user(
        client,
        academic_level=academic_level,
    )
    other_level = "hsc" if academic_level == "ssc" else "ssc"

    with app.app_context():
        own_topic = Topic(
            title="Own ICT Lesson",
            slug="own-ict-lesson",
            description="Own level ICT.",
            display_order=1,
            subject="ict",
            academic_level=academic_level,
        )
        other_topic = Topic(
            title="Other ICT Lesson",
            slug="other-ict-lesson",
            description="Other level ICT.",
            display_order=2,
            subject="ict",
            academic_level=other_level,
        )
        math_topic = Topic(
            title="Own Math Lesson",
            slug="own-math-lesson",
            description="Another subject.",
            display_order=3,
            subject="math",
            academic_level=academic_level,
        )
        db.session.add_all([own_topic, other_topic, math_topic])
        db.session.commit()

        topic_ids = [own_topic.id, other_topic.id, math_topic.id]

    for topic_id in topic_ids:
        create_attempt(
            app,
            user["user_id"],
            topic_id,
            1,
            5,
        )

    response = client.get(
        "/api/progress/weak-topics",
        headers=user["headers"],
        query_string={
            "academic_level": other_level,
            "subject": "math",
        },
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["summary"]["total_topics"] == 1
    assert [item["slug"] for item in data["weak_topics"]] == [
        "own-ict-lesson",
    ]
    assert data["other_practised_topics"] == []
    assert data["not_practised_topics"] == []