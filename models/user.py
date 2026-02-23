from extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(120), nullable = False)
    # index = True - Melhora performance nas buscas por email
    email = db.Column(db.String(255), unique = True, nullable = False, index = True)
    # hash da senha (nunca retorna em respostas)
    password_hash = db.Column(db.String(255), nullable = False)

    # relacionamento: 1 user -> várias notas
    notes = db.relationship("Note", back_populates="user", cascade="all, delete-orphan")

    # REMINDERS
    reminders = db.relationship("Reminder", back_populates="user", cascade="all, delete-orphan")


    def to_dict(self):
        return {
            "id" : self.id,
            "name" : self.name,
            "email" : self.email,
        }