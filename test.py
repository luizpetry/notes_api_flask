import pytest
import werkzeug
from app import app
from extensions import db
from models.user import User
from models.note import Note
from werkzeug.security import generate_password_hash

# Compat: algumas versões recentes do Werkzeug não possuem __version__,
# mas o Flask espera esse atributo nos testes.
if not getattr(werkzeug, "__version__", None):
    werkzeug.__version__ = "3.1.0"


@pytest.fixture
def client():
    """
    Configura um app de teste com banco em memória para cada teste.
    """
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.create_all()

        # Usuário padrão para autenticação nos testes (garante que não duplica)
        existing = User.query.filter_by(email="test@example.com").first()
        if not existing:
            user = User(
                name="Test User",
                email="test@example.com",
                password_hash=generate_password_hash("password123"),
            )
            db.session.add(user)
            db.session.commit()

        with app.test_client() as client:
            yield client

        db.session.remove()
        db.drop_all()


def get_auth_headers(client, email="test@example.com", password="password123"):
    """
    Faz login e retorna o header Authorization com Bearer token.
    """
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_register_success(self, client):
        response = client.post(
            "/auth/register",
            json={
                "name": "Novo User",
                "email": "novo@example.com",
                "password": "senha123",
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "User created successfully"

    def test_register_missing_fields(self, client):
        response = client.post("/auth/register", json={"email": "no-name@example.com"})
        assert response.status_code == 400
        data = response.get_json()
        assert data["message"] == "name, email and password are required"

    def test_register_email_conflict(self, client):
        # email já existe (criado no fixture)
        response = client.post(
            "/auth/register",
            json={
                "name": "Outro",
                "email": "test@example.com",
                "password": "senha",
            },
        )
        assert response.status_code == 409
        data = response.get_json()
        assert data["message"] == "Email already exists"

    def test_login_success(self, client):
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_missing_fields(self, client):
        response = client.post("/auth/login", json={"email": "test@example.com"})
        assert response.status_code == 400
        data = response.get_json()
        assert data["message"] == "email and password are required"

    def test_login_invalid_credentials(self, client):
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["message"] == "Invalid credentials"


class TestNotesCRUD:
    def test_create_note_success(self, client):
        headers = get_auth_headers(client)
        response = client.post(
            "/notes",
            json={"title": "Test Note", "content": "Content"},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "Note created successfully"
        assert "id" in data

    def test_create_note_missing_title(self, client):
        headers = get_auth_headers(client)
        response = client.post(
            "/notes",
            json={"content": "Sem título"},
            headers=headers,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["message"] == "Title is required"

    def test_get_notes_empty(self, client):
        headers = get_auth_headers(client)
        response = client.get("/notes", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["notes"] == []
        assert data["total_notes"] == 0

    def test_get_notes_with_data(self, client):
        headers = get_auth_headers(client)
        # cria duas notas
        client.post("/notes", json={"title": "N1"}, headers=headers)
        client.post("/notes", json={"title": "N2"}, headers=headers)

        response = client.get("/notes", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_notes"] == 2
        titles = [n["title"] for n in data["notes"]]
        assert "N1" in titles and "N2" in titles

    def test_get_note_by_id_success(self, client):
        headers = get_auth_headers(client)
        create_resp = client.post(
            "/notes",
            json={"title": "Unique", "content": "X"},
            headers=headers,
        )
        note_id = create_resp.get_json()["id"]

        response = client.get(f"/notes/{note_id}", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == note_id
        assert data["title"] == "Unique"

    def test_get_note_by_id_not_found(self, client):
        headers = get_auth_headers(client)
        response = client.get("/notes/999", headers=headers)
        assert response.status_code == 404
        data = response.get_json()
        assert data["message"] == "Note not found"

    def test_update_note_success(self, client):
        headers = get_auth_headers(client)
        create_resp = client.post(
            "/notes",
            json={"title": "Old", "content": "Old content"},
            headers=headers,
        )
        note_id = create_resp.get_json()["id"]

        response = client.put(
            f"/notes/{note_id}",
            json={"title": "New", "content": "New content"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Note updated successfully"

    def test_update_note_not_found(self, client):
        headers = get_auth_headers(client)
        response = client.put(
            "/notes/999",
            json={"title": "New"},
            headers=headers,
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["message"] == "Note not found"

    def test_delete_note_soft(self, client):
        headers = get_auth_headers(client)
        create_resp = client.post(
            "/notes",
            json={"title": "To delete"},
            headers=headers,
        )
        note_id = create_resp.get_json()["id"]

        response = client.delete(f"/notes/{note_id}", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Note moved to trash"

    def test_delete_note_not_found(self, client):
        headers = get_auth_headers(client)
        response = client.delete("/notes/999", headers=headers)
        assert response.status_code == 404
        data = response.get_json()
        assert data["message"] == "Note not found"


class TestTrashAndRestore:
    def test_trash_flow(self, client):
        headers = get_auth_headers(client)

        # cria nota
        create_resp = client.post(
            "/notes",
            json={"title": "Trash me"},
            headers=headers,
        )
        note_id = create_resp.get_json()["id"]

        # move para lixeira
        client.delete(f"/notes/{note_id}", headers=headers)

        # lista lixeira
        trash_resp = client.get("/notes/trash", headers=headers)
        assert trash_resp.status_code == 200
        trash_data = trash_resp.get_json()
        assert trash_data["total_trash"] == 1
        assert trash_data["trash"][0]["id"] == note_id

        # restaurar
        restore_resp = client.post(
            f"/notes/{note_id}/restore",
            headers=headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.get_json()["message"] == "Note restored successfully"

        # lixeira vazia novamente
        trash_resp2 = client.get("/notes/trash", headers=headers)
        assert trash_resp2.get_json()["total_trash"] == 0

    def test_restore_not_in_trash(self, client):
        headers = get_auth_headers(client)

        # cria nota mas não deleta
        create_resp = client.post(
            "/notes",
            json={"title": "Never deleted"},
            headers=headers,
        )
        note_id = create_resp.get_json()["id"]

        resp = client.post(f"/notes/{note_id}/restore", headers=headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["message"] == "Note not found in trash"

    def test_hard_delete(self, client):
        headers = get_auth_headers(client)

        create_resp = client.post(
            "/notes",
            json={"title": "Hard delete"},
            headers=headers,
        )
        note_id = create_resp.get_json()["id"]

        resp = client.delete(f"/notes/{note_id}/hard", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Note permanently deleted"

        # não deve mais existir
        get_resp = client.get(f"/notes/{note_id}", headers=headers)
        assert get_resp.status_code == 404
