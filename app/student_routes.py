import datetime as dt
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, flash, jsonify, render_template, request

from .models import (
    Booking,
    Subject,
    available_tutors_for_slot,
    collect_open_slots,
    pick_fair_tutor,
    db,
)
from .services.notifications import send_booking_notifications
from .utils.subjects import group_subjects


student_bp = Blueprint('student', __name__, template_folder='templates/student')


PST = ZoneInfo('America/Los_Angeles')


def _pacific_now() -> dt.datetime:
    return dt.datetime.now(PST)


def _minimum_bookable_date(now: dt.datetime | None = None) -> dt.date:
    if now is None:
        now = _pacific_now()
    min_date = now.date() + dt.timedelta(days=1)
    if now.time() >= dt.time(22, 0):
        min_date += dt.timedelta(days=1)
    return min_date


def _booking_window_status(target_date: dt.date) -> tuple[bool, str, dt.date]:
    now = _pacific_now()
    min_date = _minimum_bookable_date(now)
    if target_date < min_date:
        if target_date <= now.date():
            reason = 'Same-day bookings are not available.'
        else:
            reason = 'After 10:00 PM Pacific, next-day sessions close.'
        message = f"{reason} Earliest available date is {min_date.strftime('%B %d, %Y')}"
        return False, message, min_date
    return True, '', min_date


def _normalize_phone(raw: str) -> str:
    return ''.join(ch for ch in raw if ch.isdigit())


def _slot_minutes() -> int:
    try:
        return int(current_app.config.get('BOOKING_SLOT_MINUTES', 30))
    except (TypeError, ValueError):
        return 30


def _format_phone_display(digits: str) -> str:
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return digits


@student_bp.route('/', methods=['GET'])
def landing():
    return _render_booking_page()


@student_bp.route('/availability', methods=['GET'])
def availability():
    subject_id = request.args.get('subject_id', type=int)
    date_str = request.args.get('date')
    if not subject_id or not date_str:
        return jsonify({'error': 'Missing subject or date.'}), 400
    try:
        target_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format.'}), 400

    allowed, window_message, _ = _booking_window_status(target_date)
    if not allowed:
        return jsonify({'slots': [], 'message': window_message})

    slots_map = collect_open_slots(subject_id, target_date)
    slots = []
    for start_dt in sorted(slots_map.keys()):
        label = start_dt.strftime('%I:%M %p').lstrip('0')
        slots.append(
            {
                'value': start_dt.strftime('%H:%M'),
                'label': label,
                'tutor_count': len(slots_map[start_dt]),
            }
        )
    response = {'slots': slots}
    if not slots:
        response['message'] = window_message or 'No sessions available on that date. Please choose another.'
    return jsonify(response)


@student_bp.route('/book', methods=['POST'])
def book():
    form_values = {
        'student_name': request.form.get('student_name', ''),
        'student_phone': request.form.get('student_phone', ''),
        'subject_id': request.form.get('subject_id', ''),
        'date': request.form.get('date', ''),
        'start_time': request.form.get('start_time', ''),
    }

    name = form_values['student_name'].strip()
    phone = _normalize_phone(form_values['student_phone'])
    subject_id_raw = form_values['subject_id']
    date_str = form_values['date']
    start_time_str = form_values['start_time']

    if not (name and phone and subject_id_raw and date_str and start_time_str):
        flash('Please complete all booking details.', 'danger')
        return _render_booking_page(form_values)

    try:
        subject_id = int(subject_id_raw)
    except ValueError:
        flash('Invalid subject selection.', 'danger')
        return _render_booking_page(form_values)

    subject = Subject.query.get(subject_id)
    if subject is None:
        flash('Selected subject no longer exists.', 'danger')
        return _render_booking_page(form_values)

    try:
        target_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = dt.datetime.strptime(start_time_str, '%H:%M').time()
    except ValueError:
        flash('Invalid date or time value.', 'danger')
        return _render_booking_page(form_values)

    allowed, window_message, _ = _booking_window_status(target_date)
    if not allowed:
        flash(window_message, 'warning')
        return _render_booking_page(form_values)

    start_dt = dt.datetime.combine(target_date, start_time)
    end_dt = start_dt + dt.timedelta(minutes=_slot_minutes())

    candidates = available_tutors_for_slot(subject_id, start_dt, end_dt)
    tutor = pick_fair_tutor(candidates)
    if tutor is None:
        flash('Sorry, that time was just booked. Please choose another slot.', 'warning')
        return _render_booking_page(form_values)

    booking = Booking(
        tutor_id=tutor.id,
        subject_id=subject.id,
        student_name=name,
        student_phone=phone,
        start_time=start_dt,
        end_time=end_dt,
    )
    db.session.add(booking)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Unable to confirm booking. Please try another time slot.', 'danger')
        return _render_booking_page(form_values)

    send_booking_notifications(booking)

    slot_label = start_dt.strftime('%A, %B %d at %I:%M %p').replace(' 0', ' ')
    return render_template(
        'student/confirmation.html',
        booking=booking,
        tutor=tutor,
        subject=subject,
        slot_label=slot_label,
        tutor_phone=_format_phone_display(tutor.phone),
        student_phone=_format_phone_display(phone),
    )


def _render_booking_page(form_values: dict | None = None):
    subjects = Subject.ordered()
    grouped_subjects = group_subjects(subjects)
    min_date = _minimum_bookable_date()
    min_date_iso = min_date.isoformat()
    values = dict(form_values or {})
    if not values.get('date') or values['date'] < min_date_iso:
        values['date'] = min_date_iso
    return render_template(
        'student/booking.html',
        grouped_subjects=grouped_subjects,
        earliest_date=min_date_iso,
        form_values=values,
        slot_minutes=_slot_minutes(),
    )
