import pytest
from flask_jwt_extended import create_access_token

from extensions import db
from models.topic import Topic
from models.user import User


def create_user_headers(role="student", academic_level=None):
    user = User(
        name="Topics Test User",
        email="topics-test@example.com",
        password_hash="unused-password-hash",
        role=role,
        academic_level=academic_level,
    )
    user.is_email_verified = True

    db.session.add(user)
    db.session.commit()

    token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "token_version": user.token_version,
        },
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def learning_topics(app):
    topics = [
        Topic(
            title="SSC ICT Basics",
            slug="ssc-ict-basics",
            description="SSC ICT practice.",
            display_order=2,
            subject="ict",
            academic_level="ssc",
        ),
        Topic(
            title="SSC Algebra",
            slug="ssc-algebra",
            description="SSC mathematics practice.",
            display_order=1,
            subject="math",
            academic_level="ssc",
        ),
        Topic(
            title="HSC Number Systems",
            slug="hsc-number-systems",
            description="HSC ICT practice.",
            display_order=2,
            subject="ict",
            academic_level="hsc",
        ),
        Topic(
            title="HSC English Grammar",
            slug="hsc-english-grammar",
            description="HSC English practice.",
            display_order=1,
            subject="english",
            academic_level="hsc",
        ),
    ]

    db.session.add_all(topics)
    db.session.commit()


@pytest.mark.parametrize(
    ("academic_level", "expected_slugs"),
    [
        ("ssc", ["ssc-algebra", "ssc-ict-basics"]),
        ("hsc", ["hsc-english-grammar", "hsc-number-systems"]),
    ],
)
def test_student_receives_only_own_level_topics(
    app,
    client,
    learning_topics,
    academic_level,
    expected_slugs,
):
    headers = create_user_headers(
        academic_level=academic_level,
    )

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 200

    topics = response.get_json()["topics"]

    assert [topic["slug"] for topic in topics] == expected_slugs
    assert all(
        topic["academic_level"] == academic_level
        for topic in topics
    )

    for topic in topics:
        assert set(topic) == {
            "id",
            "title",
            "slug",
            "description",
            "display_order",
            "subject",
            "academic_level",
        }


def test_teacher_receives_both_levels(
    app,
    client,
    learning_topics,
):
    headers = create_user_headers(role="teacher")

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 200

    topics = response.get_json()["topics"]

    assert len(topics) == 4
    assert {topic["academic_level"] for topic in topics} == {
        "ssc",
        "hsc",
    }

    assert [
        (topic["display_order"], topic["id"])
        for topic in topics
    ] == sorted(
        (topic["display_order"], topic["id"])
        for topic in topics
    )


def test_student_without_level_must_select_level(
    app,
    client,
    learning_topics,
):
    headers = create_user_headers()

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACADEMIC_LEVEL_REQUIRED"
    assert "topics" not in response.get_json()


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_student_cannot_override_level_with_query_parameter(
    app,
    client,
    learning_topics,
    academic_level,
):
    headers = create_user_headers(
        academic_level=academic_level,
    )
    other_level = "hsc" if academic_level == "ssc" else "ssc"

    response = client.get(
        f"/api/topics?academic_level={other_level}",
        headers=headers,
    )

    assert response.status_code == 200

    topics = response.get_json()["topics"]

    assert len(topics) == 2
    assert all(
        topic["academic_level"] == academic_level
        for topic in topics
    )


def test_student_with_no_matching_topics_receives_empty_list(
    app,
    client,
):
    headers = create_user_headers(academic_level="ssc")

    db.session.add(
        Topic(
            title="HSC Only Topic",
            slug="hsc-only-topic",
            description="Available only for HSC.",
            display_order=1,
            subject="ict",
            academic_level="hsc",
        )
    )
    db.session.commit()

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 200
    assert response.get_json()["topics"] == []


def test_topics_require_authentication(client):
    response = client.get("/api/topics")

    assert response.status_code == 401


def test_deleted_user_cannot_access_topics(
    app,
    client,
    learning_topics,
):
    headers = create_user_headers(academic_level="hsc")

    user = db.session.scalar(
        db.select(User).where(
            User.email == "topics-test@example.com"
        )
    )

    assert user is not None

    db.session.delete(user)
    db.session.commit()

    response = client.get("/api/topics", headers=headers)

    # JWT account validation or the route rejects the deleted account.
    assert response.status_code in (401, 404)
    assert "topics" not in response.get_json()

@pytest.mark.parametrize(
    ("academic_level", "expected_slug"),
    [
        ("ssc", "ssc-ict-basics"),
        ("hsc", "hsc-number-systems"),
    ],
)
def test_search_returns_only_ict_topics_for_student_level(
    app,
    client,
    learning_topics,
    academic_level,
    expected_slug,
):
    headers = create_user_headers(
        academic_level=academic_level,
    )
    other_level = "hsc" if academic_level == "ssc" else "ssc"

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"academic_level": other_level},
    )

    assert response.status_code == 200
    data = response.get_json()

    assert [item["slug"] for item in data["topics"]] == [
        expected_slug,
    ]
    assert data["pagination"] == {
        "page": 1,
        "page_size": 20,
        "has_more": False,
    }


def test_search_matches_title_case_insensitively(
    app,
    client,
    learning_topics,
):
    headers = create_user_headers(academic_level="hsc")

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"q": "  NUMBER  "},
    )

    assert response.status_code == 200
    assert [
        item["slug"]
        for item in response.get_json()["topics"]
    ] == ["hsc-number-systems"]


def test_search_excludes_broad_subject_cards(app, client):
    headers = create_user_headers(academic_level="ssc")

    db.session.add_all([
        Topic(
            title="SSC ICT",
            slug="ssc-ict",
            description="Broad subject entry.",
            display_order=0,
            academic_level="ssc",
        ),
        Topic(
            title="Save and Save As",
            slug="ssc-save-and-save-as",
            description="Document saving practice.",
            display_order=1,
            academic_level="ssc",
        ),
    ])
    db.session.commit()

    response = client.get(
        "/api/topics/search",
        headers=headers,
    )

    assert response.status_code == 200
    assert [
        item["slug"]
        for item in response.get_json()["topics"]
    ] == ["ssc-save-and-save-as"]


def test_search_paginates_without_duplicates(app, client):
    headers = create_user_headers(academic_level="ssc")

    db.session.add_all([
        Topic(
            title=f"SSC Practice {index}",
            slug=f"ssc-practice-{index}",
            description="Pagination test lesson.",
            display_order=index,
            academic_level="ssc",
        )
        for index in range(21)
    ])
    db.session.commit()

    first_response = client.get(
        "/api/topics/search?page=1",
        headers=headers,
    )
    second_response = client.get(
        "/api/topics/search?page=2",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first = first_response.get_json()
    second = second_response.get_json()

    assert len(first["topics"]) == 20
    assert first["pagination"]["has_more"] is True
    assert len(second["topics"]) == 1
    assert second["pagination"]["has_more"] is False

    combined = first["topics"] + second["topics"]

    assert len({item["id"] for item in combined}) == 21
    assert [item["display_order"] for item in combined] == list(
        range(21)
    )


@pytest.mark.parametrize("search_text", ["%", "_", "\\"])
def test_search_treats_wildcards_as_literal_text(
    app,
    client,
    learning_topics,
    search_text,
):
    headers = create_user_headers(academic_level="ssc")

    db.session.add(
        Topic(
            title=f"Literal {search_text} lesson",
            slug="literal-search-lesson",
            description="Literal character search.",
            display_order=3,
            academic_level="ssc",
        )
    )
    db.session.commit()

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"q": search_text},
    )

    assert response.status_code == 200
    assert [
        item["slug"]
        for item in response.get_json()["topics"]
    ] == ["literal-search-lesson"]


@pytest.mark.parametrize("page", ["0", "-1", "abc", "10001"])
def test_search_rejects_invalid_page(app, client, page):
    headers = create_user_headers(academic_level="ssc")

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"page": page},
    )

    assert response.status_code == 400


def test_search_rejects_overlong_query(app, client):
    headers = create_user_headers(academic_level="ssc")

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"q": "a" * 101},
    )

    assert response.status_code == 400


def test_search_without_match_returns_empty_list(
    app,
    client,
    learning_topics,
):
    headers = create_user_headers(academic_level="ssc")

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"q": "nonexistent lesson"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["topics"] == []
    assert data["pagination"]["has_more"] is False


def test_search_requires_authentication(client):
    response = client.get("/api/topics/search")

    assert response.status_code == 401


def test_search_requires_student_level(app, client):
    headers = create_user_headers()

    response = client.get(
        "/api/topics/search",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACADEMIC_LEVEL_REQUIRED"