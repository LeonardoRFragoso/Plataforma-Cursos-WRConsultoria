import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_register_user(test_user_data):
    response = client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 200
    assert response.json()["email"] == test_user_data["email"]
    assert response.json()["full_name"] == test_user_data["full_name"]

def test_register_duplicate_email(test_user_data):
    client.post("/api/v1/auth/register", json=test_user_data)
    response = client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

def test_login_success(test_user_data):
    client.post("/api/v1/auth/register", json=test_user_data)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_invalid_credentials(test_user_data):
    client.post("/api/v1/auth/register", json=test_user_data)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data["email"], "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_login_nonexistent_user():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password"},
    )
    assert response.status_code == 401

def test_refresh_token(test_user_data):
    client.post("/api/v1/auth/register", json=test_user_data)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]},
    )
    refresh_token = login_response.json()["refresh_token"]
    
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
