# Main application file
from flask import Flask, jsonify, request 
from datetime import datetime
from extensions import db, migrate # Importa as instancias/objetos db e migrate de extensions.py
from models.note import Note # Importa a class Note do models/note.py
from models.user import User

app = Flask(__name__)

# Config do DB (SQLite)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///notes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inicializa as extensões do DB antes de rodar o app / CLI
db.init_app(app)
migrate.init_app(app, db)

    # ROTAS
# CREATE
@app.route('/notes', methods=['POST'])
def create_note():
    # or: Se o JSON vier vazio ou inválido, usa um dicionário vazio em vez de None.
    data = request.get_json() or {} # Pega o corpo da requisição e converte para um dicionário

    title = data.get("title")
    if not title:
        return jsonify({"message": "Title is required"}), 404

    note = Note(
        title = title,
        content = data.get("content", ""),
        created_at = datetime.utcnow()
    )

    # Salva a nota em memoria
    db.session.add(note)
    # Executa o que esta pendente no banco de dados
    db.session.commit()

    return jsonify({"message": "Note created successfully", "id": note.id}), 201
    

# READ
@app.route('/notes', methods=['GET'])
def get_notes():
    # Seleciona todas as notas, ordenando de forma decrescente, all() - Executa a consulta e retorna todas as linhas como uma lista de objetos Note
    notes = Note.query.order_by(Note.id.desc()).all()

    notes_list = [note.to_dict() for note in notes]

    output = {
        "notes": notes_list,
        "total_notes": len(notes_list)
    }

    return jsonify(output)

# READ SPECIFIC ID 
@app.route('/notes/<int:id>', methods=['GET'])
def get_note(id):
    note = note.query.get(id)
    if not note:
        return jsonify({"message": "This note ID not found"}), 404

    return jsonify(note.to_dict())

# UPDATE
@app.route('/notes/<int:id>', methods=['PUT'])
def update_note(id):
    note = Note.query.get(id)
    if not note:
        return jsonify({"message": "This note not found"}), 404

    data = request.get_json() or {} # Se get_json() existir, usa ele. Se nao, usa {}

    if "title" in data:
        note.title = data["title"]

    if "content" in data:
        note.content = data["content"]
    
    db.session.commit()
    return jsonify({"message": "Note has been updated successfully"})

# DELETE
@app.route("/notes/<int:id>", methods=['DELETE'])
def delete_note(id):
    note = Note.query.get(id)
    if not note:
        return jsonify({"message": "This note not found"}), 404
    
    db.session.delete()
    db.session.commit()
    return jsonify({"message": "Note has been deleted successfully"})


if __name__ == "__main__":
    app.run(debug=True)



