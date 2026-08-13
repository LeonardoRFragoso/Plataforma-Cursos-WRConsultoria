async def test_create_course(client, admin_token, test_course_data):
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = await client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["code"] == test_course_data["code"]
    assert response.json()["name"] == test_course_data["name"]


async def test_list_courses(client, admin_token, test_course_data):
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post("/api/v1/courses/", json=test_course_data, headers=headers)
    response = await client.get("/api/v1/courses/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) > 0


async def test_get_course(client, admin_token, test_course_data):
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = await client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    course_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/courses/{course_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == course_id


async def test_update_course(client, admin_token, test_course_data):
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = await client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    course_id = create_response.json()["id"]

    update_data = {"name": "Updated Course Name"}
    response = await client.put(
        f"/api/v1/courses/{course_id}",
        json=update_data,
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Course Name"


async def test_delete_course(client, admin_token, test_course_data):
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = await client.post(
        "/api/v1/courses/",
        json=test_course_data,
        headers=headers,
    )
    course_id = create_response.json()["id"]

    response = await client.delete(f"/api/v1/courses/{course_id}", headers=headers)
    assert response.status_code == 204
