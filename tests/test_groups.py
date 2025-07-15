from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_create_group():
    # Créer un groupe
    response = client.post("/v1/groups/", json={"name": "Test Group", "description": "A test group"})
    assert response.status_code == 200
    assert response.json()["status"] == "created"

    # Tenter de créer un groupe avec le même nom
    response = client.post("/v1/groups/", json={"name": "Test Group", "description": "Duplicate group"})
    assert response.status_code == 400
    assert "Group with name Test Group already exists" in response.json()["detail"]

def test_list_groups():
    response = client.get("/v1/groups/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_delete_group():
    # Create a group first
    response = client.post("/v1/groups/", json={"name": "To Delete", "description": "Group to delete"})
    assert response.status_code == 200
    group_id = response.json()["group"]["id"]

    # Then delete it
    response = client.delete(f"/v1/groups/{group_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    # Verify it's deleted
    response = client.delete(f"/v1/groups/{group_id}")
    assert response.status_code == 404