import json
from unittest.mock import Mock

import pytest
import requests

from services.weekly_report_ai_service import (
    WeeklyReportGenerationError,
    generate_weekly_report,
)


VALID_REPORT = (
    "Weekly overview\n"
    "The student completed two quiz attempts during this period.\n\n"
    "Practice progress\n"
    "Six of ten answers were correct, giving an overall score of 60%.\n\n"
    "Topics to practise\n"
    "Continue practising Save and Save As.\n\n"
    "Assignments\n"
    "No written or practical submissions were recorded.\n\n"
    "Suggested next steps\n"
    "Review the lesson and complete a short practice quiz."
)


@pytest.fixture()
def report_settings(monkeypatch):
    values = {
        "MAIRA_API_KEY": "test-api-key",
        "MAIRA_PROJECT_KEY": "test-project-key",
        "MAIRA_ASK_URL": "https://example.com/ask",
        "MAIRA_REPORT_PROFILE_ID": "test-report-profile",
        "MAIRA_MEMBER_ID": "test-member",
        "MAIRA_USER_ID": "test-user",
    }

    for name, value in values.items():
        monkeypatch.setenv(name, value)


@pytest.fixture()
def source_data():
    return {
        "student_name": "Private Student Name",
        "period_start": "2026-10-05T06:00:00+00:00",
        "period_end": "2026-10-12T06:00:00+00:00",
        "quiz_activity": {
            "completed_attempts": 2,
            "correct_answers": 6,
            "total_questions": 10,
            "overall_percentage": 60.0,
        },
        "weak_topics": [
            {
                "title": "Save and Save As",
                "latest_percentage": 40.0,
            }
        ],
        "learning_assignments": {
            "written_submissions": 0,
            "practical_submissions": 0,
        },
    }


def mock_response(monkeypatch, answer):
    response = Mock()
    response.json.return_value = {
        "detail": {"response": answer}
    }

    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.weekly_report_ai_service.requests.post",
        post,
    )

    return post


@pytest.mark.parametrize(
    ("language", "instruction"),
    [
        ("banglish", "Write in simple Banglish"),
        ("english", "Write in clear, simple English"),
    ],
)
def test_report_uses_selected_language_and_private_data(
    monkeypatch,
    report_settings,
    source_data,
    language,
    instruction,
):
    original_data = json.dumps(source_data, sort_keys=True)
    post = mock_response(monkeypatch, VALID_REPORT)

    report = generate_weekly_report(
        source_data,
        response_language=language,
    )

    assert report == VALID_REPORT
    post.assert_called_once()

    payload = post.call_args.kwargs["json"]
    query = payload["query"]

    assert payload["gpt_profile_id"] == "test-report-profile"
    assert payload["conversation_type"] == "question"
    assert payload["is_keyword_enabled"] is False
    assert instruction in query
    assert "Private Student Name" not in query
    assert "Save and Save As" in query
    assert "Do not invent numbers" in query

    sent_data = json.loads(query.split("REPORT DATA:\n", 1)[1])
    assert sent_data["quiz_activity"]["overall_percentage"] == 60.0
    assert "student_name" not in sent_data

    assert json.dumps(source_data, sort_keys=True) == original_data


@pytest.mark.parametrize(
    "answer",
    [
        None,
        "",
        "Too short",
        "x" * 6001,
        "```text\n" + VALID_REPORT + "\n```",
        json.dumps({"report": VALID_REPORT}),
    ],
)
def test_report_rejects_invalid_output(
    monkeypatch,
    report_settings,
    source_data,
    answer,
):
    mock_response(monkeypatch, answer)

    with pytest.raises(WeeklyReportGenerationError):
        generate_weekly_report(source_data)


def test_report_rejects_missing_configuration(
    monkeypatch,
    report_settings,
    source_data,
):
    monkeypatch.delenv("MAIRA_REPORT_PROFILE_ID")
    post = Mock()
    monkeypatch.setattr(
        "services.weekly_report_ai_service.requests.post",
        post,
    )

    with pytest.raises(
        WeeklyReportGenerationError,
        match="configuration is incomplete",
    ):
        generate_weekly_report(source_data)

    post.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        requests.Timeout(),
        requests.ConnectionError(),
    ],
)
def test_report_handles_api_failure(
    monkeypatch,
    report_settings,
    source_data,
    error,
):
    post = Mock(side_effect=error)
    monkeypatch.setattr(
        "services.weekly_report_ai_service.requests.post",
        post,
    )

    with pytest.raises(WeeklyReportGenerationError):
        generate_weekly_report(source_data)


def test_report_handles_invalid_response_json(
    monkeypatch,
    report_settings,
    source_data,
):
    response = Mock()
    response.json.side_effect = ValueError("Invalid JSON")

    monkeypatch.setattr(
        "services.weekly_report_ai_service.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(
        WeeklyReportGenerationError,
        match="invalid response",
    ):
        generate_weekly_report(source_data)


def test_report_rejects_invalid_language_before_api_call(
    monkeypatch,
    report_settings,
    source_data,
):
    post = Mock()
    monkeypatch.setattr(
        "services.weekly_report_ai_service.requests.post",
        post,
    )

    with pytest.raises(WeeklyReportGenerationError):
        generate_weekly_report(
            source_data,
            response_language="invalid",
        )

    post.assert_not_called()