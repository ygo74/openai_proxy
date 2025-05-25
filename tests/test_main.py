from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the OpenAI Proxy!"}

def test_chat_completions():
    payload: dict[str, object] = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "chatcmpl-123"
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "This is a simulated response."