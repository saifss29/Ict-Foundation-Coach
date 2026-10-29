from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.calendar_event import CalendarEvent
from models.user import User
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_recipient import QuizAssignmentRecipient
from models.teacher_quiz import TeacherQuiz
from models.topic import Topic
from models.notification import Notification
from services.calendar_assistant_service import CalendarAssistantError
from models.calendar_event_create_request import CalendarEventCreateRequest

BASE_URL = "/api/calendar-events"

VISIBLE_RANGE = {
    "starts_at": "2026-10-01T00:00:00Z",
    "ends_at": "2026-11-01T00:00:00Z",
}


@pytest.fixture()
def event_payload():
    return {
        "title": "  Binary practice  ",
        "description": "  Practice conversions.  ",
        "starts_at": "2026-10-07T20:00:00+06:00",
        "ends_at": "2026-10-07T21:00:00+06:00",
        "timezone_name": "Asia/Dhaka",
    }


def create_calendar_account(client, app, role):
    registration_data = {
        "name": f"Calendar {role.title()}",
        "email": f"calendar-api-{role}@example.com",
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = "hsc"

    registered = client.post(
        "/api/auth/register",
        json=registration_data,
    )
    assert registered.status_code == 201
    user_id = registered.get_json()["user"]["id"]

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        user.is_email_verified = True
        db.session.commit()

    logged_in = client.post(
        "/api/auth/login",
        json={
            "email": f"calendar-api-{role}@example.com",
            "password": "SecurePass123!",
        },
    )
    assert logged_in.status_code == 200

    return {
        "id": user_id,
        "headers": {
            "Authorization": (
                f"Bearer {logged_in.get_json()['access_token']}"
            ),
        },
    }


@pytest.fixture()
def calendar_accounts(client, app):
    return {
        role: create_calendar_account(client, app, role)
        for role in ("student", "teacher")
    }


def save_event(client, account, payload):
    response = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )
    assert response.status_code == 201
    return response.get_json()["event"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", ""),
        ("GET", ""),
        ("GET", "/unknown"),
        ("PUT", "/unknown"),
        ("DELETE", "/unknown"),
    ],
)
def test_calendar_routes_require_login(client, method, path):
    response = client.open(
        BASE_URL + path,
        method=method,
        json={},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_both_roles_can_create_read_update_and_delete(
    client, app, calendar_accounts, event_payload, role
):
    account = calendar_accounts[role]
    event = save_event(client, account, event_payload)

    assert event["title"] == "Binary practice"
    assert event["description"] == "Practice conversions."
    assert event["starts_at"] == "2026-10-07T14:00:00+00:00"
    assert event["ends_at"] == "2026-10-07T15:00:00+00:00"
    assert event["timezone_name"] == "Asia/Dhaka"
    assert event["version"] == 1

    detail = client.get(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
    )
    assert detail.status_code == 200
    assert detail.get_json()["event"] == event

    updated = client.put(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
        json={
            **event_payload,
            "title": "ICT revision",
            "version": 1,
        },
    )
    assert updated.status_code == 200
    updated_event = updated.get_json()["event"]
    assert updated_event["title"] == "ICT revision"
    assert updated_event["version"] == 2

    with app.app_context():
        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.user_id == account["id"]
        assert saved.title == "ICT revision"
        assert saved.version == 2

    deleted = client.delete(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
        json={"version": 2},
    )
    assert deleted.status_code == 200

    missing = client.get(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
    )
    assert missing.status_code == 404


@pytest.mark.parametrize("owner_role", ["student", "teacher"])
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_calendar_blocks_cross_user_access(
    client, app, calendar_accounts, event_payload, owner_role, method
):
    owner = calendar_accounts[owner_role]
    other_role = "teacher" if owner_role == "student" else "student"
    other = calendar_accounts[other_role]
    event = save_event(client, owner, event_payload)

    body = (
        {"version": 1}
        if method == "DELETE"
        else {**event_payload, "title": "Unauthorized change", "version": 1}
    )

    response = client.open(
        f"{BASE_URL}/{event['id']}",
        method=method,
        headers=other["headers"],
        **({"json": body} if method != "GET" else {}),
    )
    assert response.status_code == 404

    with app.app_context():
        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.title == "Binary practice"
        assert saved.version == 1


def test_calendar_list_only_returns_owned_events(
    client, calendar_accounts, event_payload
):
    own = save_event(client, calendar_accounts["student"], event_payload)
    save_event(client, calendar_accounts["teacher"], event_payload)

    response = client.get(
        BASE_URL,
        headers=calendar_accounts["student"]["headers"],
        query_string=VISIBLE_RANGE,
    )
    assert response.status_code == 200
    assert [event["id"] for event in response.get_json()["events"]] == [
        own["id"]
    ]


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_calendar_rejects_stale_version_without_changes(
    client, calendar_accounts, event_payload, method
):
    account = calendar_accounts["student"]
    event = save_event(client, account, event_payload)

    response = client.put(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
        json={**event_payload, "title": "Latest title", "version": 1},
    )
    assert response.status_code == 200

    stale_body = (
        {"version": 1}
        if method == "DELETE"
        else {**event_payload, "title": "Stale title", "version": 1}
    )
    stale = client.open(
        f"{BASE_URL}/{event['id']}",
        method=method,
        headers=account["headers"],
        json=stale_body,
    )
    assert stale.status_code == 409

    detail = client.get(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
    )
    assert detail.status_code == 200
    assert detail.get_json()["event"]["title"] == "Latest title"
    assert detail.get_json()["event"]["version"] == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", " "),
        ("ends_at", "2026-10-07T19:00:00+06:00"),
        ("starts_at", "2026-10-07T20:00:00"),
        ("timezone_name", "Invalid/Timezone"),
        ("user_id", 999),
    ],
)
def test_calendar_create_rejects_invalid_input(
    client, app, calendar_accounts, event_payload, field, value
):
    response = client.post(
        BASE_URL,
        headers=calendar_accounts["student"]["headers"],
        json={**event_payload, field: value},
    )
    assert response.status_code == 400

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(CalendarEvent)
        ) == 0


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
@pytest.mark.parametrize("body", ["null", "[]", '"text"', "{invalid"])
def test_calendar_rejects_invalid_request_body(
    client, calendar_accounts, method, body
):
    path = BASE_URL if method == "POST" else f"{BASE_URL}/unknown"

    response = client.open(
        path,
        method=method,
        headers=calendar_accounts["student"]["headers"],
        data=body,
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_calendar_requires_version_for_mutation(
    client, calendar_accounts, event_payload, method
):
    account = calendar_accounts["student"]
    event = save_event(client, account, event_payload)

    response = client.open(
        f"{BASE_URL}/{event['id']}",
        method=method,
        headers=account["headers"],
        json=event_payload if method == "PUT" else {},
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "query",
    [
        {},
        {**VISIBLE_RANGE, "starts_at": "invalid"},
        {**VISIBLE_RANGE, "starts_at": "2026-10-01T00:00:00"},
        {**VISIBLE_RANGE, "ends_at": "2026-10-01T00:00:00Z"},
        {**VISIBLE_RANGE, "ends_at": "2026-09-01T00:00:00Z"},
        {**VISIBLE_RANGE, "ends_at": "2027-02-01T00:00:00Z"},
        {**VISIBLE_RANGE, "page": "0"},
        {**VISIBLE_RANGE, "page": "-1"},
        {**VISIBLE_RANGE, "page": "abc"},
        {**VISIBLE_RANGE, "page": "10001"},
    ],
)
def test_calendar_list_rejects_invalid_range_or_page(
    client, calendar_accounts, query
):
    response = client.get(
        BASE_URL,
        headers=calendar_accounts["student"]["headers"],
        query_string=query,
    )
    assert response.status_code == 400


def test_calendar_list_includes_overlaps_and_excludes_boundaries(
    client, calendar_accounts, event_payload
):
    account = calendar_accounts["student"]

    overlapping = save_event(
        client,
        account,
        {
            **event_payload,
            "starts_at": "2026-09-30T23:00:00Z",
            "ends_at": "2026-10-01T01:00:00Z",
        },
    )
    save_event(
        client,
        account,
        {
            **event_payload,
            "starts_at": "2026-09-30T23:00:00Z",
            "ends_at": "2026-10-01T00:00:00Z",
        },
    )
    save_event(
        client,
        account,
        {
            **event_payload,
            "starts_at": "2026-11-01T00:00:00Z",
            "ends_at": "2026-11-01T01:00:00Z",
        },
    )

    response = client.get(
        BASE_URL,
        headers=account["headers"],
        query_string=VISIBLE_RANGE,
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.get_json()["events"]] == [
        overlapping["id"]
    ]


def test_calendar_list_pagination(client, app, calendar_accounts):
    account = calendar_accounts["student"]

    with app.app_context():
        start = datetime(2026, 10, 7, tzinfo=timezone.utc)

        for index in range(101):
            db.session.add(
                CalendarEvent(
                    user_id=account["id"],
                    title=f"Event {index}",
                    starts_at=start + timedelta(minutes=index),
                    ends_at=start + timedelta(minutes=index + 1),
                    timezone_name="UTC",
                )
            )

        db.session.commit()

    pages = []

    for page in (1, 2, 3):
        response = client.get(
            BASE_URL,
            headers=account["headers"],
            query_string={**VISIBLE_RANGE, "page": page},
        )
        assert response.status_code == 200
        pages.append(response.get_json())

    assert len(pages[0]["events"]) == 100
    assert pages[0]["pagination"]["has_more"] is True
    assert len(pages[1]["events"]) == 1
    assert pages[1]["pagination"]["has_more"] is False
    assert pages[2]["events"] == []

    first_ids = {event["id"] for event in pages[0]["events"]}
    second_ids = {event["id"] for event in pages[1]["events"]}
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_calendar_commit_failure_rolls_back(
    client, app, calendar_accounts, event_payload, monkeypatch, method
):
    account = calendar_accounts["student"]
    event = (
        save_event(client, account, event_payload)
        if method != "POST"
        else None
    )

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test failure")),
        )

        path = BASE_URL if event is None else f"{BASE_URL}/{event['id']}"
        body = (
            event_payload
            if method == "POST"
            else {"version": 1}
            if method == "DELETE"
            else {**event_payload, "title": "Failed change", "version": 1}
        )

        response = client.open(
            path,
            method=method,
            headers=account["headers"],
            json=body,
        )

    assert response.status_code == 500

    with app.app_context():
        if event is None:
            assert db.session.scalar(
                db.select(db.func.count()).select_from(CalendarEvent)
            ) == 0
        else:
            saved = db.session.get(CalendarEvent, event["id"])
            assert saved is not None
            assert saved.title == "Binary practice"
            assert saved.version == 1


@pytest.fixture()
def calendar_assignment_setup(app, calendar_accounts):
    accounts = calendar_accounts

    with app.app_context():
        classroom = Classroom(
            name="Calendar ICT Class",
            teacher_id=accounts["teacher"]["id"],
            join_code="CALQUIZ1",
        )
        topic = Topic(
            title="Number Systems",
            slug="number-systems",
            description="Calendar assignment test topic.",
            display_order=1,
        )
        db.session.add_all([classroom, topic])
        db.session.flush()

        quiz = TeacherQuiz(
            teacher_id=accounts["teacher"]["id"],
            topic_id=topic.id,
            title="Calendar Quiz",
            response_language="english",
            questions=[
                {
                    "id": str(index),
                    "question_text": f"Question {index}",
                    "option_a": "2",
                    "option_b": "8",
                    "option_c": "10",
                    "option_d": "16",
                    "correct_option": "A",
                    "explanation": "Binary uses base 2.",
                }
                for index in range(1, 6)
            ],
        )
        quiz.status = "published"
        quiz.published_at = datetime.now(timezone.utc)
        db.session.add(quiz)
        db.session.flush()

        assignment = QuizAssignment(
            quiz_id=quiz.id,
            classroom_id=classroom.id,
            audience="selected",
            available_at=datetime(2026, 10, 7, 14, tzinfo=timezone.utc),
            deadline_at=datetime(2026, 10, 8, 14, tzinfo=timezone.utc),
            review_at=datetime(2026, 10, 8, 15, tzinfo=timezone.utc),
            time_limit_minutes=30,
            max_attempts=2,
        )
        db.session.add(assignment)
        db.session.flush()

        db.session.add_all([
            ClassMembership(
                classroom_id=classroom.id,
                student_id=accounts["student"]["id"],
            ),
            QuizAssignmentRecipient(
                assignment_id=assignment.id,
                student_id=accounts["student"]["id"],
            ),
        ])
        db.session.commit()

        return {
            "accounts": accounts,
            "assignment_id": assignment.id,
            "quiz_id": quiz.id,
            "classroom_id": classroom.id,
        }


def get_calendar_assignments(
    client, setup, *, role="student", query=None
):
    return client.get(
        f"{BASE_URL}/assignments",
        headers=setup["accounts"][role]["headers"],
        query_string=VISIBLE_RANGE if query is None else query,
    )


def test_calendar_assignments_require_login(client):
    response = client.get(
        f"{BASE_URL}/assignments",
        query_string=VISIBLE_RANGE,
    )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_calendar_assignments_return_authorized_schedule(
    client, calendar_assignment_setup, role
):
    setup = calendar_assignment_setup
    response = get_calendar_assignments(client, setup, role=role)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["assignments"]) == 1

    item = data["assignments"][0]
    assert item["id"] == setup["assignment_id"]
    assert item["assignment_id"] == setup["assignment_id"]
    assert item["title"] == "Calendar Quiz"
    assert item["classroom_name"] == "Calendar ICT Class"
    assert item["kind"] == "quiz_assignment"
    assert item["read_only"] is True
    assert item["question_count"] == 5
    assert item["starts_at"] == "2026-10-07T14:00:00+00:00"
    assert item["ends_at"] == "2026-10-08T14:00:00+00:00"
    assert item["review_at"] == "2026-10-08T15:00:00+00:00"
    assert item["time_limit_minutes"] == 30
    assert item["max_attempts"] == 2

    assert not {
        "questions", "answers", "correct_option",
        "explanation", "students", "score",
    }.intersection(item)

    assert data["pagination"] == {
        "page": 1,
        "page_size": 100,
        "has_more": False,
    }


def test_calendar_membership_without_recipient_grants_no_access(
    client, app, calendar_assignment_setup
):
    setup = calendar_assignment_setup

    with app.app_context():
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id
                == setup["assignment_id"],
                QuizAssignmentRecipient.student_id
                == setup["accounts"]["student"]["id"],
            )
        )
        assert recipient is not None
        db.session.delete(recipient)
        db.session.commit()

    response = get_calendar_assignments(client, setup)

    assert response.status_code == 200
    assert response.get_json()["assignments"] == []


def test_calendar_recipient_retains_schedule_after_leaving_class(
    client, app, calendar_assignment_setup
):
    setup = calendar_assignment_setup

    with app.app_context():
        membership = db.session.scalar(
            db.select(ClassMembership).where(
                ClassMembership.classroom_id == setup["classroom_id"],
                ClassMembership.student_id
                == setup["accounts"]["student"]["id"],
            )
        )
        assert membership is not None
        db.session.delete(membership)
        db.session.commit()

    response = get_calendar_assignments(client, setup)

    assert response.status_code == 200
    assert [item["id"] for item in response.get_json()["assignments"]] == [
        setup["assignment_id"]
    ]


@pytest.mark.parametrize("owner_type", ["quiz", "classroom"])
def test_calendar_teacher_requires_both_ownership_checks(
    client, app, calendar_assignment_setup, owner_type
):
    setup = calendar_assignment_setup

    # Test each ownership predicate independently by changing its owner ID.
    with app.app_context():
        if owner_type == "quiz":
            item = db.session.get(TeacherQuiz, setup["quiz_id"])
        else:
            item = db.session.get(Classroom, setup["classroom_id"])

        assert item is not None
        item.teacher_id = setup["accounts"]["student"]["id"]
        db.session.commit()

    response = get_calendar_assignments(client, setup, role="teacher")

    assert response.status_code == 200
    assert response.get_json()["assignments"] == []


@pytest.mark.parametrize(
    ("start", "end", "expected_count"),
    [
        # Visible range is inside the assignment window.
        ("2026-10-07T15:00:00Z", "2026-10-07T16:00:00Z", 1),
        # Assignment starts exactly at the range end.
        ("2026-10-07T13:00:00Z", "2026-10-07T14:00:00Z", 0),
        # Assignment ends exactly at the range start.
        ("2026-10-08T14:00:00Z", "2026-10-08T15:00:00Z", 0),
        # Equivalent +06:00 local range.
        ("2026-10-07T20:00:00+06:00", "2026-10-07T21:00:00+06:00", 1),
    ],
)
def test_calendar_assignment_range_overlap(
    client, calendar_assignment_setup, start, end, expected_count
):
    response = get_calendar_assignments(
        client,
        calendar_assignment_setup,
        query={"starts_at": start, "ends_at": end},
    )

    assert response.status_code == 200
    assert len(response.get_json()["assignments"]) == expected_count


@pytest.mark.parametrize(
    "query",
    [
        {},
        {**VISIBLE_RANGE, "starts_at": "invalid"},
        {**VISIBLE_RANGE, "starts_at": "2026-10-01T00:00:00"},
        {**VISIBLE_RANGE, "ends_at": "2026-10-01T00:00:00Z"},
        {**VISIBLE_RANGE, "ends_at": "2026-09-01T00:00:00Z"},
        {**VISIBLE_RANGE, "ends_at": "2027-02-01T00:00:00Z"},
        {**VISIBLE_RANGE, "page": "0"},
        {**VISIBLE_RANGE, "page": "-1"},
        {**VISIBLE_RANGE, "page": "abc"},
        {**VISIBLE_RANGE, "page": "10001"},
    ],
)
def test_calendar_assignments_reject_invalid_query(
    client, calendar_assignment_setup, query
):
    response = get_calendar_assignments(
        client, calendar_assignment_setup, query=query
    )
    assert response.status_code == 400


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_calendar_assignments_paginate_without_duplicates(
    client, app, calendar_assignment_setup, role
):
    setup = calendar_assignment_setup

    with app.app_context():
        start = datetime(2026, 10, 7, 14, tzinfo=timezone.utc)

        # The fixture already contains one assignment.
        for index in range(100):
            assignment = QuizAssignment(
                quiz_id=setup["quiz_id"],
                classroom_id=setup["classroom_id"],
                audience="selected",
                available_at=start + timedelta(minutes=index + 1),
                deadline_at=start + timedelta(days=1),
                review_at=start + timedelta(days=1, hours=1),
                time_limit_minutes=30,
                max_attempts=1,
            )
            db.session.add(assignment)
            db.session.flush()

            db.session.add(
                QuizAssignmentRecipient(
                    assignment_id=assignment.id,
                    student_id=setup["accounts"]["student"]["id"],
                )
            )

        db.session.commit()

    pages = []

    for page in (1, 2, 3):
        response = get_calendar_assignments(
            client,
            setup,
            role=role,
            query={**VISIBLE_RANGE, "page": page},
        )
        assert response.status_code == 200
        pages.append(response.get_json())

    assert len(pages[0]["assignments"]) == 100
    assert pages[0]["pagination"]["has_more"] is True
    assert len(pages[1]["assignments"]) == 1
    assert pages[1]["pagination"]["has_more"] is False
    assert pages[2]["assignments"] == []

    first_ids = {item["id"] for item in pages[0]["assignments"]}
    second_ids = {item["id"] for item in pages[1]["assignments"]}
    assert first_ids.isdisjoint(second_ids)


def test_calendar_schedule_does_not_create_personal_event_copies(
    client, app, calendar_assignment_setup
):
    setup = calendar_assignment_setup

    for _ in range(2):
        response = get_calendar_assignments(client, setup)
        assert response.status_code == 200

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(CalendarEvent)
        ) == 0


def test_calendar_assignment_id_cannot_be_deleted_as_personal_event(
    client, app, calendar_assignment_setup
):
    setup = calendar_assignment_setup

    response = client.delete(
        f"{BASE_URL}/{setup['assignment_id']}",
        headers=setup["accounts"]["student"]["headers"],
        json={"version": 1},
    )
    assert response.status_code == 404

    with app.app_context():
        assert db.session.get(
            QuizAssignment, setup["assignment_id"]
        ) is not None


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_calendar_notifications_reach_only_event_owner(
    client, calendar_accounts, event_payload, role
):
    owner = calendar_accounts[role]
    other_role = "teacher" if role == "student" else "student"
    other = calendar_accounts[other_role]

    event = save_event(client, owner, event_payload)

    created_list = client.get(
        "/api/notifications",
        headers=owner["headers"],
    )
    assert created_list.status_code == 200

    created_data = created_list.get_json()
    assert created_data["unread_count"] == 1
    assert len(created_data["notifications"]) == 1

    notification = created_data["notifications"][0]
    assert notification["notification_type"] == "calendar_event_created"
    assert notification["title"] == "Calendar event created"
    assert notification["message"] == (
        'You added "Binary practice" to your calendar.'
    )
    assert notification["is_read"] is False

    updated = client.put(
        f"{BASE_URL}/{event['id']}",
        headers=owner["headers"],
        json={
            **event_payload,
            "title": "ICT revision",
            "version": 1,
        },
    )
    assert updated.status_code == 200

    updated_list = client.get(
        "/api/notifications",
        headers=owner["headers"],
    )
    assert updated_list.status_code == 200

    updated_data = updated_list.get_json()
    assert updated_data["unread_count"] == 2
    assert len(updated_data["notifications"]) == 2

    updates = [
        item
        for item in updated_data["notifications"]
        if item["notification_type"] == "calendar_event_updated"
    ]
    assert len(updates) == 1
    assert updates[0]["title"] == "Calendar event updated"
    assert updates[0]["message"] == (
        'You updated "ICT revision" in your calendar.'
    )
    assert updates[0]["is_read"] is False

    unread = client.get(
        "/api/notifications/unread-count",
        headers=owner["headers"],
    )
    assert unread.status_code == 200
    assert unread.get_json()["unread_count"] == 2

    other_list = client.get(
        "/api/notifications",
        headers=other["headers"],
    )
    assert other_list.status_code == 200
    assert other_list.get_json()["notifications"] == []
    assert other_list.get_json()["unread_count"] == 0


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        ("invalid", 400),
        ("stale", 409),
        ("other_user", 404),
    ],
)
def test_rejected_calendar_update_creates_no_notification(
    client, app, calendar_accounts, event_payload,
    failure, expected_status
):
    owner = calendar_accounts["student"]
    event = save_event(client, owner, event_payload)

    body = {
        **event_payload,
        "title": "Rejected change",
        "version": 1,
    }
    account = owner

    if failure == "invalid":
        body["title"] = " "
    elif failure == "stale":
        body["version"] = 2
    else:
        account = calendar_accounts["teacher"]

    response = client.put(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
        json=body,
    )
    assert response.status_code == expected_status

    with app.app_context():
        notifications = db.session.scalars(
            db.select(Notification)
        ).all()

        # Only the successful creation notification remains.
        assert len(notifications) == 1
        assert notifications[0].user_id == owner["id"]
        assert (
            notifications[0].notification_type
            == "calendar_event_created"
        )

        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.title == "Binary practice"
        assert saved.version == 1


@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_calendar_failure_rolls_back_event_and_notification(
    client, app, calendar_accounts, event_payload,
    monkeypatch, method
):
    owner = calendar_accounts["student"]
    event = (
        save_event(client, owner, event_payload)
        if method == "PUT"
        else None
    )

    # Flush pending notifications before simulating a commit failure.
    # This checks rollback of actual database writes too.
    real_flush = db.session.flush

    def fail_commit():
        real_flush()
        raise SQLAlchemyError("Test transaction failure")

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)

        if event is None:
            response = client.post(
                BASE_URL,
                headers=owner["headers"],
                json=event_payload,
            )
        else:
            response = client.put(
                f"{BASE_URL}/{event['id']}",
                headers=owner["headers"],
                json={
                    **event_payload,
                    "title": "Failed change",
                    "version": 1,
                },
            )

    assert response.status_code == 500

    with app.app_context():
        notifications = db.session.scalars(
            db.select(Notification)
        ).all()

        if event is None:
            assert notifications == []
            assert db.session.scalar(
                db.select(db.func.count()).select_from(CalendarEvent)
            ) == 0
        else:
            assert len(notifications) == 1
            assert (
                notifications[0].notification_type
                == "calendar_event_created"
            )

            saved = db.session.get(CalendarEvent, event["id"])
            assert saved is not None
            assert saved.title == "Binary practice"
            assert saved.version == 1

@pytest.fixture()
def assistant_draft():
    return {
        "status": "draft",
        "event": {
            "title": "Math practice",
            "description": "Practice algebra.",
            "starts_at": "2026-10-07T14:00:00+00:00",
            "ends_at": "2026-10-07T15:00:00+00:00",
            "timezone_name": "Asia/Dhaka",
        },
    }


def test_calendar_assistant_requires_login(client, monkeypatch):
    generate = Mock()
    monkeypatch.setattr(
        "routes.calendar_events.generate_calendar_proposal",
        generate,
    )

    response = client.post(f"{BASE_URL}/assistant", json={})

    assert response.status_code == 401
    generate.assert_not_called()


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_calendar_assistant_create_returns_preview_without_saving(
    client, app, calendar_accounts, assistant_draft, monkeypatch, role
):
    generate = Mock(return_value=assistant_draft)
    monkeypatch.setattr(
        "routes.calendar_events.generate_calendar_proposal",
        generate,
    )

    response = client.post(
        f"{BASE_URL}/assistant",
        headers=calendar_accounts[role]["headers"],
        json={
            "message": "  Kalke Math practice  ",
            "timezone_name": "Asia/Dhaka",
            "action": "create",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "action": "create",
        "event_id": None,
        "version": None,
        "proposal": assistant_draft,
    }
    generate.assert_called_once_with(
        message="Kalke Math practice",
        timezone_name="Asia/Dhaka",
        action="create",
        selected_event=None,
    )

    with app.app_context():
        for model in (CalendarEvent, Notification):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 0


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_calendar_assistant_update_preserves_saved_event(
    client, app, calendar_accounts, event_payload,
    assistant_draft, monkeypatch, role
):
    account = calendar_accounts[role]
    event = save_event(client, account, event_payload)

    generate = Mock(return_value=assistant_draft)
    monkeypatch.setattr(
        "routes.calendar_events.generate_calendar_proposal",
        generate,
    )

    response = client.post(
        f"{BASE_URL}/assistant",
        headers=account["headers"],
        json={
            "message": "Title Math practice koro",
            "timezone_name": "Asia/Dhaka",
            "action": "update",
            "event_id": event["id"],
            "version": 1,
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "action": "update",
        "event_id": event["id"],
        "version": 1,
        "proposal": assistant_draft,
    }
    generate.assert_called_once_with(
        message="Title Math practice koro",
        timezone_name="Asia/Dhaka",
        action="update",
        selected_event=event,
    )

    with app.app_context():
        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.title == "Binary practice"
        assert saved.version == 1

        # Only the original event creation notification exists.
        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 1


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        ("other_user", 404),
        ("missing", 404),
        ("stale", 409),
    ],
)
def test_calendar_assistant_rejects_inaccessible_or_stale_target(
    client, calendar_accounts, event_payload,
    monkeypatch, failure, expected_status
):
    owner = calendar_accounts["student"]
    event = save_event(client, owner, event_payload)
    account = owner
    event_id = event["id"]
    version = 1

    if failure == "other_user":
        account = calendar_accounts["teacher"]
    elif failure == "missing":
        event_id = "d7ef2cb8-f749-4f75-90ed-73cb94f37896"
    else:
        version = 2

    generate = Mock()
    monkeypatch.setattr(
        "routes.calendar_events.generate_calendar_proposal",
        generate,
    )

    response = client.post(
        f"{BASE_URL}/assistant",
        headers=account["headers"],
        json={
            "message": "Update event",
            "timezone_name": "Asia/Dhaka",
            "action": "update",
            "event_id": event_id,
            "version": version,
        },
    )

    assert response.status_code == expected_status
    generate.assert_not_called()


@pytest.mark.parametrize("status_code", [500, 502, 504])
def test_calendar_assistant_handles_service_failure_without_saving(
    client, app, calendar_accounts, monkeypatch, status_code
):
    generate = Mock(
        side_effect=CalendarAssistantError(
            "Calendar service failed.",
            status_code=status_code,
        )
    )
    monkeypatch.setattr(
        "routes.calendar_events.generate_calendar_proposal",
        generate,
    )

    response = client.post(
        f"{BASE_URL}/assistant",
        headers=calendar_accounts["student"]["headers"],
        json={
            "message": "Create event",
            "timezone_name": "Asia/Dhaka",
            "action": "create",
        },
    )

    assert response.status_code == status_code
    assert response.get_json()["error"] == "Calendar service failed."

    with app.app_context():
        for model in (CalendarEvent, Notification):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 0


def test_calendar_assistant_returns_clarification(
    client, calendar_accounts, monkeypatch
):
    proposal = {
        "status": "needs_clarification",
        "question": "Koytay shuru ar shesh korte chao?",
    }
    monkeypatch.setattr(
        "routes.calendar_events.generate_calendar_proposal",
        Mock(return_value=proposal),
    )

    response = client.post(
        f"{BASE_URL}/assistant",
        headers=calendar_accounts["student"]["headers"],
        json={
            "message": "Math practice-er event banao",
            "timezone_name": "Asia/Dhaka",
            "action": "create",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["proposal"] == proposal

@pytest.mark.parametrize("role", ["student", "teacher"])
def test_calendar_create_retry_returns_same_event(
    client, app, calendar_accounts, event_payload, role
):
    account = calendar_accounts[role]
    payload = {
        **event_payload,
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
    }

    first = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )
    retry = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.get_json() == first.get_json()

    with app.app_context():
        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 1

        record = db.session.get(
            CalendarEventCreateRequest,
            (account["id"], payload["request_id"]),
        )
        assert record is not None
        assert record.response_data == first.get_json()
        assert len(record.request_hash) == 64


def test_calendar_create_retry_accepts_equivalent_normalized_input(
    client, app, calendar_accounts, event_payload
):
    account = calendar_accounts["student"]
    payload = {
        **event_payload,
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
    }

    first = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )
    assert first.status_code == 201

    retry = client.post(
        BASE_URL,
        headers=account["headers"],
        json={
            **payload,
            "title": "Binary practice",
            "description": "Practice conversions.",
            "starts_at": "2026-10-07T14:00:00Z",
            "ends_at": "2026-10-07T15:00:00Z",
        },
    )

    assert retry.status_code == 201
    assert retry.get_json() == first.get_json()

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(CalendarEvent)
        ) == 1


def test_calendar_create_rejects_reused_id_with_changed_details(
    client, app, calendar_accounts, event_payload
):
    account = calendar_accounts["student"]
    payload = {
        **event_payload,
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    original = save_event(client, account, payload)

    conflict = client.post(
        BASE_URL,
        headers=account["headers"],
        json={**payload, "title": "Different event"},
    )

    assert conflict.status_code == 409

    with app.app_context():
        saved = db.session.get(CalendarEvent, original["id"])
        assert saved is not None
        assert saved.title == "Binary practice"

        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 1


def test_calendar_create_request_ids_are_scoped_to_each_user(
    client, app, calendar_accounts, event_payload
):
    payload = {
        **event_payload,
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
    }

    student_event = save_event(
        client, calendar_accounts["student"], payload
    )
    teacher_event = save_event(
        client, calendar_accounts["teacher"], payload
    )

    assert student_event["id"] != teacher_event["id"]

    with app.app_context():
        for role, event in (
            ("student", student_event),
            ("teacher", teacher_event),
        ):
            account = calendar_accounts[role]
            record = db.session.get(
                CalendarEventCreateRequest,
                (account["id"], payload["request_id"]),
            )
            assert record is not None
            assert record.response_data["event"]["id"] == event["id"]

        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 2


def test_calendar_create_new_request_id_allows_new_event(
    client, app, calendar_accounts, event_payload
):
    account = calendar_accounts["student"]

    first = save_event(
        client,
        account,
        {
            **event_payload,
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
        },
    )
    second = save_event(
        client,
        account,
        {
            **event_payload,
            "request_id": "550e8400-e29b-41d4-a716-446655440001",
        },
    )

    assert first["id"] != second["id"]

    with app.app_context():
        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 2


@pytest.mark.parametrize("request_id", ["invalid", "", None])
def test_calendar_create_rejects_invalid_request_id(
    client, app, calendar_accounts, event_payload, request_id
):
    response = client.post(
        BASE_URL,
        headers=calendar_accounts["student"]["headers"],
        json={**event_payload, "request_id": request_id},
    )

    assert response.status_code == 400

    with app.app_context():
        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 0


def test_calendar_create_failure_rolls_back_request_record(
    client, app, calendar_accounts, event_payload, monkeypatch
):
    account = calendar_accounts["student"]
    payload = {
        **event_payload,
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
    }

    real_flush = db.session.flush

    def fail_commit():
        real_flush()
        raise SQLAlchemyError("Test transaction failure")

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)

        failed = client.post(
            BASE_URL,
            headers=account["headers"],
            json=payload,
        )

    assert failed.status_code == 500

    with app.app_context():
        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 0

    # A failed transaction must not block a successful retry.
    retry = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )
    assert retry.status_code == 201

    with app.app_context():
        for model in (
            CalendarEvent,
            Notification,
            CalendarEventCreateRequest,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 1


def test_calendar_create_retry_does_not_recreate_deleted_event(
    client, app, calendar_accounts, event_payload
):
    account = calendar_accounts["student"]
    payload = {
        **event_payload,
        "request_id": "550e8400-e29b-41d4-a716-446655440000",
    }

    first = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )
    assert first.status_code == 201
    event = first.get_json()["event"]

    deleted = client.delete(
        f"{BASE_URL}/{event['id']}",
        headers=account["headers"],
        json={"version": event["version"]},
    )
    assert deleted.status_code == 200

    retry = client.post(
        BASE_URL,
        headers=account["headers"],
        json=payload,
    )
    assert retry.status_code == 201
    assert retry.get_json() == first.get_json()

    with app.app_context():
        assert db.session.get(CalendarEvent, event["id"]) is None

        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 1

        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                CalendarEventCreateRequest
            )
        ) == 1