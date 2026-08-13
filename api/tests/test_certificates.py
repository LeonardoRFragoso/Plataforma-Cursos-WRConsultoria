



async def test_validate_certificate_not_found(client):
    """Deve retornar valid=False para um código de validação inexistente."""
    response = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": "CODIGO-INVALIDO-1234567890"},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


async def test_validate_certificate_missing_code(client):
    """Deve retornar um erro quando o código de validação não é enviado."""
    response = await client.post("/api/v1/certificates/validate", json={})
    assert response.status_code == 422
