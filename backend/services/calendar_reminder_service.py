from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from extensions import db
from models.calendar_event import CalendarEvent
from models.notification import Notification


def as_utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def send_due_calendar_reminders(
    now: datetime | None = None,
) -> int:
    current_time = now if now is not None else datetime.now(timezone.utc)

    if current_time.utcoffset() is None:
        raise ValueError("Reminder processing requires a timezone-aware time.")

    current_time = current_time.astimezone(timezone.utc)
    latest_start = current_time + timedelta(days=7)

    events_table = db.metadata.tables["calendar_events"]
    sent_count = 0

    try:
        # The maximum reminder interval is seven days.
        # Skip events that have already started or were already reminded.
        events = db.session.scalars(
            db.select(CalendarEvent)
            .where(
                events_table.c["reminder_minutes"].is_not(None),
                events_table.c["reminder_sent_at"].is_(None),
                events_table.c["starts_at"] > current_time,
                events_table.c["starts_at"] <= latest_start,
            )
            .order_by(
                events_table.c["starts_at"],
                events_table.c["id"],
            )
            .with_for_update(
                of=CalendarEvent,
                skip_locked=True,
            )
        ).all()

        for event in events:
            reminder_minutes = event.reminder_minutes

            if reminder_minutes is None:
                continue

            starts_at = as_utc(event.starts_at)
            reminder_due_at = starts_at - timedelta(
                minutes=reminder_minutes
            )

            if current_time < reminder_due_at:
                continue

            local_start = starts_at.astimezone(
                ZoneInfo(event.timezone_name)
            )

            db.session.add(
                Notification(
                    user_id=event.user_id,
                    notification_type="calendar_event_reminder",
                    title="Upcoming calendar event",
                    message=(
                        f'"{event.title}" starts at '
                        f'{local_start.strftime("%d %b %Y, %I:%M %p")} '
                        f'({event.timezone_name}).'
                    ),
                )
            )

            event.reminder_sent_at = current_time
            sent_count += 1

        # Save notifications and reminder markers together.
        # Commit also releases the row locks.
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return sent_count