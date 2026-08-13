import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import UserRole

client = TestClient(app)

def get_admin_token(test_user_data):
    user_data = test_user_data.copy()
    user_data["email"] = "admin@example.com"
    client.post("/api/v1/auth/register", json=user_data)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    return login_response.json()["access_token"]

def test_create_course(test_course_data):
    token = get_admin_token({"email": "admin@example.com", "full_name": "Admin", "password": "pass123"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["code"] == test_course_data["code"]
    assert response.json()["name"] == test_course_data["name"]

def test_list_courses(test_course_data):
    token = get_admin_token({"email": "admin@example.com", "full_name": "Admin", "password": "pass123"})
    headers = {"Authorization": f"Bearer {token}"}
    
    client.post("/api/v1/courses/", json=test_course_data, headers=headers)
    response = client.get("/api/v1/courses/")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_get_course(test_course_data):
    token = get_admin_token({"email": "admin@example.com", "full_name": "Admin", "password": "pass123"})
    headers = {"Authorization": f"Bearer {token}"}
    
    create_response = client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    course_id = create_response.json()["id"]
    
    response = client.get(f"/api/v1/courses/{course_id}")
    assert response.status_code == 200
    assert response.json()["id"] == course_id

def test_update_course(test_course_data):
    token = get_admin_token({"email": "admin@example.com", "full_name": "Admin", "password": "pass123"})
    headers = {"Authorization": f"Bearer {token}"}
    
    create_response = client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    course_id = create_response.json()["id"]
    
    update_data = {"name": "Updated Course Name"}
    response = client.put(
        f"/api/v1/courses/{course_id}",
        json=update_data,
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Course Name"

def test_delete_course(test_course_data):
    token = get_admin_token({"email": "admin@example.com", "full_name": "Admin", "password": "pass123"})
    headers = {"Authorization": f"Bearer {token}"}
    
    create_response = client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    course_id = create_response.json()["id"]
    
    response = client.delete(f"/api/v1/courses/{course_id}", headers=headers)
    assert response.status_code == 204
