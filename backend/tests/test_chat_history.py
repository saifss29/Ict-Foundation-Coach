from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from extensions import db
from models.chat_conversation import ChatConversation
from models.chat_message import ChatMessage


BASE_URL = "/api/chat/conversations"


def create_account(client, *, email, role="student"):
    registration_data = {
        "name": "History Test User",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = "hsc"

    with patch(
        "services.email_verification_service.send_email"
    ) as mock_send_email:
        register_response = client.post(
            "/api/auth/register",
            json=registration_data,
        )

        assert register_response.status_code == 201
        mock_send_email.assert_called_once()

        user_id = register_response.get_json()["user"]["id"]
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

    token = login_response.get_json()["access_token"]

    return user_id, {"Authorization": f"Bearer {token}"}


def create_conversation(user_id, *, title="Binary practice"):
    conversation = ChatConversation(
        user_id=user_id,
        title=title,
        topic="Number Systems",
        response_language="english",
    )

    db.session.add(conversation)
    db.session.flush()

    return conversation


def add_message(conversation_id, *, role, content):
    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    db.session.add(message)
    db.session.flush()

    return message


@pytest.mark.parametrize(
    "path",
    [
        BASE_URL,
        f"{BASE_URL}/unknown",
    ],
)
def test_history_requires_login(client, path):
    response = client.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        BASE_URL,
        f"{BASE_URL}/unknown",
    ],
)
def test_teacher_cannot_access_student_chat_history(client, path):
    _, headers = create_account(
        client,
        email="teacher@example.com",
        role="teacher",
    )

    response = client.get(path, headers=headers)

    assert response.status_code == 403


def test_student_without_history_gets_empty_list(client):
    _, headers = create_account(
        client,
        email="student@example.com",
    )

    response = client.get(BASE_URL, headers=headers)

    assert response.status_code == 200

    data = response.get_json()

    assert data["conversations"] == []
    assert data["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 0,
        "has_next": False,
    }


def test_student_only_sees_own_conversations_in_recent_order(client):
    owner_id, owner_headers = create_account(
        client,
        email="owner@example.com",
    )
    other_id, _ = create_account(
        client,
        email="other@example.com",
    )

    older = create_conversation(owner_id, title="Older chat")
    newer = create_conversation(owner_id, title="Newer chat")
    create_conversation(other_id, title="Private other chat")

    now = datetime.now(timezone.utc)
    older.updated_at = now - timedelta(days=1)
    newer.updated_at = now

    db.session.commit()

    response = client.get(BASE_URL, headers=owner_headers)

    assert response.status_code == 200

    data = response.get_json()

    assert [
        conversation["id"]
        for conversation in data["conversations"]
    ] == [newer.id, older.id]

    assert data["pagination"]["total"] == 2


def test_student_can_read_own_messages_in_order(client):
    user_id, headers = create_account(
        client,
        email="student@example.com",
    )

    conversation = create_conversation(user_id)

    question = add_message(
        conversation.id,
        role="student",
        content="What is binary?",
    )
    answer = add_message(
        conversation.id,
        role="assistant",
        content="Binary uses 0 and 1.",
    )

    db.session.commit()

    response = client.get(
        f"{BASE_URL}/{conversation.id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["conversation"]["id"] == conversation.id
    assert data["conversation"]["topic"] == "Number Systems"
    assert data["conversation"]["response_language"] == "english"

    assert [
        (message["id"], message["role"], message["text"])
        for message in data["messages"]
    ] == [
        (question.id, "student", "What is binary?"),
        (answer.id, "assistant", "Binary uses 0 and 1."),
    ]

    assert data["pagination"]["total"] == 2
    assert data["pagination"]["has_next"] is False

    timestamp = datetime.fromisoformat(
        data["messages"][0]["created_at"]
    )
    assert timestamp.utcoffset() == timedelta(0)


def test_student_cannot_read_another_students_messages(client):
    owner_id, _ = create_account(
        client,
        email="owner@example.com",
    )
    _, other_headers = create_account(
        client,
        email="other@example.com",
    )

    conversation = create_conversation(owner_id)

    add_message(
        conversation.id,
        role="student",
        content="Private question",
    )

    db.session.commit()

    response = client.get(
        f"{BASE_URL}/{conversation.id}",
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "Conversation not found",
    }


def test_unknown_conversation_returns_404(client):
    _, headers = create_account(
        client,
        email="student@example.com",
    )

    response = client.get(
        f"{BASE_URL}/unknown",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "Conversation not found",
    }


def test_conversation_list_pagination(client):
    user_id, headers = create_account(
        client,
        email="student@example.com",
    )

    start = datetime.now(timezone.utc)
    conversation_ids = []

    for index in range(21):
        conversation = create_conversation(
            user_id,
            title=f"Chat {index}",
        )
        conversation.updated_at = start + timedelta(minutes=index)
        conversation_ids.append(conversation.id)

    db.session.commit()

    first_response = client.get(
        BASE_URL,
        headers=headers,
    )
    second_response = client.get(
        f"{BASE_URL}?page=2",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first = first_response.get_json()
    second = second_response.get_json()

    assert len(first["conversations"]) == 20
    assert len(second["conversations"]) == 1
    assert first["pagination"]["total"] == 21
    assert first["pagination"]["has_next"] is True
    assert second["pagination"]["has_next"] is False

    returned_ids = [
        conversation["id"]
        for conversation in (
            first["conversations"] + second["conversations"]
        )
    ]

    assert returned_ids == list(reversed(conversation_ids))


def test_message_pagination(client):
    user_id, headers = create_account(
        client,
        email="student@example.com",
    )
    conversation = create_conversation(user_id)

    for index in range(52):
        add_message(
            conversation.id,
            role="student" if index % 2 == 0 else "assistant",
            content=f"Message {index}",
        )

    db.session.commit()

    first_response = client.get(
        f"{BASE_URL}/{conversation.id}",
        headers=headers,
    )
    second_response = client.get(
        f"{BASE_URL}/{conversation.id}?page=2",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first = first_response.get_json()
    second = second_response.get_json()

    assert len(first["messages"]) == 50
    assert len(second["messages"]) == 2
    assert first["pagination"]["total"] == 52
    assert first["pagination"]["has_next"] is True
    assert second["pagination"]["has_next"] is False

    returned_texts = [
        message["text"]
        for message in first["messages"] + second["messages"]
    ]

    assert returned_texts == [
        f"Message {index}" for index in range(52)
    ]


@pytest.mark.parametrize("page", ["0", "-1", "abc", "1.5"])
@pytest.mark.parametrize("view", ["list", "messages"])
def test_history_rejects_invalid_page(client, page, view):
    user_id, headers = create_account(
        client,
        email="student@example.com",
    )

    path = BASE_URL

    if view == "messages":
        conversation = create_conversation(user_id)
        db.session.commit()
        path = f"{BASE_URL}/{conversation.id}"

    response = client.get(
        path,
        query_string={"page": page},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Page must be a positive integer"
    )


@pytest.mark.parametrize(
    "learning_mode",
    ["personal_growth", "exam_preparation"],
)
def test_history_returns_saved_learning_mode(client, learning_mode):
    user_id, headers = create_account(
        client,
        email="mode.student@example.com",
    )

    conversation = ChatConversation(
        user_id=user_id,
        title="Binary practice",
        topic="Number Systems",
        response_language="english",
        learning_mode=learning_mode,
    )

    db.session.add(conversation)
    db.session.flush()

    conversation_id = conversation.id

    add_message(
        conversation_id,
        role="student",
        content="What is binary?",
    )
    add_message(
        conversation_id,
        role="assistant",
        content="Binary uses 0 and 1.",
    )

    db.session.commit()
    db.session.expire_all()

    list_response = client.get(BASE_URL, headers=headers)

    assert list_response.status_code == 200

    conversations = list_response.get_json()["conversations"]

    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["learning_mode"] == learning_mode

    detail_response = client.get(
        f"{BASE_URL}/{conversation_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200

    detail = detail_response.get_json()

    assert detail["conversation"]["id"] == conversation_id
    assert detail["conversation"]["learning_mode"] == learning_mode
    assert [
        (message["role"], message["text"])
        for message in detail["messages"]
    ] == [
        ("student", "What is binary?"),
        ("assistant", "Binary uses 0 and 1."),
    ]


def test_history_returns_default_learning_mode(client):
    user_id, headers = create_account(
        client,
        email="default.student@example.com",
    )

    # Existing helper omits learning_mode.
    conversation = create_conversation(user_id)
    conversation_id = conversation.id

    db.session.commit()
    db.session.expire_all()

    list_response = client.get(BASE_URL, headers=headers)

    assert list_response.status_code == 200

    conversations = list_response.get_json()["conversations"]

    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["learning_mode"] == "personal_growth"

    detail_response = client.get(
        f"{BASE_URL}/{conversation_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert (
        detail_response.get_json()["conversation"]["learning_mode"]
        == "personal_growth"
    )