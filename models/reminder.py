from datetime import datetime
from extensions import db

class Reminder(db.Model):
    __tablename__ = "reminders"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=True, default="")

    # Data/hora do compromisso
    scheduled_at = db.Column(db.DateTime, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # dono
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    user = db.relationship("User", back_populates="reminders")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "details": self.details,
            "scheduled_at": self.scheduled_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
        }
