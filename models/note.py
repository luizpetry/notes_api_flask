from datetime import datetime
from extensions import db

class Note:
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key = True)

    title =  db.Column(db.String(120), nullable = False)

    content = db.Column(db.Text, nullable = True, default = "")

    created_at = db.Column(db.DateTime, nullable = False, default = datetime.utcnow)

    # FK - Foreign Key (Chave Estrangeira) para users.id - Se refere a primary key de outra tabela
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable = False)

    # Relacionamento Reverso
    user = db.relationship("User", back_populates = "notes")
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
        }
