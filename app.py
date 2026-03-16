# app.py
import os
import re
import secrets
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, migrate
from models.note import Note
from models.user import User
from models.reminder import Reminder

# OTP
from models.otp import OTP
from otp_sender import send_code


load_dotenv()

app = Flask(__name__)
CORS(app)

# Config do DB (SQLite)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///notes.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Config JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-secret")

# OTP (DEV)
app.config["DEV_OTP"] = True

# Inicializa extensões
db.init_app(app)
migrate.init_app(app, db)
jwt = JWTManager(app)


# ==========================
# OTP Helpers
# ==========================
OTP_TTL_MIN = 10
MAX_ATTEMPTS = 5

def normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    phone = re.sub(r"[^\d+]", "", phone)
    return phone

def gen_otp_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


# ==========================
# AUTH (PHONE + OTP)
# ==========================
@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json() or {}

    phone = normalize_phone(data.get("phone"))
    password = data.get("password", "")
    confirm = data.get("confirm_password", "")

    if not phone or not password or not confirm:
        return jsonify({"message": "phone, password and confirm_password are required"}), 400
    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400
    if password != confirm:
        return jsonify({"message": "Passwords do not match"}), 400

    # Se já existe verificado, bloqueia
    user = User.query.filter_by(phone=phone).first()
    if user and user.is_verified:
        return jsonify({"message": "Phone already exists"}), 409

    # Cria usuário (não verificado) ou atualiza senha se já existia não-verificado
    if not user:
        user = User(
            phone=phone,
            password_hash=generate_password_hash(password),
            is_verified=False
        )
        db.session.add(user)
        db.session.flush()  # garante user.id
    else:
        user.password_hash = generate_password_hash(password)

    # Gera OTP
    code = gen_otp_code()
    otp = OTP(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MIN),
        attempts=0,
    )
    db.session.add(otp)
    db.session.commit()

    # Envia (DEV imprime; depois tu troca o plug)
    send_code(phone, code)

    resp = {"message": "OTP sent"}
    if app.config.get("DEV_OTP"):
        resp["dev_code"] = code  # útil em testes
    return jsonify(resp), 201


@app.route("/auth/verify", methods=["POST"])
def auth_verify():
    data = request.get_json() or {}

    phone = normalize_phone(data.get("phone"))
    code = (data.get("code") or "").strip()

    if not phone or not code:
        return jsonify({"message": "phone and code are required"}), 400

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    otp = OTP.query.filter_by(user_id=user.id).order_by(OTP.created_at.desc()).first()
    if not otp:
        return jsonify({"message": "No code found. Resend."}), 400
    if datetime.utcnow() > otp.expires_at:
        return jsonify({"message": "Code expired. Resend."}), 400
    if otp.attempts >= MAX_ATTEMPTS:
        return jsonify({"message": "Too many attempts. Resend a new code."}), 429

    if not check_password_hash(otp.code_hash, code):
        otp.attempts += 1
        db.session.commit()
        return jsonify({"message": "Invalid code"}), 400

    user.is_verified = True
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": access_token, "user": user.to_dict()}), 200


@app.route("/auth/resend", methods=["POST"])
def auth_resend():
    data = request.get_json() or {}

    phone = normalize_phone(data.get("phone"))
    if not phone:
        return jsonify({"message": "phone is required"}), 400

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({"message": "User not found"}), 404
    if user.is_verified:
        return jsonify({"message": "Already verified"}), 400

    code = gen_otp_code()
    otp = OTP(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MIN),
        attempts=0,
    )
    db.session.add(otp)
    db.session.commit()

    send_code(phone, code)

    resp = {"message": "OTP resent"}
    if app.config.get("DEV_OTP"):
        resp["dev_code"] = code
    return jsonify(resp), 200


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}

    phone = normalize_phone(data.get("phone"))
    password = data.get("password", "")

    if not phone or not password:
        return jsonify({"message": "phone and password are required"}), 400

    user = User.query.filter_by(phone=phone).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid credentials"}), 401

    if not user.is_verified:
        return jsonify({"message": "Account not verified"}), 403

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": access_token, "user": user.to_dict()}), 200


# ==========================
# ROTAS NOTES
# ==========================
@app.route("/notes", methods=["POST"])
@jwt_required()
def create_note():
    data = request.get_json() or {}

    title = data.get("title")
    if not title:
        return jsonify({"message": "Title is required"}), 400

    user_id = int(get_jwt_identity())

    note = Note(
        title=title,
        content=data.get("content", ""),
        created_at=datetime.utcnow(),
        user_id=user_id,
    )

    db.session.add(note)
    db.session.commit()

    return jsonify({"message": "Note created successfully", "id": note.id}), 201


@app.route("/notes", methods=["GET"])
@jwt_required()
def get_notes():
    user_id = int(get_jwt_identity())

    search = request.args.get("search")
    favorite = request.args.get("favorite")
    pinned = request.args.get("pinned")
    sort = request.args.get("sort", "recent")

    query = Note.query.filter_by(user_id=user_id, deleted_at=None)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Note.title.ilike(like), Note.content.ilike(like)))

    if favorite is not None:
        if favorite.lower() == "true":
            query = query.filter(Note.is_favorite.is_(True))
        elif favorite.lower() == "false":
            query = query.filter(Note.is_favorite.is_(False))

    if pinned is not None:
        if pinned.lower() == "true":
            query = query.filter(Note.is_pinned.is_(True))
        elif pinned.lower() == "false":
            query = query.filter(Note.is_pinned.is_(False))

    if sort == "oldest":
        query = query.order_by(Note.id.asc())
    else:
        query = query.order_by(Note.is_pinned.desc(), Note.id.desc())

    notes = query.all()

    return jsonify({
        "notes": [n.to_dict() for n in notes],
        "total_notes": len(notes),
    })


@app.route("/notes/<int:id>", methods=["GET"])
@jwt_required()
def get_note(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    return jsonify(note.to_dict())


@app.route("/notes/<int:id>", methods=["PUT"])
@jwt_required()
def update_note(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    data = request.get_json() or {}

    if "title" in data:
        note.title = data["title"]
    if "content" in data:
        note.content = data["content"]

    db.session.commit()
    return jsonify({"message": "Note updated successfully"})


@app.route("/notes/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_note(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    note.deleted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "Note moved to trash"})


# ==========================
# LIXEIRA
# ==========================
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
        "total_trash": len(notes),
    })

# Esvaziar Lixeira
@app.route("/notes/trash/empty", methods=["DELETE"])
@jwt_required()
def empty_trash():
    user_id = int(get_jwt_identity())

    notes = (
        Note.query
        .filter_by(user_id=user_id)
        .filter(Note.deleted_at.isnot(None))
        .all()
    )

    for n in notes:
        db.session.delete(n)

    db.session.commit()
    return jsonify({"message": "Trash emptied"}), 200

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


# ==========================
# FAVORITAR / PIN
# ==========================
@app.route("/notes/<int:id>/favorite", methods=["PATCH"])
@jwt_required()
def toggle_favorite(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_favorite" in data:
        note.is_favorite = bool(data["is_favorite"])
    else:
        note.is_favorite = not note.is_favorite

    db.session.commit()
    return jsonify({"message": "Favorite updated", "note": note.to_dict()})


@app.route("/notes/<int:id>/pin", methods=["PATCH"])
@jwt_required()
def toggle_pin(id):
    user_id = int(get_jwt_identity())

    note = Note.query.filter_by(id=id, user_id=user_id, deleted_at=None).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_pinned" in data:
        note.is_pinned = bool(data["is_pinned"])
    else:
        note.is_pinned = not note.is_pinned

    db.session.commit()
    return jsonify({"message": "Pin updated", "note": note.to_dict()})


# ==========================
# CRUD REMINDERS
# ==========================
@app.route("/reminders", methods=["POST"])
@jwt_required()
def create_reminder():
    data = request.get_json() or {}

    title = data.get("title")
    scheduled_at = data.get("scheduled_at")
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
    app.run(host="0.0.0.0", port=5000, debug=True)