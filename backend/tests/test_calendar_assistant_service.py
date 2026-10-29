import json

import pytest

from unittest.mock import Mock

import requests
import json
from unittest.mock import Mock

import pytest
import requests

from services.calendar_assistant_service import (
    CalendarAssistantError,
    generate_calendar_proposal,
    parse_calendar_proposal,
)

@pytest.fixture()
def draft_payload():
    return {
        "status": "draft",
        "event": {
            "title": "  Math practice  ",
            "description": "  Practice algebra.  ",
            "starts_at": "2026-10-07T20:00:00+06:00",
            "ends_at": "2026-10-07T21:00:00+06:00",
            "timezone_name": "Asia/Dhaka",
        },
    }


def test_parser_accepts_and_normalizes_draft(draft_payload):
    result = parse_calendar_proposal(
        json.dumps(draft_payload),
        "Asia/Dhaka",
    )

    assert result == {
        "status": "draft",
        "event": {
            "title": "Math practice",
            "description": "Practice algebra.",
            "starts_at": "2026-10-07T14:00:00+00:00",
            "ends_at": "2026-10-07T15:00:00+00:00",
            "timezone_name": "Asia/Dhaka",
        },
    }


@pytest.mark.parametrize("opening", ["```", "```json"])
def test_parser_accepts_complete_json_code_block(draft_payload, opening):
    answer = f"{opening}\n{json.dumps(draft_payload)}\n```"

    assert parse_calendar_proposal(
        answer, "Asia/Dhaka"
    )["status"] == "draft"


def test_parser_accepts_clarification():
    result = parse_calendar_proposal(
        json.dumps({
            "status": "needs_clarification",
            "question": "  Koytay shuru korte chao?  ",
        }),
        "Asia/Dhaka",
    )

    assert result == {
        "status": "needs_clarification",
        "question": "Koytay shuru korte chao?",
    }


@pytest.mark.parametrize(
    "answer",
    [
        "Not JSON",
        "",
        "```json\n{}\n",
        "```python\n{}\n```",
        "```",
    ],
)
def test_parser_rejects_invalid_json_or_code_block(answer):
    with pytest.raises(CalendarAssistantError):
        parse_calendar_proposal(answer, "Asia/Dhaka")


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "text",
        {},
        {"status": "saved"},
        {"status": "draft"},
        {"status": "draft", "event": []},
        {"status": "needs_clarification"},
        {"status": "needs_clarification", "question": None},
        {"status": "needs_clarification", "question": " "},
        {"status": "needs_clarification", "question": "A" * 501},
        {
            "status": "needs_clarification",
            "question": "When?",
            "user_id": 999,
        },
    ],
)
def test_parser_rejects_invalid_response_structure(payload):
    with pytest.raises(CalendarAssistantError):
        parse_calendar_proposal(json.dumps(payload), "Asia/Dhaka")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", " "),
        ("title", "A" * 151),
        ("description", "A" * 2001),
        ("starts_at", "invalid"),
        ("starts_at", "2026-10-07T20:00:00"),
        ("ends_at", "2026-10-07T20:00:00+06:00"),
        ("ends_at", "2026-10-07T19:00:00+06:00"),
        ("timezone_name", "Invalid/Timezone"),
        ("timezone_name", "UTC"),
        ("user_id", 999),
    ],
)
def test_parser_rejects_invalid_event_details(
    draft_payload, field, value
):
    draft_payload["event"][field] = value

    with pytest.raises(CalendarAssistantError):
        parse_calendar_proposal(
            json.dumps(draft_payload),
            "Asia/Dhaka",
        )


def test_parser_rejects_missing_event_field(draft_payload):
    del draft_payload["event"]["description"]

    with pytest.raises(CalendarAssistantError):
        parse_calendar_proposal(json.dumps(draft_payload), "Asia/Dhaka")


def test_parser_rejects_extra_top_level_field(draft_payload):
    draft_payload["event_id"] = "unexpected"

    with pytest.raises(CalendarAssistantError):
        parse_calendar_proposal(json.dumps(draft_payload), "Asia/Dhaka")



@pytest.fixture()
def calendar_maira_settings(monkeypatch):
    settings = {
        "MAIRA_API_KEY": "test-api-key",
        "MAIRA_PROJECT_KEY": "test-project-key",
        "MAIRA_ASK_URL": "https://example.com/ask",
        "MAIRA_CALENDAR_GPT_PROFILE_ID": "calendar-profile",
        "MAIRA_MEMBER_ID": "test-member",
        "MAIRA_USER_ID": "test-user",
        "MAIRA_USER_NAME": "Test User",
    }

    for name, value in settings.items():
        monkeypatch.setenv(name, value)


def test_generator_returns_validated_calendar_draft(
    monkeypatch, calendar_maira_settings, draft_payload
):
    response = Mock()
    response.json.return_value = {
        "detail": {"response": json.dumps(draft_payload)}
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post", post
    )

    result = generate_calendar_proposal(
        "Kalke rat 8ta theke 9ta Math practice",
        "Asia/Dhaka",
        "create",
    )

    assert result["status"] == "draft"
    assert result["event"]["title"] == "Math practice"
    response.raise_for_status.assert_called_once()

    args, kwargs = post.call_args
    assert args == ("https://example.com/ask",)
    assert kwargs["timeout"] == 30
    assert kwargs["headers"] == {
        "api-key": "test-api-key",
        "project-key": "test-project-key",
    }
    assert kwargs["json"]["gpt_profile_id"] == "calendar-profile"
    assert kwargs["json"]["is_background_task"] is False
    assert "Kalke rat 8ta theke 9ta Math practice" in (
        kwargs["json"]["query"]
    )
    assert "Current local date and time:" in kwargs["json"]["query"]
    assert "Asia/Dhaka" in kwargs["json"]["query"]


def test_generator_returns_clarification(
    monkeypatch, calendar_maira_settings
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps({
                "status": "needs_clarification",
                "question": "Koytay shuru ar shesh korte chao?",
            })
        }
    }
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post",
        Mock(return_value=response),
    )

    result = generate_calendar_proposal(
        "Math practice-er event banao",
        "Asia/Dhaka",
        "create",
    )

    assert result["status"] == "needs_clarification"
    assert result["question"] == "Koytay shuru ar shesh korte chao?"


def test_update_sends_only_selected_event_details(
    monkeypatch, calendar_maira_settings, draft_payload
):
    response = Mock()
    response.json.return_value = {
        "detail": {"response": json.dumps(draft_payload)}
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post", post
    )

    selected_event = {
        **draft_payload["event"],
        "id": "private-event-id",
        "user_id": 999,
        "version": 3,
    }

    generate_calendar_proposal(
        "Title Math practice koro",
        "Asia/Dhaka",
        "update",
        selected_event,
    )

    query = post.call_args.kwargs["json"]["query"]
    assert "Practice algebra." in query
    assert "private-event-id" not in query
    assert '"user_id": 999' not in query
    assert '"version": 3' not in query


@pytest.mark.parametrize(
    ("action", "selected_event", "timezone_name"),
    [
        ("delete", None, "Asia/Dhaka"),
        ("update", None, "Asia/Dhaka"),
        ("create", {}, "Asia/Dhaka"),
        ("create", None, "Invalid/Timezone"),
    ],
)
def test_generator_rejects_invalid_request_before_api_call(
    monkeypatch, action, selected_event, timezone_name
):
    post = Mock()
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post", post
    )

    with pytest.raises(CalendarAssistantError) as error:
        generate_calendar_proposal(
            "Create event",
            timezone_name,
            action,
            selected_event,
        )

    assert error.value.status_code == 400
    post.assert_not_called()


def test_generator_requires_calendar_profile(
    monkeypatch, calendar_maira_settings
):
    monkeypatch.delenv("MAIRA_CALENDAR_GPT_PROFILE_ID")
    post = Mock()
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post", post
    )

    with pytest.raises(CalendarAssistantError) as error:
        generate_calendar_proposal("Create event", "Asia/Dhaka", "create")

    assert error.value.status_code == 500
    post.assert_not_called()


def test_generator_handles_timeout(
    monkeypatch, calendar_maira_settings
):
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post",
        Mock(side_effect=requests.Timeout()),
    )

    with pytest.raises(CalendarAssistantError) as error:
        generate_calendar_proposal("Create event", "Asia/Dhaka", "create")

    assert error.value.status_code == 504


def test_generator_handles_http_failure(
    monkeypatch, calendar_maira_settings
):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError()
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(CalendarAssistantError) as error:
        generate_calendar_proposal("Create event", "Asia/Dhaka", "create")

    assert error.value.status_code == 502
    response.json.assert_not_called()


def test_generator_handles_invalid_response_json(
    monkeypatch, calendar_maira_settings
):
    response = Mock()
    response.json.side_effect = ValueError("Invalid JSON")
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(CalendarAssistantError) as error:
        generate_calendar_proposal("Create event", "Asia/Dhaka", "create")

    assert error.value.status_code == 502


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"detail": None},
        {"detail": {}},
        {"detail": {"response": ""}},
        {"detail": {"response": 123}},
    ],
)
def test_generator_rejects_missing_answer(
    monkeypatch, calendar_maira_settings, payload
):
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(CalendarAssistantError) as error:
        generate_calendar_proposal("Create event", "Asia/Dhaka", "create")

    assert error.value.status_code == 502


def test_generator_rejects_invalid_ai_proposal(
    monkeypatch, calendar_maira_settings
):
    response = Mock()
    response.json.return_value = {
        "detail": {"response": '{"status": "saved"}'}
    }
    monkeypatch.setattr(
        "services.calendar_assistant_service.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(CalendarAssistantError):
        generate_calendar_proposal("Create event", "Asia/Dhaka", "create") 