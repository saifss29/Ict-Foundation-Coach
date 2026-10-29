from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from extensions import db
from models.chat_conversation import ChatConversation
from models.chat_message import ChatMessage
from models.topic import Topic
from models.user import User


def authenticated_headers(
    client,
    *,
    email="chat.student@example.com",
    role="student",
    academic_level="hsc",
):
    registration_data = {
        "name": "Chat Test User",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = academic_level

    with patch(
        "services.email_verification_service.send_email"
    ) as mock_send_email:
        register_response = client.post(
            "/api/auth/register",
            json=registration_data,
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

    verify_response = client.post(
        "/api/auth/verify-email",
        json={"token": verification_token},
    )

    assert verify_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.get_json()["access_token"]

    return {
        "Authorization": f"Bearer {access_token}",
    }


def set_maira_environment(monkeypatch):
    monkeypatch.setenv("MAIRA_API_KEY", "test-api-key")
    monkeypatch.setenv("MAIRA_PROJECT_KEY", "test-project-key")
    monkeypatch.setenv("MAIRA_ASK_URL", "https://maira.test/api/ask")
    monkeypatch.setenv("MAIRA_GPT_PROFILE_ID", "test-profile-id")
    monkeypatch.setenv("MAIRA_MEMBER_ID", "test-member-id")
    monkeypatch.setenv("MAIRA_USER_ID", "test-user-id")
    monkeypatch.setenv("MAIRA_USER_NAME", "Test Student")


def mock_maira_answer(monkeypatch, answer):
    set_maira_environment(monkeypatch)

    fake_response = Mock()
    fake_response.json.return_value = {
        "detail": {
            "response": answer,
        }
    }
    fake_response.raise_for_status.return_value = None

    mock_post = Mock(return_value=fake_response)
    monkeypatch.setattr("app.requests.post", mock_post)

    return mock_post


def send_chat(
    client,
    headers,
    *,
    message="What is binary?",
    topic="Number Systems",
    language="english",
    session_id=None,
):
    return client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": message,
            "topic": topic,
            "response_language": language,
            "session_id": session_id,
        },
    )


def stored_messages(conversation_id):
    return db.session.scalars(
        db.select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.id)
    ).all()


def assert_no_saved_chat():
    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatConversation)
    ) == 0

    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatMessage)
    ) == 0


def test_chat_route_requires_login(client):
    response = client.post(
        "/api/chat",
        json={"message": "What is binary?"},
    )

    assert response.status_code == 401


def test_chat_rejects_invalid_response_language(client):
    headers = authenticated_headers(client)

    response = send_chat(
        client,
        headers,
        language="bangla",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Response language must be banglish or english"
    )


def test_chat_rejects_empty_message(client):
    headers = authenticated_headers(client)

    response = send_chat(
        client,
        headers,
        message="   ",
        language="banglish",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Message is required"


def test_chat_returns_mocked_maira_answer_in_english(client, monkeypatch):
    headers = authenticated_headers(client)
    expected_answer = "Binary is a number system that uses 0 and 1."

    mock_post = mock_maira_answer(monkeypatch, expected_answer)

    response = send_chat(client, headers)

    assert response.status_code == 200

    data = response.get_json()

    assert data["answer"] == expected_answer
    assert data["topic"] == "Number Systems"
    assert data["response_language"] == "english"
    assert isinstance(data["session_id"], str)
    assert data["session_id"]

    mock_post.assert_called_once()

    sent_payload = mock_post.call_args.kwargs["json"]

    assert sent_payload["session_id"] == data["session_id"]
    assert "What is binary?" in sent_payload["query"]
    assert "Reply in clear, simple English." in sent_payload["query"]


def test_chat_returns_timeout_error_when_maira_is_slow(client, monkeypatch):
    headers = authenticated_headers(client)
    set_maira_environment(monkeypatch)

    mock_post = Mock(side_effect=requests.Timeout)
    monkeypatch.setattr("app.requests.post", mock_post)

    response = send_chat(
        client,
        headers,
        message="Explain logic gates.",
        topic="General ICT",
        language="banglish",
    )

    assert response.status_code == 504
    assert response.get_json()["error"] == (
        "Maira took too long to respond. Please try again."
    )

    assert_no_saved_chat()


def test_chat_saves_conversation_and_both_messages(client, monkeypatch):
    headers = authenticated_headers(client)
    expected_answer = "Binary uses the digits 0 and 1."

    mock_maira_answer(monkeypatch, expected_answer)

    profile_response = client.get("/api/auth/me", headers=headers)
    assert profile_response.status_code == 200

    user_id = profile_response.get_json()["user"]["id"]

    response = send_chat(client, headers)
    assert response.status_code == 200

    conversation_id = response.get_json()["session_id"]
    conversation = db.session.get(ChatConversation, conversation_id)

    assert conversation is not None
    assert conversation.user_id == user_id
    assert conversation.title == "What is binary?"
    assert conversation.topic == "Number Systems"
    assert conversation.response_language == "english"
    assert conversation.created_at is not None
    assert conversation.updated_at is not None

    messages = stored_messages(conversation_id)

    assert [(message.role, message.content) for message in messages] == [
        ("student", "What is binary?"),
        ("assistant", expected_answer),
    ]


def test_student_can_continue_own_conversation(client, monkeypatch):
    headers = authenticated_headers(client)

    mock_maira_answer(monkeypatch, "Binary uses 0 and 1.")

    first_response = send_chat(client, headers)
    assert first_response.status_code == 200

    conversation_id = first_response.get_json()["session_id"]

    second_mock = mock_maira_answer(
        monkeypatch,
        "Binary 101 equals decimal 5.",
    )

    second_response = send_chat(
        client,
        headers,
        message="Give me an example.",
        session_id=conversation_id,
    )

    assert second_response.status_code == 200
    assert second_response.get_json()["session_id"] == conversation_id

    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatConversation)
    ) == 1

    messages = stored_messages(conversation_id)

    assert [(message.role, message.content) for message in messages] == [
        ("student", "What is binary?"),
        ("assistant", "Binary uses 0 and 1."),
        ("student", "Give me an example."),
        ("assistant", "Binary 101 equals decimal 5."),
    ]

    second_mock.assert_called_once()
    assert second_mock.call_args.kwargs["json"]["session_id"] == (
        conversation_id
    )


def test_student_cannot_use_another_students_conversation(
    client,
    monkeypatch,
):
    owner_headers = authenticated_headers(
        client,
        email="owner@example.com",
    )
    other_headers = authenticated_headers(
        client,
        email="other@example.com",
    )

    mock_post = mock_maira_answer(monkeypatch, "Binary uses 0 and 1.")

    first_response = send_chat(client, owner_headers)
    assert first_response.status_code == 200

    conversation_id = first_response.get_json()["session_id"]

    mock_post.reset_mock()

    response = send_chat(
        client,
        other_headers,
        message="Continue this conversation.",
        session_id=conversation_id,
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == (
        "Conversation not found. Please start a new chat."
    )

    mock_post.assert_not_called()

    messages = stored_messages(conversation_id)
    assert len(messages) == 2


def test_unknown_conversation_is_rejected(client, monkeypatch):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(monkeypatch, "Unused answer.")

    response = send_chat(
        client,
        headers,
        session_id="00000000-0000-0000-0000-000000000000",
    )

    assert response.status_code == 404
    mock_post.assert_not_called()
    assert_no_saved_chat()


@pytest.mark.parametrize(
    ("topic", "language"),
    [
        ("Variables", "english"),
        ("Number Systems", "banglish"),
    ],
)
def test_existing_conversation_rejects_topic_or_language_change(
    client,
    monkeypatch,
    topic,
    language,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(monkeypatch, "Binary uses 0 and 1.")

    first_response = send_chat(client, headers)
    assert first_response.status_code == 200

    conversation_id = first_response.get_json()["session_id"]

    mock_post.reset_mock()

    response = send_chat(
        client,
        headers,
        topic=topic,
        language=language,
        session_id=conversation_id,
    )

    assert response.status_code == 409
    mock_post.assert_not_called()
    assert len(stored_messages(conversation_id)) == 2


def test_failed_followup_preserves_existing_messages(client, monkeypatch):
    headers = authenticated_headers(client)
    mock_maira_answer(monkeypatch, "Binary uses 0 and 1.")

    first_response = send_chat(client, headers)
    assert first_response.status_code == 200

    conversation_id = first_response.get_json()["session_id"]

    timeout_mock = Mock(side_effect=requests.Timeout)
    monkeypatch.setattr("app.requests.post", timeout_mock)

    response = send_chat(
        client,
        headers,
        message="Give another example.",
        session_id=conversation_id,
    )

    assert response.status_code == 504

    messages = stored_messages(conversation_id)

    assert [(message.role, message.content) for message in messages] == [
        ("student", "What is binary?"),
        ("assistant", "Binary uses 0 and 1."),
    ]

    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatConversation)
    ) == 1


def test_empty_maira_answer_does_not_save_chat(client, monkeypatch):
    headers = authenticated_headers(client)
    mock_maira_answer(monkeypatch, "   ")

    response = send_chat(client, headers)

    assert response.status_code == 502
    assert_no_saved_chat()


def test_teacher_cannot_use_student_tutor(client, monkeypatch):
    headers = authenticated_headers(
        client,
        email="teacher@example.com",
        role="teacher",
    )
    mock_post = mock_maira_answer(monkeypatch, "Unused answer.")

    response = send_chat(client, headers)

    assert response.status_code == 403
    mock_post.assert_not_called()
    assert_no_saved_chat()


@pytest.mark.parametrize(
    "learning_mode",
    ["personal_growth", "exam_preparation"],
)
def test_chat_learning_mode_is_saved_and_used_in_prompt(
    client,
    monkeypatch,
    learning_mode,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Binary uses 0 and 1.",
    )

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "What is binary?",
            "topic": "Number Systems",
            "response_language": "english",
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["learning_mode"] == learning_mode

    conversation = db.session.get(
        ChatConversation,
        data["session_id"],
    )

    assert conversation is not None
    assert conversation.learning_mode == learning_mode
    assert len(stored_messages(conversation.id)) == 2

    mock_post.assert_called_once()
    prompt = mock_post.call_args.kwargs["json"]["query"]

    assert f"Learning mode: {learning_mode}" in prompt

    if learning_mode == "exam_preparation":
        assert "Focus on revision of the selected topic." in prompt
    else:
        assert (
            "Focus on understanding concepts and developing skills."
            in prompt
        )


def test_chat_defaults_to_personal_growth(
    client,
    monkeypatch,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Binary uses 0 and 1.",
    )

    # Existing helper does not send learning_mode.
    response = send_chat(client, headers)

    assert response.status_code == 200
    data = response.get_json()

    assert data["learning_mode"] == "personal_growth"

    conversation = db.session.get(
        ChatConversation,
        data["session_id"],
    )
    assert conversation is not None
    assert conversation.learning_mode == "personal_growth"

    mock_post.assert_called_once()
    assert (
        "Learning mode: personal_growth"
        in mock_post.call_args.kwargs["json"]["query"]
    )


@pytest.mark.parametrize(
    "learning_mode",
    [
        None,
        "",
        "exam",
        "EXAM_PREPARATION",
        " personal_growth ",
        123,
        True,
        [],
        {},
    ],
)
def test_chat_rejects_invalid_learning_mode(
    client,
    monkeypatch,
    learning_mode,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Unused answer.",
    )

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "What is binary?",
            "topic": "Number Systems",
            "response_language": "english",
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Learning mode must be exam_preparation or personal_growth"
    )

    mock_post.assert_not_called()
    assert_no_saved_chat()


@pytest.mark.parametrize(
    ("original_mode", "changed_mode"),
    [
        ("personal_growth", "exam_preparation"),
        ("exam_preparation", "personal_growth"),
    ],
)
def test_existing_chat_rejects_learning_mode_change(
    client,
    monkeypatch,
    original_mode,
    changed_mode,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Binary uses 0 and 1.",
    )

    first_response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "What is binary?",
            "topic": "Number Systems",
            "response_language": "english",
            "learning_mode": original_mode,
        },
    )

    assert first_response.status_code == 200
    conversation_id = first_response.get_json()["session_id"]
    mock_post.reset_mock()

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "Give another example.",
            "topic": "Number Systems",
            "response_language": "english",
            "learning_mode": changed_mode,
            "session_id": conversation_id,
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == (
        "Start a new chat when changing the topic, "
        "response language or learning mode."
    )

    mock_post.assert_not_called()

    conversation = db.session.get(
        ChatConversation,
        conversation_id,
    )
    assert conversation is not None
    assert conversation.learning_mode == original_mode
    assert len(stored_messages(conversation_id)) == 2
    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatConversation)
    ) == 1


@pytest.mark.parametrize(
    "learning_mode",
    ["personal_growth", "exam_preparation"],
)
def test_existing_chat_can_continue_with_same_learning_mode(
    client,
    monkeypatch,
    learning_mode,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Binary uses 0 and 1.",
    )

    first_response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "What is binary?",
            "topic": "Number Systems",
            "response_language": "english",
            "learning_mode": learning_mode,
        },
    )

    assert first_response.status_code == 200
    conversation_id = first_response.get_json()["session_id"]
    mock_post.reset_mock()

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "Give another example.",
            "topic": "Number Systems",
            "response_language": "english",
            "learning_mode": learning_mode,
            "session_id": conversation_id,
        },
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["session_id"] == conversation_id
    assert data["learning_mode"] == learning_mode

    mock_post.assert_called_once()
    assert (
        mock_post.call_args.kwargs["json"]["session_id"]
        == conversation_id
    )

    conversation = db.session.get(
        ChatConversation,
        conversation_id,
    )
    assert conversation is not None
    assert conversation.learning_mode == learning_mode
    assert len(stored_messages(conversation_id)) == 4
    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatConversation)
    ) == 1


@pytest.mark.parametrize(
    ("subject", "subject_label"),
    [
        ("ict", "ICT"),
    ],
)
@pytest.mark.parametrize(
    ("academic_level", "level_label"),
    [
        ("ssc", "SSC"),
        ("hsc", "HSC"),
    ],
)
def test_chat_uses_selected_topics_database_context(
    client,
    monkeypatch,
    subject,
    subject_label,
    academic_level,
    level_label,
):
    headers = authenticated_headers(
        client,
        academic_level=academic_level,
    )
    mock_post = mock_maira_answer(
        monkeypatch,
        "Here is a simple explanation.",
    )

    topic = Topic(
        title=f"Context Test {subject} {academic_level}",
        slug=f"context-test-{subject}-{academic_level}",
        description="Topic used to verify tutor context.",
        display_order=100,
        subject=subject,
        academic_level=academic_level,
    )

    db.session.add(topic)
    db.session.commit()

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "Explain this topic.",
            "topic": topic.title,
            "topic_slug": topic.slug,
            "response_language": "english",
            "learning_mode": "exam_preparation",
        },
    )

    assert response.status_code == 200

    mock_post.assert_called_once()
    prompt = mock_post.call_args.kwargs["json"]["query"]

    assert f"Subject: {subject_label}" in prompt
    assert f"Academic level: {level_label}" in prompt
    assert f"Current learning topic: {topic.title}" in prompt
    assert "Learning mode: exam_preparation" in prompt

    conversation = db.session.get(
        ChatConversation,
        response.get_json()["session_id"],
    )

    assert conversation is not None
    assert conversation.topic == topic.title
    assert conversation.learning_mode == "exam_preparation"
    assert len(stored_messages(conversation.id)) == 2


@pytest.mark.parametrize(
    "topic_slug",
    [
        None,
        "",
        "   ",
        123,
        True,
        [],
        {},
        "a" * 101,
    ],
)
def test_chat_rejects_invalid_topic_slug(
    client,
    monkeypatch,
    topic_slug,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Unused answer.",
    )

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "What is binary?",
            "topic": "Number Systems",
            "topic_slug": topic_slug,
            "response_language": "english",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Topic slug must be a non-empty string "
        "within 100 characters"
    )

    mock_post.assert_not_called()
    assert_no_saved_chat()


def test_chat_rejects_unknown_topic_slug(client, monkeypatch):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Unused answer.",
    )

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "Explain this topic.",
            "topic": "Unknown Topic",
            "topic_slug": "missing-chat-context-topic",
            "response_language": "english",
        },
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Learning topic not found"

    mock_post.assert_not_called()
    assert_no_saved_chat()


def test_chat_rejects_topic_title_and_slug_mismatch(
    client,
    monkeypatch,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Unused answer.",
    )

    topic = Topic(
        title="Context Test Algebra",
        slug="context-test-algebra",
        description="Algebra practice.",
        display_order=100,
        subject="math",
        academic_level="ssc",
    )

    db.session.add(topic)
    db.session.commit()

    response = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "Explain this topic.",
            "topic": "A Different Topic",
            "topic_slug": topic.slug,
            "response_language": "english",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Topic title does not match the selected topic"
    )

    mock_post.assert_not_called()
    assert_no_saved_chat()


def test_chat_without_slug_keeps_ict_hsc_context(
    client,
    monkeypatch,
):
    headers = authenticated_headers(client)
    mock_post = mock_maira_answer(
        monkeypatch,
        "Binary uses 0 and 1.",
    )

    # Existing helper does not send topic_slug.
    response = send_chat(client, headers)

    assert response.status_code == 200

    mock_post.assert_called_once()
    prompt = mock_post.call_args.kwargs["json"]["query"]

    assert "Subject: ICT" in prompt
    assert "Academic level: HSC" in prompt

@pytest.mark.parametrize(
    ("student_level", "topic_level"),
    [
        ("ssc", "hsc"),
        ("hsc", "ssc"),
    ],
)
@pytest.mark.parametrize("include_slug", [True, False])
def test_chat_rejects_other_level_topic(
    client,
    monkeypatch,
    student_level,
    topic_level,
    include_slug,
):
    headers = authenticated_headers(
        client,
        academic_level=student_level,
    )
    mock_post = mock_maira_answer(monkeypatch, "Unused answer.")

    topic = Topic(
        title="Restricted Learning Topic",
        slug="restricted-learning-topic",
        description="Topic for checking level access.",
        display_order=100,
        subject="ict",
        academic_level=topic_level,
    )
    db.session.add(topic)
    db.session.commit()

    payload = {
        "message": "Explain this topic.",
        "topic": topic.title,
        "response_language": "english",
    }

    if include_slug:
        payload["topic_slug"] = topic.slug

    response = client.post(
        "/api/chat",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TOPIC_LEVEL_MISMATCH"
    mock_post.assert_not_called()
    assert_no_saved_chat()


def test_chat_requires_saved_study_level(client, monkeypatch):
    headers = authenticated_headers(client)

    # Simulate an older account without a saved study level.
    user = db.session.scalar(
        db.select(User).where(
            User.email == "chat.student@example.com",
        )
    )
    assert user is not None

    user.academic_level = None
    db.session.commit()

    mock_post = mock_maira_answer(monkeypatch, "Unused answer.")
    response = send_chat(client, headers)

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACADEMIC_LEVEL_REQUIRED"
    mock_post.assert_not_called()
    assert_no_saved_chat()


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_general_chat_uses_account_study_level(
    client,
    monkeypatch,
    academic_level,
):
    headers = authenticated_headers(
        client,
        academic_level=academic_level,
    )
    mock_post = mock_maira_answer(
        monkeypatch,
        "Here is a simple explanation.",
    )

    response = send_chat(
        client,
        headers,
        topic="General ICT",
    )

    assert response.status_code == 200
    mock_post.assert_called_once()

    prompt = mock_post.call_args.kwargs["json"]["query"]
    assert f"Academic level: {academic_level.upper()}" in prompt

    conversation_id = response.get_json()["session_id"]
    assert len(stored_messages(conversation_id)) == 2


@pytest.mark.parametrize("include_slug", [True, False])
def test_existing_chat_rechecks_topic_level(
    client,
    monkeypatch,
    include_slug,
):
    headers = authenticated_headers(client, academic_level="hsc")
    mock_post = mock_maira_answer(monkeypatch, "First answer.")

    topic = Topic(
        title="Existing Chat Topic",
        slug="existing-chat-topic",
        description="Topic for checking continued chat access.",
        display_order=100,
        subject="ict",
        academic_level="hsc",
    )
    db.session.add(topic)
    db.session.commit()

    first_response = send_chat(
        client,
        headers,
        topic=topic.title,
    )
    assert first_response.status_code == 200

    conversation_id = first_response.get_json()["session_id"]

    # Simulate a topic being reassigned to another study level.
    topic.academic_level = "ssc"
    db.session.commit()
    mock_post.reset_mock()

    payload = {
        "message": "Give another example.",
        "topic": topic.title,
        "response_language": "english",
        "session_id": conversation_id,
    }

    if include_slug:
        payload["topic_slug"] = topic.slug

    response = client.post(
        "/api/chat",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TOPIC_LEVEL_MISMATCH"
    mock_post.assert_not_called()

    messages = stored_messages(conversation_id)
    assert [(message.role, message.content) for message in messages] == [
        ("student", "What is binary?"),
        ("assistant", "First answer."),
    ]
    assert db.session.scalar(
        db.select(db.func.count()).select_from(ChatConversation)
    ) == 1