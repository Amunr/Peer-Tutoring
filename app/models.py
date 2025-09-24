from __future__ import annotations

import datetime as dt
import random
from typing import Dict, List, Tuple

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship


db = SQLAlchemy()


class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    category = db.Column(db.String(64), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, unique=True)

    tutors = relationship('Tutor', secondary='tutor_subjects', back_populates='subjects')

    @staticmethod
    def ordered() -> List['Subject']:
        return Subject.query.order_by(Subject.sort_order).all()


class Tutor(db.Model):
    __tablename__ = 'tutors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), nullable=False, unique=True)
    pin_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    subjects = relationship('Subject', secondary='tutor_subjects', back_populates='tutors')
    weekly_availability = relationship('WeeklyAvailability', cascade='all, delete-orphan', back_populates='tutor')
    exceptions = relationship('TutorException', cascade='all, delete-orphan', back_populates='tutor')
    bookings = relationship('Booking', cascade='all, delete-orphan', back_populates='tutor')

    def total_bookings(self) -> int:
        return sum(1 for booking in self.bookings if not booking.is_canceled)

    def availability_for_day(self, weekday: int) -> List['WeeklyAvailability']:
        return [avail for avail in self.weekly_availability if avail.day_of_week == weekday]

    def is_available_for_slot(self, start_dt: dt.datetime, end_dt: dt.datetime) -> bool:
        for exception in self.exceptions:
            if exception.overlaps(start_dt, end_dt):
                return False
        blocks = self.availability_for_day(start_dt.weekday())
        block_matches = any(
            block.start_time <= start_dt.time() and block.end_time >= end_dt.time()
            for block in blocks
        )
        if not block_matches:
            return False
        for booking in self.bookings:
            if booking.is_canceled:
                continue
            if booking.start_time < end_dt and booking.end_time > start_dt:
                return False
        return True


class TutorSubject(db.Model):
    __tablename__ = 'tutor_subjects'
    __table_args__ = (UniqueConstraint('tutor_id', 'subject_id', name='uq_tutor_subject'),)

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)


class WeeklyAvailability(db.Model):
    __tablename__ = 'weekly_availability'

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id', ondelete='CASCADE'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    tutor = relationship('Tutor', back_populates='weekly_availability')

    def generate_slots(self, date: dt.date, slot_minutes: int) -> List[Tuple[dt.datetime, dt.datetime]]:
        slots: List[Tuple[dt.datetime, dt.datetime]] = []
        start_dt = dt.datetime.combine(date, self.start_time)
        end_dt = dt.datetime.combine(date, self.end_time)
        step = dt.timedelta(minutes=slot_minutes)
        cursor = start_dt
        while cursor + step <= end_dt:
            slots.append((cursor, cursor + step))
            cursor += step
        return slots


class TutorException(db.Model):
    __tablename__ = 'tutor_exceptions'
    __table_args__ = (UniqueConstraint('tutor_id', 'date', 'start_time', 'end_time', name='uq_tutor_date_exception'),)

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    note = db.Column(db.String(255))

    tutor = relationship('Tutor', back_populates='exceptions')

    def is_full_day(self) -> bool:
        return self.start_time is None and self.end_time is None

    def overlaps(self, start_dt: dt.datetime, end_dt: dt.datetime) -> bool:
        if self.date != start_dt.date():
            return False
        if self.is_full_day():
            return True
        if self.start_time is None or self.end_time is None:
            return True
        exc_start = dt.datetime.combine(self.date, self.start_time)
        exc_end = dt.datetime.combine(self.date, self.end_time)
        return start_dt < exc_end and end_dt > exc_start


class Booking(db.Model):
    __tablename__ = 'bookings'
    __table_args__ = (UniqueConstraint('tutor_id', 'start_time', name='uq_tutor_booking_start'),)

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'))
    student_name = db.Column(db.String(120), nullable=False)
    student_phone = db.Column(db.String(32), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    is_canceled = db.Column(db.Boolean, default=False, nullable=False)
    canceled_at = db.Column(db.DateTime)
    cancel_reason = db.Column(db.String(255))

    tutor = relationship('Tutor', back_populates='bookings')
    subject = relationship('Subject')

    @property
    def is_active(self) -> bool:
        return not self.is_canceled


SUBJECT_GROUPS: List[Tuple[str, List[str]]] = [
    ('Math Subjects', [
        'IM1',
        'IM2',
        'IM3',
        'Precalculus',
        'HonorsTrig/Precalc',
        'AP Calculus',
        'Intro to Statistics',
        'Personal Finance',
    ]),
    ('Science Classes', [
        'Biology',
        'Chemistry',
        'Physics',
        'AP Biology',
        'AP Chemistry',
        'AP Environmental Science',
        'Nutrition and Food Science',
        'Biotechnology',
        'Anatomy Physiology',
        'Intro to Computer Science',
    ]),
    ('English Classes', [
        'English 9',
        'Honors English 9',
        'English 10',
        'Honors English 10',
        'English 11th Grade',
        'English 12th Grade',
        'AP Seminar',
        'AP English Language and Composition',
        'AP English Literature and Composition',
    ]),
    ('History Classes', [
        'World History',
        'AP World History',
        'US History',
        'AP US History',
        'American Government',
        'Economics',
        'AP Government and Politics',
        'AP Macroeconomics',
    ]),
    ('Foreign Language', [
        'Spanish I',
        'Spanish II',
        'Spanish III',
        'Spanish IV',
        'AP Spanish Language',
        'Japanese I',
        'Japanese II',
    ]),
    ('Any Elective Classes', [
        'Health',
        'AP Psych',
        'AP Research',
    ]),
]


def ensure_subjects_seeded() -> None:
    existing = {subject.name: subject for subject in Subject.query.all()}
    order = 1
    for category, names in SUBJECT_GROUPS:
        for name in names:
            subject = existing.get(name)
            if subject is None:
                subject = Subject(name=name, category=category, sort_order=order)
                db.session.add(subject)
            else:
                subject.category = category
                subject.sort_order = order
            order += 1
    db.session.commit()


def available_tutors_for_slot(subject_id: int, start_dt: dt.datetime, end_dt: dt.datetime) -> List[Tutor]:
    tutors = (
        Tutor.query.join(TutorSubject)
        .filter(TutorSubject.subject_id == subject_id, Tutor.is_active.is_(True))
        .all()
    )

    eligible: List[Tutor] = []
    for tutor in tutors:
        if tutor.is_available_for_slot(start_dt, end_dt):
            eligible.append(tutor)

    return eligible


def pick_fair_tutor(candidates: List[Tutor]) -> Tutor | None:
    if not candidates:
        return None
    booking_counts = {
        tutor.id: sum(1 for booking in tutor.bookings if not booking.is_canceled)
        for tutor in candidates
    }
    min_count = min(booking_counts.values())
    smallest = [tutor for tutor in candidates if booking_counts[tutor.id] == min_count]
    return random.choice(smallest)

def collect_open_slots(subject_id: int, target_date: dt.date) -> Dict[dt.datetime, List[Tutor]]:
    """Return a mapping of slot start times to available tutors for a given subject/date."""
    slot_minutes = int(current_app.config.get('BOOKING_SLOT_MINUTES', 30))
    tutors = (
        Tutor.query.join(TutorSubject)
        .filter(TutorSubject.subject_id == subject_id, Tutor.is_active.is_(True))
        .all()
    )
    slots: Dict[dt.datetime, List[Tutor]] = {}
    weekday = target_date.weekday()
    for tutor in tutors:
        availabilities = tutor.availability_for_day(weekday)
        if not availabilities:
            continue
        for block in availabilities:
            for start_dt, end_dt in block.generate_slots(target_date, slot_minutes):
                if tutor.is_available_for_slot(start_dt, end_dt):
                    slots.setdefault(start_dt, []).append(tutor)
    return slots
