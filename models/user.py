from datetime import datetime
from extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # pode deixar opcional agora (no registro não vamos pedir nome)
    name = db.Column(db.String(120), nullable=True)

    # NOVO: telefone em vez de email
    phone = db.Column(db.String(32), unique=True, nullable=False, index=True)

    # hash da senha
    password_hash = db.Column(db.String(255), nullable=False)

    # NOVO: usuário precisa verificar com código
    is_verified = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # relacionamento: 1 user -> várias notas
    notes = db.relationship("Note", back_populates="user", cascade="all, delete-orphan")

    # reminders
    reminders = db.relationship("Reminder", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "is_verified": self.is_verified,
        }