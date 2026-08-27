#!/usr/bin/env python3
"""Batch uploader for WR course materials (apostilas).

Uploads the 47 unique PDF apostilas to private storage via the platform API.

Flow per PDF:
  1. Compute SHA-256 locally
  2. Validate against manifest SHA
  3. Look up course by code via API
  4. Check if material already exists (SKIP_DUPLICATE)
  5. Request presigned upload URL from API
  6. PUT the PDF directly to storage
  7. Call /complete to finalize the CourseMaterial record

Usage:
  python -m app.scripts.upload_wr_course_materials --dry-run
  python -m app.scripts.upload_wr_course_materials --apply
  python -m app.scripts.upload_wr_course_materials --apply --api-url https://wr-api-production.up.railway.app

Authentication:
  Set WR_ADMIN_EMAIL and WR_ADMIN_PASSWORD environment variables,
  OR set WR_ADMIN_TOKEN to a pre-existing JWT.

  The script authenticates via POST /api/v1/auth/login and uses the
  resulting Bearer token for all subsequent requests.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Manifest path (relative to api/ directory when running as module)
MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wr_course_content_manifest.json"
PDF_SOURCE_DIR = Path(os.environ.get("WR_PDF_SOURCE_DIR", "/home/leonardo/Documentos/Apostilas-WR-Cursos"))

# Tenant slug for authentication
TENANT_SLUG = "wr"
DEFAULT_API_URL = "http://localhost:8000"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


async def login(client: httpx.AsyncClient, api_url: str) -> str:
    """Authenticate and return a Bearer token."""
    token = os.environ.get("WR_ADMIN_TOKEN")
    if token:
        return token

    email = os.environ.get("WR_ADMIN_EMAIL")
    password = os.environ.get("WR_ADMIN_PASSWORD")
    if not email or not password:
        print("ERROR: Set WR_ADMIN_EMAIL and WR_ADMIN_PASSWORD, or WR_ADMIN_TOKEN")
        sys.exit(1)

    response = await client.post(
        f"{api_url}/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Slug": TENANT_SLUG, "Origin": "https://wr-cursos-demo.vercel.app"},
    )
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} {response.text}")
        sys.exit(1)

    data = response.json()
    token = data.get("access_token")
    if not token:
        print(f"Login response missing access_token: {data}")
        sys.exit(1)
    return token


async def fetch_courses(client: httpx.AsyncClient, api_url: str, token: str) -> dict[str, str]:
    """Fetch all active WR courses and return {code: course_id}."""
    response = await client.get(
        f"{api_url}/api/v1/courses/?limit=100",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": TENANT_SLUG,
            "Origin": "https://wr-cursos-demo.vercel.app",
        },
    )
    if response.status_code != 200:
        print(f"Failed to fetch courses: {response.status_code} {response.text}")
        sys.exit(1)

    courses = response.json()
    return {c["code"]: c["id"] for c in courses if c.get("is_active", True)}


async def check_existing_material(
    client: httpx.AsyncClient,
    api_url: str,
    token: str,
    course_id: str,
) -> list[dict]:
    """Check if course already has active materials."""
    response = await client.get(
        f"{api_url}/api/v1/courses/{course_id}/materials",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": TENANT_SLUG,
            "Origin": "https://wr-cursos-demo.vercel.app",
        },
    )
    if response.status_code == 200:
        return response.json()
    return []


async def upload_single_material(
    client: httpx.AsyncClient,
    api_url: str,
    token: str,
    course_id: str,
    pdf_path: Path,
    sha256: str,
    title: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Upload a single PDF as a course material."""
    size_bytes = pdf_path.stat().st_size

    # Step 1: Request presigned upload URL
    response = await client.post(
        f"{api_url}/api/v1/courses/{course_id}/materials/upload-url",
        json={
            "filename": pdf_path.name,
            "mime_type": "application/pdf",
            "size_bytes": size_bytes,
            "sha256": sha256,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": TENANT_SLUG,
            "Origin": "https://wr-cursos-demo.vercel.app",
        },
    )

    if response.status_code == 409:
        return {"status": "SKIP_DUPLICATE", "sha256": sha256}
    if response.status_code != 200:
        return {"status": "ERROR", "step": "upload-url", "code": response.status_code, "body": response.text[:200]}

    upload_data = response.json()
    upload_url = upload_data["upload_url"]
    storage_key = upload_data["storage_key"]

    if dry_run:
        return {"status": "WOULD_UPLOAD", "sha256": sha256, "storage_key": storage_key}

    # Step 2: PUT the PDF directly to storage
    file_data = pdf_path.read_bytes()
    put_response = await client.put(
        upload_url,
        content=file_data,
        headers={"Content-Type": "application/pdf"},
    )

    if put_response.status_code not in (200, 204):
        return {
            "status": "ERROR",
            "step": "put_to_storage",
            "code": put_response.status_code,
            "body": put_response.text[:200] if put_response.text else "",
        }

    # Step 3: Complete the upload
    complete_response = await client.post(
        f"{api_url}/api/v1/courses/{course_id}/materials/complete",
        json={
            "storage_key": storage_key,
            "title": title,
            "mime_type": "application/pdf",
            "size_bytes": size_bytes,
            "sha256": sha256,
            "document_type": "APOSTILA",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": TENANT_SLUG,
            "Origin": "https://wr-cursos-demo.vercel.app",
        },
    )

    if complete_response.status_code == 409:
        return {"status": "SKIP_DUPLICATE", "sha256": sha256}
    if complete_response.status_code != 201:
        return {
            "status": "ERROR",
            "step": "complete",
            "code": complete_response.status_code,
            "body": complete_response.text[:200],
        }

    material = complete_response.json()
    return {"status": "UPLOADED", "sha256": sha256, "material_id": material["id"], "storage_key": storage_key}


async def main():
    parser = argparse.ArgumentParser(description="Upload WR course materials (apostilas)")
    parser.add_argument("--dry-run", action="store_true", help="Check without uploading")
    parser.add_argument("--apply", action="store_true", help="Upload for real")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("WR_API_URL", DEFAULT_API_URL),
        help="API base URL",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply")
        sys.exit(1)

    # Load manifest
    manifest = json.loads(MANIFEST_PATH.read_text())

    courses = manifest["courses"]
    print(f"Manifest: {len(courses)} courses")
    print(f"PDF source: {PDF_SOURCE_DIR}")
    print(f"API: {args.api_url}")
    print()

    # Phase 1: Validate all PDFs locally (SHA check)
    report: dict[str, list] = {
        "FOUND": [],
        "MISSING": [],
        "SHA_MATCH": [],
        "SHA_MISMATCH": [],
        "ALREADY_UPLOADED": [],
        "UPLOADED": [],
        "SKIP_DUPLICATE": [],
        "WOULD_UPLOAD": [],
        "ERROR": [],
    }

    pdf_map: dict[str, Path] = {}
    sha_map: dict[str, str] = {}

    for entry in courses:
        code = entry["code"]
        filename = entry["source_pdf"]["filename"]
        expected_sha = entry["source_pdf"]["sha256"].lower()
        pdf_path = PDF_SOURCE_DIR / filename

        if not pdf_path.exists():
            report["MISSING"].append({"code": code, "filename": filename})
            continue

        report["FOUND"].append({"code": code, "filename": filename})
        pdf_map[code] = pdf_path

        actual_sha = compute_sha256(pdf_path)
        if actual_sha == expected_sha:
            report["SHA_MATCH"].append({"code": code, "sha256": actual_sha})
            sha_map[code] = actual_sha
        else:
            report["SHA_MISMATCH"].append({
                "code": code,
                "expected": expected_sha,
                "actual": actual_sha,
            })

    print(f"FOUND: {len(report['FOUND'])}")
    print(f"MISSING: {len(report['MISSING'])}")
    print(f"SHA_MATCH: {len(report['SHA_MATCH'])}")
    print(f"SHA_MISMATCH: {len(report['SHA_MISMATCH'])}")
    print()

    if report["MISSING"]:
        print("MISSING PDFs:")
        for m in report["MISSING"]:
            print(f"  {m['code']}: {m['filename']}")
        print()

    if report["SHA_MISMATCH"]:
        print("SHA MISMATCHES:")
        for m in report["SHA_MISMATCH"]:
            print(f"  {m['code']}: expected={m['expected'][:16]}... actual={m['actual'][:16]}...")
        print()

    # Phase 2: Upload (only if all SHA match)
    valid_codes = set(sha_map.keys())
    if len(valid_codes) < len(courses):
        print(f"Only {len(valid_codes)}/{len(courses)} PDFs validated. Stopping before upload.")
        print("\n".join([f"  {s}: {len(v)}" for s, v in report.items() if v]))
        sys.exit(1)

    if not args.apply and not args.dry_run:
        return

    # Authenticate
    async with httpx.AsyncClient(timeout=300.0) as client:
        token = await login(client, args.api_url)
        print("Authenticated successfully")
        print()

        # Fetch course IDs
        course_map = await fetch_courses(client, args.api_url, token)
        print(f"Fetched {len(course_map)} active courses from API")
        print()

        # Check existing materials
        for code in valid_codes:
            course_id = course_map.get(code)
            if not course_id:
                report["ERROR"].append({"code": code, "reason": "Course not found in API"})
                continue

            existing = await check_existing_material(client, args.api_url, token, course_id)
            if existing:
                report["ALREADY_UPLOADED"].append({"code": code, "count": len(existing)})
                continue

            if args.dry_run:
                report["WOULD_UPLOAD"].append({"code": code, "sha256": sha_map[code]})
                continue

            # Upload
            entry = next(e for e in courses if e["code"] == code)
            title = entry["name"]
            result = await upload_single_material(
                client, args.api_url, token, course_id,
                pdf_map[code], sha_map[code], title, args.dry_run,
            )
            status_key = result["status"]
            if status_key in report:
                report[status_key].append({"code": code, **{k: v for k, v in result.items() if k != "status"}})
            else:
                report["ERROR"].append({"code": code, "result": result})

    # Summary
    print()
    print("=" * 60)
    print("  UPLOAD REPORT")
    print("=" * 60)
    for key in ["FOUND", "MISSING", "SHA_MATCH", "SHA_MISMATCH",
                "ALREADY_UPLOADED", "UPLOADED", "SKIP_DUPLICATE",
                "WOULD_UPLOAD", "ERROR"]:
        if report[key]:
            print(f"  {key} ({len(report[key])}):")
            for item in report[key]:
                print(f"    - {item}")
    print()
    total_actions = sum(len(v) for v in report.values())
    print(f"  Total: {total_actions}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
