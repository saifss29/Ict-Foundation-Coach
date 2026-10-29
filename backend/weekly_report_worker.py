import logging
import os
import signal
from datetime import datetime, timedelta, timezone
from threading import Event
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import app
from extensions import db
from services.weekly_report_delivery_service import deliver_weekly_report


logger = logging.getLogger("weekly_report_worker")
stop_event = Event()
DHAKA = ZoneInfo("Asia/Dhaka")


def report_schedule(now: datetime, mode: str):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Scheduler time must include a timezone.")

    now = now.astimezone(timezone.utc)

    if mode == "demo":
        # One delivery slot every five minutes.
        slot_seconds = int(now.timestamp()) // 300 * 300
        period_end = datetime.fromtimestamp(
            slot_seconds,
            tz=timezone.utc,
        )
        key = f"demo:{slot_seconds}"
        return key, period_end, True

    if mode != "weekly":
        raise ValueError("Report mode must be demo or weekly.")

    # Regular delivery: Monday at 09:00 Bangladesh time.
    local_now = now.astimezone(DHAKA)
    monday = (
        local_now - timedelta(days=local_now.weekday())
    ).replace(hour=9, minute=0, second=0, microsecond=0)

    if local_now < monday:
        monday -= timedelta(days=7)

    period_end = monday.astimezone(timezone.utc)
    key = f"weekly:{monday:%Y-%m-%d}"

    return key, period_end, False


def run_report_cycle(now: datetime, mode: str):
    delivery_key, period_end, is_demo = report_schedule(now, mode)
    users = db.metadata.tables["users"]

    student_ids = db.session.execute(
        select(users.c.id)
        .where(
            users.c.role == "student",
            users.c.academic_level.in_(("ssc", "hsc")),
            users.c.weekly_report_enabled.is_(True),
            users.c.parent_email.is_not(None),
            users.c.parent_email_verified_at.is_not(None),
            users.c.parent_email_verified_at <= period_end,
        )
        .order_by(users.c.id)
    ).scalars().all()

    db.session.rollback()

    results = {}

    for student_id in student_ids:
        if stop_event.is_set():
            break

        try:
            result = deliver_weekly_report(
                student_id=student_id,
                delivery_key=delivery_key,
                period_end=period_end,
                is_demo=is_demo,
            )
        except Exception as error:
            db.session.rollback()
            logger.error(
                "Report cycle failed for student %s: %s",
                student_id,
                type(error).__name__,
            )
            result = "error"
        finally:
            db.session.remove()

        results[result] = results.get(result, 0) + 1

        if result != "duplicate":
            logger.info(
                "Student %s report result: %s",
                student_id,
                result,
            )

    return results


def stop_worker(signum, frame):
    stop_event.set()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    enabled = (
        os.getenv("WEEKLY_REPORT_ENABLED", "false").strip().lower()
        == "true"
    )
    mode = os.getenv("WEEKLY_REPORT_MODE", "weekly").strip().lower()

    if not enabled:
        logger.info("Weekly report worker is disabled.")
        return

    if mode not in {"demo", "weekly"}:
        raise ValueError("WEEKLY_REPORT_MODE must be demo or weekly.")

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    logger.info(
        "Weekly report worker started. Mode: %s",
        mode,
    )

    while not stop_event.is_set():
        try:
            with app.app_context():
                run_report_cycle(
                    datetime.now(timezone.utc),
                    mode,
                )
        except Exception as error:
            logger.error(
                "Worker cycle failed: %s",
                type(error).__name__,
            )

        stop_event.wait(30)

    logger.info("Weekly report worker stopped.")


if __name__ == "__main__":
    main()