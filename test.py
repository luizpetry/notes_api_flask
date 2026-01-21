import pytest
from app import *
from models.note import Note
from datetime import datetime


@pytest.fixture
def client():
    # Cria um cliente de teste para a aplicação Flask
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_state():
    # Reseta o estado global antes de cada teste
    global notes, id_note_control
    notes.clear()
    id_note_control = 1
    yield
    notes.clear()
    id_note_control = 1


class TestCreateNote:
    # Testes para criação de notas
    
    def test_create_note_success(self, client):
        #  esta criação de nota com sucesso
        response = client.post('/notes', 
                              json={'title': 'Test Note', 'content': 'This is a test note'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Note created  successfully'
        assert data['id'] == 1
        assert len(notes) == 1
        assert notes[0].title == 'Test Note'
        assert notes[0].content == 'This is a test note'
    
    def test_create_multiple_notes(self, client):
        # Testa criação de múltiplas notas com IDs incrementais
        client.post('/notes', json={'title': 'Note 1', 'content': 'Content 1'})
        client.post('/notes', json={'title': 'Note 2', 'content': 'Content 2'})
        client.post('/notes', json={'title': 'Note 3', 'content': 'Content 3'})
        
        assert len(notes) == 3
        assert notes[0].id == 1
        assert notes[1].id == 2
        assert notes[2].id == 3


class TestGetNotes:
    # Testes para listagem de notas#
    
    def test_get_empty_notes_list(self, client):
        # Testa listagem quando não há notas
        response = client.get('/notes')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['notes'] == []
        assert data['total_notes'] == 0
    
    def test_get_all_notes(self, client):
        # Testa listagem de todas as notas
        #  Cria algumas notas
        client.post('/notes', json={'title': 'Note 1', 'content': 'Content 1'})
        client.post('/notes', json={'title': 'Note 2', 'content': 'Content 2'})
        
        response = client.get('/notes')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['total_notes'] == 2
        assert len(data['notes']) == 2
        assert data['notes'][0]['title'] == 'Note 1'
        assert data['notes'][1]['title'] == 'Note 2'


class TestGetNoteById:
    # Testes para buscar nota por ID
    
    def test_get_note_by_id_success(self, client):
        # Testa busca de nota existente por ID
        client.post('/notes', json={'title': 'Test Note', 'content': 'Test Content'})
        
        response = client.get('/notes/1')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == 1
        assert data['title'] == 'Test Note'
        assert data['content'] == 'Test Content'
        assert 'created_at' in data
    
    def test_get_note_by_id_not_found(self, client):
        # Testa busca de nota inexistente
        response = client.get('/notes/999')
        
        assert response.status_code == 404
        data = response.get_jsown()
        assert data['message'] == 'This note ID not found'


class TestUpdateNote:
    # Testes para atualização de notas#
    
    def test_update_note_success(self, client):
        # Testa atualização completa de nota
        client.post('/notes', json={'title': 'Original Title', 'content': 'Original Content'})
        
        response = client.put('/notes/1', 
                             json={'title': 'Updated Title', 'content': 'Updated Content'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Note has been updated successfully'
        assert notes[0].title == 'Updated Title'
        assert notes[0].content == 'Updated Content'
    
    def test_update_note_partial_title(self, client):
        # Testa atualização apenas do título 
        client.post('/notes', json={'title': 'Original Title', 'content': 'Original Content'})
        
        response = client.put('/notes/1', json={'title': 'New Title'})
        
        assert response.status_code == 200
        assert notes[0].title == 'New Title'
        assert notes[0].content == 'Original Content'  #  Não deve mudar
    
    def test_update_note_partial_content(self, client):
        # Testa atualização apenas do conteúdo 
        client.post('/notes', json={'title': 'Original Title', 'content': 'Original Content'})
        
        response = client.put('/notes/1', json={'content': 'New Content'})
        
        assert response.status_code == 200
        assert notes[0].title == 'Original Title'  #  Não deve mudar
        assert notes[0].content == 'New Content'
    
    def test_update_note_not_found(self, client):
        # Testa atualização de nota inexistente 
        response = client.put('/notes/999', json={'title': 'New Title'})
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['message'] == 'This note not found'


class TestDeleteNote:
    # Testes para deleção de notas 
    
    def test_delete_note_success(self, client):
        # Testa deleção de nota existente 
        client.post('/notes', json={'title': 'Note to Delete', 'content': 'Content'})
        assert len(notes) == 1
        
        response = client.delete('/notes/1')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Note has been deleted successfully'
        assert len(notes) == 0
    
    def test_delete_note_not_found(self, client):
        # Testa deleção de nota inexistente# 
        response = client.delete('/notes/999')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['message'] == 'Note not found'
    
    def test_delete_multiple_notes(self, client):
        # Testa deleção de múltiplas notas# 
        client.post('/notes', json={'title': 'Note 1', 'content': 'Content 1'})
        client.post('/notes', json={'title': 'Note 2', 'content': 'Content 2'})
        client.post('/notes', json={'title': 'Note 3', 'content': 'Content 3'})
        
        assert len(notes) == 3
        
        client.delete('/notes/2')
        assert len(notes) == 2
        assert notes[0].id == 1
        assert notes[1].id == 3


class TestNoteModel:
    # Testes para o modelo Note# 
    
    def test_note_initialization(self):
        # Testa inicialização do modelo Note# 
        note = Note(id=1, title='Test', content='Content', created_at=datetime.now())
        
        assert note.id == 1
        assert note.title == 'Test'
        assert note.content == 'Content'
        assert isinstance(note.created_at, datetime)
    
    def test_note_to_dict(self):
        # Testa conversão de Note para dicionário# 
        created_at = datetime.now()
        note = Note(id=1, title='Test', content='Content', created_at=created_at)
        
        note_dict = note.to_dict()
        
        assert note_dict['id'] == 1
        assert note_dict['title'] == 'Test'
        assert note_dict['content'] == 'Content'
        assert note_dict['created_at'] == created_at
        assert isinstance(note_dict, dict)
