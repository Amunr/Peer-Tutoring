import datetime as dt
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .models import Booking, Subject, Tutor, TutorException, WeeklyAvailability, db
from .services.notifications import send_cancellation_notification
from .utils.subjects import group_subjects

tutor_bp = Blueprint('tutor', __name__, template_folder='templates/tutor')


@tutor_bp.route('/')
def index():
    if session.get('tutor_id'):
        return redirect(url_for('tutor.dashboard'))
    return redirect(url_for('tutor.login'))


def _normalize_phone(raw: str) -> str:
    digits = ''.join(ch for ch in raw if ch.isdigit())
    return digits


def _format_phone_display(raw: str) -> str:
    digits = _normalize_phone(raw)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw


def get_current_tutor() -> Tutor | None:
    tutor_id = session.get('tutor_id')
    if not tutor_id:
        return None
    return Tutor.query.get(tutor_id)


def tutor_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('tutor_id'):
            flash('Please log in to access the tutor portal.', 'warning')
            return redirect(url_for('tutor.login'))
        return view_func(*args, **kwargs)

    return wrapped


@tutor_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    subjects = Subject.ordered()
    grouped_subjects = group_subjects(subjects)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = _normalize_phone(request.form.get('phone', ''))
        pin = request.form.get('pin', '').strip()

        if not name or not phone or not pin:
            flash('All fields are required.', 'danger')
            return render_template('tutor/signup.html', grouped_subjects=grouped_subjects)
        if len(pin) < 4:
            flash('PIN must be at least 4 characters.', 'danger')
            return render_template('tutor/signup.html', grouped_subjects=grouped_subjects)
        if Tutor.query.filter_by(phone=phone).first():
            flash('A tutor with that phone number already exists. Please log in instead.', 'danger')
            return redirect(url_for('tutor.login'))

        tutor = Tutor(name=name, phone=phone, pin_hash=generate_password_hash(pin))

        selected_subject_ids = [int(sid) for sid in request.form.getlist('subjects') if sid.isdigit()]
        if selected_subject_ids:
            tutor.subjects = Subject.query.filter(Subject.id.in_(selected_subject_ids)).all()
        db.session.add(tutor)
        db.session.commit()
        session['tutor_id'] = tutor.id
        flash('Welcome! You can now set up your availability.', 'success')
        return redirect(url_for('tutor.dashboard'))

    return render_template('tutor/signup.html', grouped_subjects=grouped_subjects)


@tutor_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = _normalize_phone(request.form.get('phone', ''))
        pin = request.form.get('pin', '').strip()
        tutor = Tutor.query.filter_by(phone=phone).first()
        if tutor and check_password_hash(tutor.pin_hash, pin):
            session['tutor_id'] = tutor.id
            flash('Logged in successfully.', 'success')
            return redirect(url_for('tutor.dashboard'))
        flash('Invalid phone or PIN.', 'danger')
    return render_template('tutor/login.html')


@tutor_bp.route('/logout')
@tutor_login_required
def logout():
    session.pop('tutor_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('tutor.login'))


@tutor_bp.route('/dashboard')
@tutor_login_required
def dashboard():
    tutor = get_current_tutor()
    if tutor is None:
        flash('Please log in to access the tutor portal.', 'warning')
        return redirect(url_for('tutor.login'))
    subjects = Subject.ordered()
    grouped_subjects = group_subjects(subjects)
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    availability_blocks = sorted(
        tutor.weekly_availability,
        key=lambda block: (block.day_of_week, block.start_time),
    )
    exception_list = sorted(
        tutor.exceptions,
        key=lambda exc: (exc.date, exc.start_time or dt.time.min),
    )
    now_utc = dt.datetime.utcnow()
    upcoming_bookings = (
        Booking.query.filter(
            Booking.tutor_id == tutor.id,
            Booking.is_canceled.is_(False),
            Booking.start_time >= now_utc,
        )
        .order_by(Booking.start_time.asc())
        .all()
    )
    recent_cancellations = (
        Booking.query.filter(
            Booking.tutor_id == tutor.id,
            Booking.is_canceled.is_(True),
        )
        .order_by(Booking.canceled_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        'tutor/dashboard.html',
        tutor=tutor,
        grouped_subjects=grouped_subjects,
        weekday_names=weekday_names,
        availability_blocks=availability_blocks,
        exception_list=exception_list,
        upcoming_bookings=upcoming_bookings,
        recent_cancellations=recent_cancellations,
        format_phone=_format_phone_display,
    )


@tutor_bp.route('/subjects', methods=['POST'])
@tutor_login_required
def update_subjects():
    tutor = get_current_tutor()
    selected_subject_ids = [int(sid) for sid in request.form.getlist('subjects') if sid.isdigit()]
    tutor.subjects = Subject.query.filter(Subject.id.in_(selected_subject_ids)).all()
    db.session.commit()
    flash('Subjects updated.', 'success')
    return redirect(url_for('tutor.dashboard'))


@tutor_bp.route('/availability', methods=['POST'])
@tutor_login_required
def add_availability():
    tutor = get_current_tutor()
    day = request.form.get('day_of_week')
    start = request.form.get('start_time')
    end = request.form.get('end_time')

    try:
        day_idx = int(day)
        start_time = dt.datetime.strptime(start, '%H:%M').time()
        end_time = dt.datetime.strptime(end, '%H:%M').time()
    except (ValueError, TypeError):
        flash('Invalid availability input.', 'danger')
        return redirect(url_for('tutor.dashboard'))

    if end_time <= start_time:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('tutor.dashboard'))

    availability = WeeklyAvailability(tutor_id=tutor.id, day_of_week=day_idx, start_time=start_time, end_time=end_time)
    db.session.add(availability)
    db.session.commit()
    flash('Availability added.', 'success')
    return redirect(url_for('tutor.dashboard'))


@tutor_bp.route('/availability/<int:availability_id>/delete', methods=['POST'])
@tutor_login_required
def delete_availability(availability_id: int):
    availability = WeeklyAvailability.query.get_or_404(availability_id)
    tutor = get_current_tutor()
    if availability.tutor_id != tutor.id:
        flash('You cannot modify another tutor\'s availability.', 'danger')
        return redirect(url_for('tutor.dashboard'))
    db.session.delete(availability)
    db.session.commit()
    flash('Availability removed.', 'info')
    return redirect(url_for('tutor.dashboard'))


@tutor_bp.route('/exceptions', methods=['POST'])
@tutor_login_required
def add_exception():
    tutor = get_current_tutor()
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    note = request.form.get('note', '').strip() or None
    try:
        date_obj = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date for unavailability.', 'danger')
        return redirect(url_for('tutor.dashboard'))

    start_time = end_time = None
    if start_str or end_str:
        if not start_str or not end_str:
            flash('Please provide both start and end time for a partial blackout.', 'danger')
            return redirect(url_for('tutor.dashboard'))
        try:
            start_time = dt.datetime.strptime(start_str, '%H:%M').time()
            end_time = dt.datetime.strptime(end_str, '%H:%M').time()
        except ValueError:
            flash('Invalid time for blackout period.', 'danger')
            return redirect(url_for('tutor.dashboard'))
        if end_time <= start_time:
            flash('Blackout end time must be after the start time.', 'danger')
            return redirect(url_for('tutor.dashboard'))

    provisional_start = dt.datetime.combine(date_obj, start_time or dt.time.min)
    provisional_end = dt.datetime.combine(date_obj, end_time or dt.time.max)
    for existing in tutor.exceptions:
        if existing.overlaps(provisional_start, provisional_end):
            flash('That blackout overlaps with an existing one.', 'warning')
            return redirect(url_for('tutor.dashboard'))

    exception = TutorException(
        tutor_id=tutor.id,
        date=date_obj,
        start_time=start_time,
        end_time=end_time,
        note=note,
    )
    db.session.add(exception)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('You already marked that time as unavailable.', 'warning')
        return redirect(url_for('tutor.dashboard'))
    flash('Unavailability added.', 'success')
    return redirect(url_for('tutor.dashboard'))


@tutor_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@tutor_login_required
def cancel_booking(booking_id: int):
    tutor = get_current_tutor()
    if tutor is None:
        flash('Please log in to access the tutor portal.', 'warning')
        return redirect(url_for('tutor.login'))
    booking = Booking.query.get_or_404(booking_id)
    if booking.tutor_id != tutor.id:
        flash("You cannot modify another tutor's booking.", 'danger')
        return redirect(url_for('tutor.dashboard'))
    if booking.is_canceled:
        flash('That booking is already canceled.', 'info')
        return redirect(url_for('tutor.dashboard'))
    reason = request.form.get('cancel_reason', '').strip() or None
    booking.is_canceled = True
    booking.canceled_at = dt.datetime.utcnow()
    booking.cancel_reason = reason[:255] if reason else None
    db.session.commit()
    send_cancellation_notification(booking)
    flash('Booking canceled. Please notify the student if possible.', 'info')
    return redirect(url_for('tutor.dashboard'))


@tutor_bp.route('/exceptions/<int:exception_id>/delete', methods=['POST'])
@tutor_login_required
def delete_exception(exception_id: int):
    exception = TutorException.query.get_or_404(exception_id)
    tutor = get_current_tutor()
    if exception.tutor_id != tutor.id:
        flash('You cannot modify another tutor\'s exception.', 'danger')
        return redirect(url_for('tutor.dashboard'))
    db.session.delete(exception)
    db.session.commit()
    flash('Exception removed.', 'info')
    return redirect(url_for('tutor.dashboard'))
