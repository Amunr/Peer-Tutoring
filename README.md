# PVHS Peer Tutoring Scheduler

A Flask application for managing peer tutoring signups, student bookings, and admin operations. The stack includes Flask, SQLAlchemy, Jinja templates, Bootstrap 5, and Textbelt integration for SMS notifications (optional).

## Features

- Tutor portal for subject selection, availability, partial/full day blackout periods, and session cancellation.
- Student booking flow with fairness-based tutor selection, blackout enforcement, and optional SMS notifications (Textbelt).
- Admin dashboard to review bookings, manage tutors, and monitor cancellations.
- CLI command for sending reminder texts 24 hours before sessions.

## Requirements

- Python 3.11+
- SQLite (default) or any `DATABASE_URL` compatible with SQLAlchemy
- Optionally, a Textbelt API key for SMS notifications

## Local Setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows
pip install -r requirements.txt
cp .env.example .env  # set secrets / environment variables
python -m flask shell  # optional sanity check
python app.py  # runs on 0.0.0.0:5000 by default
```

The default configuration uses `sqlite:///peer_tutoring.db` in the project root. To store the database elsewhere, set `DATABASE_URL` in `.env`.

## Deployment Notes

1. **Environment variables**: Set at least `SECRET_KEY`, `DATABASE_URL`, `ADMIN_PASSWORD`, and `TEXTBELT_API_KEY` (if SMS should be live). `HOST` defaults to `0.0.0.0` and `PORT` to `5000`.
2. **Procfile**: The repository includes a `Procfile` with `web: gunicorn app:app`, suitable for Render, Heroku, or any container-based platform.
3. **Flask CLI**: After deployment you can run reminders via `flask send-reminders` (schedule this externally; it does not auto-run).
4. **Static files**: Served by Flask; no extra configuration required.
5. **SMS**: If `TEXTBELT_API_KEY` is empty, SMS calls are skipped but logged.

## Reminder Task Example (Render)

Add a background cron job calling:

```bash
flask send-reminders
```

Ensure `TEXTBELT_API_KEY` is set so texts are actually sent.

## Tests

No automated test suite yet. To verify critical flows:

1. Create a tutor, set availability, add a partial blackout.
2. Book a session as a student (watch server logs for SMS log lines).
3. Cancel as a tutor to ensure the booking status updates and notifications fire.
4. Run `flask send-reminders` to confirm reminder generation.

## Development Tips

- Run with `FLASK_DEBUG=1` locally to auto-reload.
- Delete `instance/peer_tutoring.db` whenever the schema changes.
- Use `pip freeze > requirements.txt` sparingly; keep dependencies minimal.

## License

Not specified. Add one if you plan to open-source.
