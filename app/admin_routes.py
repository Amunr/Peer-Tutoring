import datetime as dt
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from .models import Booking, Subject, Tutor, db
from .utils.subjects import group_subjects


admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')


def _normalize_phone(raw: str) -> str:
    return ''.join(ch for ch in raw if ch.isdigit())


def _format_phone_display(digits: str) -> str:
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return digits


def admin_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('admin_authenticated'):
            flash('Please sign in as an administrator.', 'warning')
            return redirect(url_for('admin.admin_login'))
        return view_func(*args, **kwargs)

    return wrapped


@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_authenticated'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        expected = current_app.config.get('ADMIN_PASSWORD', '')
        if password and password == expected:
            session['admin_authenticated'] = True
            flash('Administrator access granted.', 'success')
            return redirect(url_for('admin.dashboard'))
        flash('Invalid admin password.', 'danger')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
@admin_login_required
def admin_logout():
    session.pop('admin_authenticated', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/')
def admin_index():
    if session.get('admin_authenticated'):
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/dashboard')
@admin_login_required
def dashboard():
    bookings = Booking.query.order_by(Booking.start_time.asc()).all()
    tutors = Tutor.query.order_by(Tutor.name.asc()).all()
    grouped_subjects = group_subjects(Subject.ordered())
    today = dt.date.today()
    return render_template(
        'admin/dashboard.html',
        bookings=bookings,
        tutors=tutors,
        grouped_subjects=grouped_subjects,
        today=today,
        format_phone=_format_phone_display,
    )


@admin_bp.route('/tutors/add', methods=['POST'])
@admin_login_required
def add_tutor():
    name = request.form.get('name', '').strip()
    phone = _normalize_phone(request.form.get('phone', ''))
    pin = request.form.get('pin', '').strip()
    subject_ids = [int(value) for value in request.form.getlist('subjects') if value.isdigit()]

    if not (name and phone and pin):
        flash('Name, phone, and PIN are required.', 'danger')
        return redirect(url_for('admin.dashboard'))
    if len(pin) < 4:
        flash('PIN must be at least 4 characters.', 'danger')
        return redirect(url_for('admin.dashboard'))
    if Tutor.query.filter_by(phone=phone).first():
        flash('A tutor with that phone number already exists.', 'warning')
        return redirect(url_for('admin.dashboard'))

    tutor = Tutor(name=name, phone=phone, pin_hash=generate_password_hash(pin))
    if subject_ids:
        tutor.subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all()
    db.session.add(tutor)
    db.session.commit()
    flash('Tutor added successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/tutors/<int:tutor_id>/toggle', methods=['POST'])
@admin_login_required
def toggle_tutor_active(tutor_id: int):
    tutor = Tutor.query.get_or_404(tutor_id)
    tutor.is_active = not tutor.is_active
    db.session.commit()
    status = 'activated' if tutor.is_active else 'deactivated'
    flash(f'Tutor {status}.', 'info')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/tutors/<int:tutor_id>/delete', methods=['POST'])
@admin_login_required
def delete_tutor(tutor_id: int):
    tutor = Tutor.query.get_or_404(tutor_id)
    if tutor.bookings:
        flash('Cannot delete tutor with existing bookings. Deactivate instead.', 'warning')
        return redirect(url_for('admin.dashboard'))
    db.session.delete(tutor)
    db.session.commit()
    flash('Tutor removed.', 'info')
    return redirect(url_for('admin.dashboard'))
