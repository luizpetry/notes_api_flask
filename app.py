# Main application file
from flask import Flask, jsonify, request 
from models.note import Note # Importa a class Note do models/note.py
from datetime import datetime
from extensions import db, migrate # Importa as instancias/objetos db e migrate de extensions.py

app = Flask(__name__)

# Guarda todas as notas criadas na lista
notes = []
# Controla o id de cada nota
id_note_control = 1

# CREATE
@app.route('/notes', methods=['POST'])
def create_note():
    global id_note_control # Permite acessar a variável global id_note_control
    data = request.get_json() # Pega o corpo da requisição e converte para um dicionário

    new_note = Note(id = id_note_control, title = data['title'], content= data['content'], created_at= datetime.now())
    id_note_control += 1
    notes.append(new_note)

    return jsonify({"message": "Note created  successfully", "id": new_note.id})

# READ
@app.route('/notes', methods=['GET'])
def get_notes():
    notes_list = [note.to_dict() for note in notes]

    output = {
        "notes": notes_list,
        "total_notes": len(notes_list)
    }

    return jsonify(output)



# READ SPECIFIC ID 
@app.route('/notes/<int:id>', methods=['GET'])
def get_note(id):
    for n in notes:
        if n.id == id:
            return jsonify(n.to_dict())

    return jsonify({"message": "This note ID not found"}), 404

# UPDATE
@app.route('/notes/<int:id>', methods=['PUT'])
def update_note(id):
    note = None
    for n in notes:
        if n.id == id:
            note = n
            break

    if note == None:
        return jsonify({"message": "This note not found"}), 404

    data = request.get_json()
    
    # Atualiza apenas os campos que foram enviados
    if 'title' in data:
        note.title = data['title']
    if 'content' in data:
        note.content = data['content']
    
    return jsonify({"message": "Note has been updated successfully"})

# DELETE
@app.route("/notes/<int:id>", methods=['DELETE'])
def delete_note(id):
    note = None
    for n in notes:
        if n.id == id:
            note = n
            break
    
    if note == None:
        return jsonify({"message": "Note not found"}), 404

    notes.remove(note)
    return jsonify({"message": "Note has been deleted successfully"})


if __name__ == "__main__":
    app.run(debug=True)

