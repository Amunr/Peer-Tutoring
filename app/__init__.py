from flask import Flask

from .models import db, ensure_subjects_seeded


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object('config.Config')

    db.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_subjects_seeded()

    from .services import notifications
    notifications.init_app(app)

    from .tutor_routes import tutor_bp
    from .student_routes import student_bp
    from .admin_routes import admin_bp

    app.register_blueprint(student_bp)
    app.register_blueprint(tutor_bp, url_prefix='/tutor')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app
