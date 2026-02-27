from datetime import datetime
from extensions import db

class OTP(db.Model):
    __tablename__ = 'otps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Hash do código OTP
    code_hash = db.Column(db.String(255), nullable=False)

    # Data/hora de expiração do OTP
    expires_at = db.Column(db.DateTime, nullable=False)

    # Tentativas de uso do OTP
    attempts = db.Column(db.Integer, default=0, nullable=False)

    # Data/hora de criação
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)