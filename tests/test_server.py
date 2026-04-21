import pytest
from fastapi.testclient import TestClient
from adapters.server import app

client = TestClient(app)

def test_providers_endpoint():
    response = client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert all("name" in p for p in data)

def test_chat_endpoint_empty_text():
    response = client.post("/api/chat", json={"text": "", "provider": "kimi"})
    assert response.status_code == 400

def test_upload_endpoint_missing_file():
    response = client.post("/api/upload")
    assert response.status_code == 422