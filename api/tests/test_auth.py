

async def test_register_user(client, test_user_data):
    response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 200
    assert response.json()["email"] == test_user_data["email"]
    assert response.json()["full_name"] == test_user_data["full_name"]

async def test_register_duplicate_email(client, test_user_data):
    await client.post("/api/v1/auth/register", json=test_user_data)
    response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

async def test_login_success(client, test_user_data):
    await client.post("/api/v1/auth/register", json=test_user_data)
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": test_user_data["email"], "password": test_user_data["password"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"

async def test_login_invalid_credentials(client, test_user_data):
    await client.post("/api/v1/auth/register", json=test_user_data)
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": test_user_data["email"], "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

async def test_login_nonexistent_user(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "nonexistent@example.com", "password": "password"},
    )
    assert response.status_code == 401

async def test_refresh_token(client, test_user_data):
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": test_user_data["email"], "password": test_user_data["password"]},
    )
    refresh_token = login_response.json()["refresh_token"]
    
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
