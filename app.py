# Main application file
import os
from flask import Flask, jsonify, request 
from datetime import datetime
from extensions import db, migrate # Importa as instancias/objetos db e migrate de extensions.py

from models.note import Note # Importa a class Note do models/note.py
from models.user import User

from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

from sqlalchemy import or_
from flask_cors import CORS
from dotenv import load_dotenv

from models.reminder import Reminder

load_dotenv()

app = Flask(__name__)
CORS(app)


# Config do DB (SQLite)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///notes.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Config JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-secret")

# Inicializa as extensões do DB antes de rodar o app / CLI
db.init_app(app)
migrate.init_app(app, db)

jwt = JWTManager(app)


    # ROTAS NOTES
# CREATE 
@app.route('/notes', methods=['POST'])
@jwt_required()
def create_note():
    # or: Se o JSON vier vazio ou inválido, usa um dicionário vazio em vez de None.
    data = request.get_json() or {} # Pega o corpo da requisição e converte para um dicionário

    title = data.get("title")
    if not title:
        return jsonify({"message": "Title is required"}), 400

    user_id = int(get_jwt_identity()) # Pega o user.id dentro do token

    note = Note(
        title = title,
        content = data.get("content", ""),
        created_at = datetime.utcnow(),
        user_id=user_id
    )

    # Salva a nota em memoria
    db.session.add(note)
    # Executa o que esta pendente no banco de dados
    db.session.commit()

    return jsonify({"message": "Note created successfully", "id": note.id}), 201
    

# READ
@app.route('/notes', methods=['GET'])
@jwt_required() # Exige token valido
def get_notes():
    user_id = int(get_jwt_identity())

    search = request.args.get("search")          # texto livre
    favorite = request.args.get("favorite")      # "true" | "false" | None
    pinned = request.args.get("pinned")          # "true" | "false" | None
    sort = request.args.get("sort", "recent")    # recent | oldest

    query = Note.query.filter_by(user_id=user_id, deleted_at=None)

    # BUSCA por título ou conteúdo
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Note.title.ilike(like),
                Note.content.ilike(like)
            )
        )

    # FILTRO FAVORITOS
    if favorite is not None:
        if favorite.lower() == "true":
            query = query.filter(Note.is_favorite.is_(True))
        elif favorite.lower() == "false":
            query = query.filter(Note.is_favorite.is_(False))

    # FILTRO PINNED
    if pinned is not None:
        if pinned.lower() == "true":
            query = query.filter(Note.is_pinned.is_(True))
        elif pinned.lower() == "false":
            query = query.filter(Note.is_pinned.is_(False))

    # ORDENAÇÃO
    if sort == "oldest":
        query = query.order_by(Note.id.asc())
    else:  
        query = query.order_by(Note.is_pinned.desc(), Note.id.desc())

    notes = query.all()

    return jsonify({
        "notes": [n.to_dict() for n in notes],
        "total_notes": len(notes)
    })

# READ SPECIFIC ID 
@app.route('/notes/<int:id>', methods=['GET'])
@jwt_required()
def get_note(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    return jsonify(note.to_dict())

# UPDATE
@app.route('/notes/<int:id>', methods=['PUT'])
@jwt_required()
def update_note(id):
    user_id = int(get_jwt_identity())

    # Busca a nota pelo id e pelo dono
    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()

    if not note: # Se nao existir nota ou nao for dele
        return jsonify({"message": "Note not found"}), 404

    data = request.get_json() or {} 

    # Atualiza só os campos enviados
    if "title" in data:
        note.title = data["title"]

    if "content" in data:
        note.content = data["content"]

    db.session.commit() # Salva no banco

    return jsonify({"message": "Note updated successfully"})

# DELETE
@app.route("/notes/<int:id>", methods=['DELETE'])
@jwt_required()
def delete_note(id):
    user_id = int(get_jwt_identity())
                                        # deleted_at=None: você só “deleta” se ela não estiver já na lixeira
    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    note.deleted_at = datetime.utcnow()  # manda pra lixeira
    db.session.commit()

    return jsonify({"message": "Note moved to trash"})


#       Rotas de registro e login
# Register
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "name, email and password are required"}), 400

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password) # Usa o werkzeug
    )

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        # Reverte alteracoes pendentes feitas no banco de dados na transacao atual
        db.session.rollback()
        return jsonify({"message": "Email already exists"}), 409
    
    return jsonify({"message": "User created successfully"}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "email and password are required"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(identity=str(user.id))

    return jsonify({"access_token": access_token, "user": user.to_dict()}), 200


# LIXEIRA
# LISTAR LIXEIRA
@app.route("/notes/trash", methods=["GET"])
@jwt_required()
def get_trash():
    user_id = int(get_jwt_identity())

    notes = (
        Note.query
        .filter_by(user_id=user_id)
        .filter(Note.deleted_at.isnot(None))
        .order_by(Note.deleted_at.desc())
        .all()
    )

    return jsonify({
        "trash": [n.to_dict() for n in notes],
        "total_trash": len(notes)
    })

# RESTAURAR NOTA DA LIXEIRA
@app.route("/notes/<int:id>/restore", methods=["POST"])
@jwt_required()
def restore_note(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id).first()
    if not note or note.deleted_at is None:
        return jsonify({"message": "Note not found in trash"}), 404

    note.deleted_at = None
    db.session.commit()

    return jsonify({"message": "Note restored successfully"})

# HARD DELETE - APAGAR DA LIXEIRA
@app.route("/notes/<int:id>/hard", methods=["DELETE"])
@jwt_required()
def hard_delete_note(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    db.session.delete(note)
    db.session.commit()

    return jsonify({"message": "Note permanently deleted"})

# FAVORITAR/DESFAVORITAR
        # PATCH envia apenas os campos específicos a serem modificados 
@app.route("/notes/<int:id>/favorite", methods=["PATCH"])
@jwt_required()
def toggle_favorite(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    data = request.get_json(silent=True) or {}
    # Se enviar {"is_favorite": true/false}, usa isso. Se não enviar, inverte (toggle).
    if "is_favorite" in data:
        note.is_favorite = bool(data["is_favorite"])
    else:
        note.is_favorite = not note.is_favorite

    db.session.commit()
    return jsonify({"message": "Favorite updated", "note": note.to_dict()})

# PIN/UNPIN
        # PATCH envia apenas os campos específicos a serem modificados 
@app.route("/notes/<int:id>/pin", methods=["PATCH"])
@jwt_required()
def toggle_pin(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    data = request.get_json(silent=True) or {}
    # Se enviar {"is_pinned": true/false}, usa isso. Se não enviar, inverte (toggle).
    if "is_pinned" in data:
        note.is_pinned = bool(data["is_pinned"])
    else:
        note.is_pinned = not note.is_pinned

    db.session.commit()
    return jsonify({"message": "Pin updated", "note": note.to_dict()})

# CRUD REMINDERS
@app.route("/reminders", methods=["POST"])
@jwt_required()
def create_reminder():
    data = request.get_json() or {}

    title = data.get("title")
    scheduled_at = data.get("scheduled_at")  # ISO string
    if not title or not scheduled_at:
        return jsonify({"message": "title and scheduled_at are required"}), 400

    user_id = int(get_jwt_identity())

    try:
        dt = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return jsonify({"message": "scheduled_at must be ISO format"}), 400

    reminder = Reminder(
        title=title,
        details=data.get("details", ""),
        scheduled_at=dt,
        user_id=user_id,
    )

    db.session.add(reminder)
    db.session.commit()

    return jsonify(reminder.to_dict()), 201


@app.route("/reminders", methods=["GET"])
@jwt_required()
def list_reminders():
    user_id = int(get_jwt_identity())

    # ordena pelos próximos
    reminders = (
        Reminder.query
        .filter_by(user_id=user_id)
        .order_by(Reminder.scheduled_at.asc())
        .all()
    )

    return jsonify({
        "reminders": [r.to_dict() for r in reminders],
        "total": len(reminders),
    })


@app.route("/reminders/<int:id>", methods=["GET"])
@jwt_required()
def get_reminder(id):
    user_id = int(get_jwt_identity())
    reminder = Reminder.query.filter_by(id=id, user_id=user_id).first()
    if not reminder:
        return jsonify({"message": "Reminder not found"}), 404
    return jsonify(reminder.to_dict())


@app.route("/reminders/<int:id>", methods=["PUT"])
@jwt_required()
def update_reminder(id):
    user_id = int(get_jwt_identity())
    reminder = Reminder.query.filter_by(id=id, user_id=user_id).first()
    if not reminder:
        return jsonify({"message": "Reminder not found"}), 404

    data = request.get_json() or {}

    if "title" in data:
        reminder.title = data["title"]

    if "details" in data:
        reminder.details = data["details"]

    if "scheduled_at" in data:
        try:
            reminder.scheduled_at = datetime.fromisoformat(data["scheduled_at"])
        except ValueError:
            return jsonify({"message": "scheduled_at must be ISO format"}), 400

    db.session.commit()
    return jsonify(reminder.to_dict())


@app.route("/reminders/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_reminder(id):
    user_id = int(get_jwt_identity())
    reminder = Reminder.query.filter_by(id=id, user_id=user_id).first()
    if not reminder:
        return jsonify({"message": "Reminder not found"}), 404

    db.session.delete(reminder)
    db.session.commit()
    return jsonify({"message": "Reminder deleted"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)



