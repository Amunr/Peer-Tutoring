import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///peer_tutoring.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    BOOKING_SLOT_MINUTES = int(os.environ.get('BOOKING_SLOT_MINUTES', '30'))
    TEXTBELT_API_KEY = os.environ.get('TEXTBELT_API_KEY', '')
    TEXTBELT_SENDER = os.environ.get('TEXTBELT_SENDER', 'PVHS Peer Tutoring')
