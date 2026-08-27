import hashlib

import pytest

from app.core.config import settings
from tests.test_trusted_certificate_document_pipeline import _ready_for_signature

BASE = "/api/v1/certificate-documents/studio"


@pytest.fixture
def local_certificate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path / "certificate-studio-storage"))
    return tmp_path


async def _create_published_template(client, admin_headers, *, slug="nr-classic"):
    template = await client.post(
        f"{BASE}/templates",
        json={"name": "NR Classic", "slug": slug},
        headers=admin_headers,
    )
    assert template.status_code == 201, template.text
    template = template.json()

    version = await client.post(
        f"{BASE}/templates/{template['id']}/versions",
        json={
            "visual_config": {
                "preset": "MODERN",
                "primary_color": "#0A5C36",
                "secondary_color": "#163A2B",
                "accent_color": "#DDEEE5",
                "background_color": "#FFFFFF",
                "font_family": "HELVETICA",
                "border_style": "DOUBLE",
                "background_style": "LIGHT_TINT",
                "logo_position": "CENTER",
                "qr_position": "LEFT",
                "show_issuer_logo": False,
                "show_secondary_logo": False,
                "show_verification_seal": True,
            }
        },
        headers=admin_headers,
    )
    assert version.status_code == 201, version.text
    version = version.json()
    assert version["status"] == "DRAFT"

    preview = await client.post(
        f"{BASE}/preview",
        json={"visual_config": version["visual_config"]},
        headers=admin_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.content.startswith(b"%PDF")
    assert preview.headers["x-certificate-studio-preview"] == "NO-VALIDITY"
    assert preview.headers["cache-control"] == "no-store"
    assert hashlib.sha256(preview.content).hexdigest() == preview.headers["x-certificate-sha256"]

    published = await client.post(
        f"{BASE}/templates/{template['id']}/versions/{version['id']}/publish",
        headers=admin_headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"
    return template, published.json()


@pytest.mark.asyncio
async def test_studio_is_admin_only_and_visual_schema_rejects_regulatory_facts(client, admin_headers):
    fixture = await _ready_for_signature(client, admin_headers)

    denied = await client.get(f"{BASE}/templates", headers=fixture["student_headers"])
    assert denied.status_code == 403

    invalid = await client.post(
        f"{BASE}/preview",
        json={
            "visual_config": {
                "preset": "CLASSIC",
                "student_name": "Tentativa de sobrescrever fato regulatório",
            }
        },
        headers=admin_headers,
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_published_version_is_immutable_and_assignment_requires_publication(client, admin_headers):
    fixture = await _ready_for_signature(client, admin_headers)
    course_id = fixture["course"]["id"]

    draft_template = await client.post(
        f"{BASE}/templates",
        json={"name": "Draft only", "slug": "draft-only"},
        headers=admin_headers,
    )
    assert draft_template.status_code == 201, draft_template.text
    template_id = draft_template.json()["id"]
    draft = await client.post(
        f"{BASE}/templates/{template_id}/versions",
        json={},
        headers=admin_headers,
    )
    assert draft.status_code == 201, draft.text

    premature = await client.put(
        f"{BASE}/courses/{course_id}/assignment",
        json={"template_id": template_id},
        headers=admin_headers,
    )
    assert premature.status_code == 409

    published = await client.post(
        f"{BASE}/templates/{template_id}/versions/{draft.json()['id']}/publish",
        headers=admin_headers,
    )
    assert published.status_code == 200, published.text

    immutable = await client.patch(
        f"{BASE}/templates/{template_id}/versions/{draft.json()['id']}",
        json={"visual_config": {"primary_color": "#FF0000"}},
        headers=admin_headers,
    )
    assert immutable.status_code == 409

    assigned = await client.put(
        f"{BASE}/courses/{course_id}/assignment",
        json={"template_id": template_id},
        headers=admin_headers,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["template_id"] == template_id


@pytest.mark.asyncio
async def test_trusted_document_freezes_published_visual_version(
    client,
    admin_headers,
    local_certificate_storage,
):
    fixture = await _ready_for_signature(client, admin_headers)
    course_id = fixture["course"]["id"]
    template, v1 = await _create_published_template(client, admin_headers, slug="frozen-template")

    assigned = await client.put(
        f"{BASE}/courses/{course_id}/assignment",
        json={"template_id": template["id"]},
        headers=admin_headers,
    )
    assert assigned.status_code == 200, assigned.text

    resolution = await client.get(f"{BASE}/courses/{course_id}/resolution", headers=admin_headers)
    assert resolution.status_code == 200, resolution.text
    assert resolution.json()["source"] == "TENANT"
    assert resolution.json()["template_version_id"] == v1["id"]

    prepared = await client.post(
        f"/api/v1/certificate-documents/enrollments/{fixture['enrollment']['id']}/prepare",
        headers=admin_headers,
    )
    assert prepared.status_code == 201, prepared.text
    certificate_id = prepared.json()["certificate_id"]

    snapshot_response = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/snapshot",
        headers=admin_headers,
    )
    assert snapshot_response.status_code == 200, snapshot_response.text
    snapshot = snapshot_response.json()["snapshot"]
    visual = snapshot["certificate_template"]
    assert visual["source"] == "TENANT"
    assert visual["template_id"] == template["id"]
    assert visual["template_version_id"] == v1["id"]
    assert visual["version"] == 1
    assert visual["visual_config"]["preset"] == "MODERN"
    assert len(visual["visual_config_sha256"]) == 64

    original = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/original",
        headers=admin_headers,
    )
    assert original.status_code == 200, original.text
    assert original.content.startswith(b"%PDF")
    assert len(original.content) > 500

    # Publishing v2 changes future resolution only. The already-issued document
    # keeps v1 in its immutable regulatory/document snapshot.
    v2 = await client.post(
        f"{BASE}/templates/{template['id']}/versions",
        json={"visual_config": {**v1["visual_config"], "primary_color": "#123456"}},
        headers=admin_headers,
    )
    assert v2.status_code == 201, v2.text
    publish_v2 = await client.post(
        f"{BASE}/templates/{template['id']}/versions/{v2.json()['id']}/publish",
        headers=admin_headers,
    )
    assert publish_v2.status_code == 200, publish_v2.text

    future = await client.get(f"{BASE}/courses/{course_id}/resolution", headers=admin_headers)
    assert future.status_code == 200
    assert future.json()["version"] == 2

    still_frozen = await client.get(
        f"/api/v1/certificate-documents/{certificate_id}/snapshot",
        headers=admin_headers,
    )
    assert still_frozen.json()["snapshot"]["certificate_template"]["version"] == 1
