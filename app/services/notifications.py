from __future__ import annotations

import datetime as dt
from typing import Iterable

import requests
from zoneinfo import ZoneInfo

from flask import current_app

from ..models import Booking

PST = ZoneInfo('America/Los_Angeles')


def _normalize_phone(raw: str) -> str:
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if raw.startswith('+'):
        return raw
    return digits


def _send_sms(phone: str, message: str) -> bool:
    api_key = current_app.config.get('TEXTBELT_API_KEY')
    if not api_key:
        current_app.logger.info(
            "Skipping SMS to %s because TEXTBELT_API_KEY is not configured.", phone
        )
        return False

    url = current_app.config.get('TEXTBELT_URL', 'https://textbelt.com/text')
    sender = current_app.config.get('TEXTBELT_SENDER', 'PVHS Peer Tutoring')
    payload = {
        'phone': phone,
        'message': message,
        'sender': sender,
        'key': api_key,
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('success'):
            current_app.logger.warning(
                "Textbelt reported failure: phone=%s response=%s", phone, data
            )
            return False
        return True
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("Failed to send SMS to %s: %s", phone, exc)
        return False


def format_slot_label(booking: Booking) -> str:
    start_time = booking.start_time
    if start_time.tzinfo is None:
        start_local = start_time
    else:
        start_local = start_time.astimezone(PST)
    return start_local.strftime('%A, %B %d at %I:%M %p').replace(' 0', ' ')


def send_booking_notifications(booking: Booking) -> None:
    tutor = booking.tutor
    subject_name = booking.subject.name if booking.subject else 'tutoring'
    slot_label = format_slot_label(booking)

    student_phone = _normalize_phone(booking.student_phone)
    tutor_phone = _normalize_phone(tutor.phone)

    student_message = (
        f"PVHS Peer Tutoring: You're booked for {subject_name} on {slot_label} with "
        f"{tutor.name}. Tutor contact: {tutor_phone}. If you need to cancel, please text your tutor."
    )
    tutor_message = (
        f"PVHS Peer Tutoring: You have been booked for {slot_label} with {booking.student_name} "
        f"for {subject_name}. Visit the tutor portal if you need to cancel."
    )

    _send_sms(student_phone, student_message)
    _send_sms(tutor_phone, tutor_message)


def send_cancellation_notification(booking: Booking) -> None:
    tutor = booking.tutor
    student_phone = _normalize_phone(booking.student_phone)
    slot_label = format_slot_label(booking)
    message = (
        f"PVHS Peer Tutoring: Tutor {tutor.name} has canceled your session on {slot_label}. "
        "Please book another time."
    )
    _send_sms(student_phone, message)


def send_reminder_notifications(bookings: Iterable[Booking]) -> None:
    for booking in bookings:
        if booking.is_canceled:
            continue
        tutor = booking.tutor
        subject_name = booking.subject.name if booking.subject else 'tutoring'
        slot_label = format_slot_label(booking)
        time_only = slot_label.split(' at ')[-1]

        student_phone = _normalize_phone(booking.student_phone)
        tutor_phone = _normalize_phone(tutor.phone)

        student_msg = (
            f"Reminder: You have a tutoring session with {tutor.name} tomorrow at {time_only}."
        )
        tutor_msg = (
            f"Reminder: You have a tutoring session with {booking.student_name} tomorrow at {time_only} "
            f"for {subject_name}."
        )

        _send_sms(student_phone, student_msg)
        _send_sms(tutor_phone, tutor_msg)


def reminder_candidates(window_start: dt.datetime, window_end: dt.datetime) -> Iterable[Booking]:
    return (
        Booking.query.filter(
            Booking.is_canceled.is_(False),
            Booking.start_time >= window_start,
            Booking.start_time < window_end,
        )
        .order_by(Booking.start_time.asc())
        .all()
    )


def register_cli(app):
    @app.cli.command('send-reminders')
    def send_reminders_command():
        """Send reminder texts for sessions starting tomorrow."""
        with app.app_context():
            now = dt.datetime.now(PST)
            window_start = now + dt.timedelta(days=1)
            window_end = now + dt.timedelta(days=1, hours=1)
            bookings = reminder_candidates(window_start, window_end)
            app.logger.info('Found %s bookings for reminder window.', len(bookings))
            send_reminder_notifications(bookings)


def init_app(app):
    register_cli(app)
