from extensions import db
from models.direct_message import DirectMessage
from models.notification import Notification
from models.user import User


def create_account(client, app, *, role, email):
    registration_data = {
        "name": f"Test {role.title()}",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = "hsc"

    response = client.post(
        "/api/auth/register",
        json=registration_data,
    )

    assert response.status_code == 201
    user_id = response.get_json()["user"]["id"]

    # Verify the test account without sending a real email.
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        user.is_email_verified = True
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 200

    return {
        "id": user_id,
        "headers": {
            "Authorization": (
                f"Bearer {response.get_json()['access_token']}"
            ),
        },
    }

def create_pair(client, app):
    teacher = create_account(
        client,
        app,
        role="teacher",
        email="message.teacher@example.com",
    )
    student = create_account(
        client,
        app,
        role="student",
        email="message.student@example.com",
    )

    response = client.post(
        "/api/messages/conversations",
        headers=student["headers"],
        json={"recipient_id": teacher["id"]},
    )

    assert response.status_code == 201

    return teacher, student, response.get_json()["conversation"]["id"]


def send_message(client, account, conversation_id, content):
    return client.post(
        f"/api/messages/conversations/{conversation_id}/messages",
        headers=account["headers"],
        json={"content": content},
    )


def test_direct_messages_require_login(client):
    response = client.get("/api/messages/conversations")

    assert response.status_code == 401


def test_student_can_contact_teacher_without_joining_class(client, app):
    teacher, student, conversation_id = create_pair(client, app)

    # No classroom or membership was created.
    response = client.get(
        "/api/messages/conversations",
        headers=student["headers"],
    )

    assert response.status_code == 200
    conversations = response.get_json()["conversations"]

    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["other_user"]["id"] == teacher["id"]

    # Starting the same conversation returns the existing one.
    response = client.post(
        "/api/messages/conversations",
        headers=student["headers"],
        json={"recipient_id": teacher["id"]},
    )

    assert response.status_code == 200
    assert response.get_json()["conversation"]["id"] == conversation_id


def test_message_is_saved_and_notifies_only_recipient(client, app):
    teacher, student, conversation_id = create_pair(client, app)

    response = send_message(
        client,
        student,
        conversation_id,
        "  Sir, binary conversion bujhte help lagbe.  ",
    )

    assert response.status_code == 201
    message = response.get_json()["message"]

    assert message["content"] == (
        "Sir, binary conversion bujhte help lagbe."
    )
    assert message["sender_id"] == student["id"]

    with app.app_context():
        saved_message = db.session.get(DirectMessage, message["id"])
        assert saved_message is not None
        assert saved_message.conversation_id == conversation_id

        notifications = db.session.scalars(
            db.select(Notification).where(
                Notification.direct_message_id == message["id"]
            )
        ).all()

        assert len(notifications) == 1
        assert notifications[0].user_id == teacher["id"]
        assert notifications[0].notification_type == "direct_message"
        assert notifications[0].read_at is None


def test_teacher_can_reply_and_messages_are_in_order(client, app):
    teacher, student, conversation_id = create_pair(client, app)

    first_response = send_message(
        client, student, conversation_id, "Sir, help lagbe."
    )
    second_response = send_message(
        client, teacher, conversation_id, "Kon part bujhte problem?"
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    response = client.get(
        f"/api/messages/conversations/{conversation_id}/messages",
        headers=student["headers"],
    )

    assert response.status_code == 200
    messages = response.get_json()["messages"]

    assert [message["content"] for message in messages] == [
        "Sir, help lagbe.",
        "Kon part bujhte problem?",
    ]
    assert messages[0]["is_mine"] is True
    assert messages[1]["is_mine"] is False

    reply_id = second_response.get_json()["message"]["id"]

    with app.app_context():
        notification = db.session.scalar(
            db.select(Notification).where(
                Notification.direct_message_id == reply_id
            )
        )

        assert notification is not None
        assert notification.user_id == student["id"]


def test_outsider_cannot_read_send_or_mark_conversation_read(client, app):
    _, _, conversation_id = create_pair(client, app)

    outsider = create_account(
        client,
        app,
        role="student",
        email="outsider@example.com",
    )

    response = client.get(
        f"/api/messages/conversations/{conversation_id}/messages",
        headers=outsider["headers"],
    )
    assert response.status_code == 404

    response = send_message(
        client, outsider, conversation_id, "Unauthorized message"
    )
    assert response.status_code == 404

    response = client.patch(
        f"/api/messages/conversations/{conversation_id}/read",
        headers=outsider["headers"],
        json={"last_message_id": 1},
    )
    assert response.status_code == 404


def test_read_boundary_preserves_newer_unread_message(client, app):
    teacher, student, conversation_id = create_pair(client, app)

    first_response = send_message(
        client, student, conversation_id, "First question"
    )
    second_response = send_message(
        client, student, conversation_id, "Second question"
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_id = first_response.get_json()["message"]["id"]
    second_id = second_response.get_json()["message"]["id"]

    response = client.patch(
        f"/api/messages/conversations/{conversation_id}/read",
        headers=teacher["headers"],
        json={"last_message_id": first_id},
    )

    assert response.status_code == 200
    assert response.get_json()["unread_count"] == 1

    with app.app_context():
        first_message = db.session.get(DirectMessage, first_id)
        second_message = db.session.get(DirectMessage, second_id)

        assert first_message is not None
        assert second_message is not None
        assert first_message.read_at is not None
        assert second_message.read_at is None

        first_notification = db.session.scalar(
            db.select(Notification).where(
                Notification.direct_message_id == first_id
            )
        )
        second_notification = db.session.scalar(
            db.select(Notification).where(
                Notification.direct_message_id == second_id
            )
        )

        assert first_notification is not None
        assert second_notification is not None
        assert first_notification.read_at is not None
        assert second_notification.read_at is None


def test_message_notification_contains_correct_conversation_id(client, app):
    teacher, student, conversation_id = create_pair(client, app)

    response = send_message(
        client,
        student,
        conversation_id,
        "Sir, binary niye ekta question ache.",
    )

    assert response.status_code == 201
    message_id = response.get_json()["message"]["id"]

    response = client.get(
        "/api/notifications",
        headers=teacher["headers"],
    )

    assert response.status_code == 200
    notifications = response.get_json()["notifications"]

    assert len(notifications) == 1
    notification = notifications[0]

    assert notification["notification_type"] == "direct_message"
    assert notification["direct_message_id"] == message_id
    assert notification["conversation_id"] == conversation_id
    assert notification["feedback_id"] is None

    response = client.patch(
        f"/api/notifications/{notification['id']}/read",
        headers=teacher["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["notification"]["conversation_id"] == (
        conversation_id
    )
    assert response.get_json()["notification"]["is_read"] is True

    # Reading the bell notification does not mark the chat message read.
    with app.app_context():
        message = db.session.get(DirectMessage, message_id)
        assert message is not None
        assert message.read_at is None