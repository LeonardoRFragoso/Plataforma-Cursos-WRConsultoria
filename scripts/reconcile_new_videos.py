#!/usr/bin/env python3
"""Reconcile newly uploaded bucket videos with platform lessons.

Read-only phases (default / --dry-run):
  1. Fetch all courses + lessons from the production API (admin token).
  2. List current bucket objects (read-only).
  3. Compare against the baseline snapshot (remote-video-inventory-after.json).
  4. Classify each object: EXISTING_BASELINE, NEW_VIDEO, NEW_NON_VIDEO,
     CHANGED_EXISTING, DUPLICATE_CONTENT, UNKNOWN.
  5. Map each NEW_VIDEO to a lesson using deterministic evidence
     (storage_key path IDs > metadata > filename pattern).
  6. Write reconciliation matrix + delta report.

Write phase (--apply):
  - Create Lesson rows when mapping is EXACT and lesson is missing.
  - Link storage_key on existing lessons when ALREADY_LINKED is false.
  - Never overwrite an existing storage_key (CONFLICT instead).

Idempotent: re-running yields TO_CREATE=0, TO_LINK=0, ALREADY_CORRECT=N.

Usage:
  python scripts/reconcile_new_videos.py --dry-run
  python scripts/reconcile_new_videos.py --apply
  python scripts/reconcile_new_videos.py --reconcile-only   # bucket+DB snapshot only

Env vars (loaded from Railway):
  STORAGE_ENDPOINT, STORAGE_BUCKET, STORAGE_REGION, STORAGE_ACCESS_KEY,
  STORAGE_SECRET_KEY
  API_BASE_URL, API_ADMIN_EMAIL, API_ADMIN_PASSWORD
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "analysis" / "storage"
BASELINE = ANALYSIS / "remote-video-inventory-after.json"
DB_MAP_BASELINE = ANALYSIS / "db-lesson-mapping-full.json"
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi"}
TENANT_ID = "11111111-1111-1111-1111-111111111111"

# ─── Storage client ──────────────────────────────────────────────────────

def get_s3():
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("STORAGE_ENDPOINT") or None,
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_KEY"],
        region_name=os.environ.get("STORAGE_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )
    return s3, os.environ["STORAGE_BUCKET"]


def list_bucket(s3, bucket, prefix="tenants/"):
    """List all objects with head metadata for video keys."""
    objects = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            o = {
                "key": obj["Key"],
                "size": obj["Size"],
                "etag": obj.get("ETag", "").strip('"'),
                "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
            }
            objects.append(o)
    # Enrich video keys with head_object
    for o in objects:
        ext = Path(o["key"]).suffix.lower()
        if ext in VIDEO_EXTS:
            try:
                head = s3.head_object(Bucket=bucket, Key=o["key"])
                o["content_type"] = head.get("ContentType")
                o["content_length"] = head.get("ContentLength")
                o["metadata"] = dict(head.get("Metadata", {}))
            except ClientError as exc:
                o["head_error"] = str(exc)
    return objects


# ─── API client ──────────────────────────────────────────────────────────

class APIClient:
    def __init__(self, base_url, email, password):
        self.base = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30, follow_redirects=True)
        self.token = self._login(email, password)

    def _login(self, email, password):
        r = self.client.post(
            f"{self.base}/api/v1/auth/login",
            json={"identifier": email, "password": password},
        )
        r.raise_for_status()
        return r.json()["access_token"]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, **kw):
        r = self.client.get(f"{self.base}{path}", headers=self.headers, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path, **kw):
        r = self.client.post(f"{self.base}{path}", headers=self.headers, **kw)
        return r

    def patch(self, path, **kw):
        r = self.client.patch(f"{self.base}{path}", headers=self.headers, **kw)
        return r


def fetch_courses(api):
    courses = api.get("/api/v1/courses", params={"skip": 0, "limit": 500})
    if isinstance(courses, dict) and "items" in courses:
        return courses["items"]
    return courses


def fetch_lessons(api, course_id):
    return api.get(f"/api/v1/lessons/courses/{course_id}/lessons")


# ─── Delta computation ───────────────────────────────────────────────────

def load_baseline():
    if not BASELINE.exists():
        return {}
    data = json.loads(BASELINE.read_text())
    return {o["key"]: o for o in data.get("objects", [])}


def classify_object(key, current, baseline_map, current_video_keys):
    ext = Path(key).suffix.lower()
    is_video = ext in VIDEO_EXTS
    if key in baseline_map:
        base = baseline_map[key]
        if base.get("size") == current.get("size") and base.get("etag") == current.get("etag"):
            return "EXISTING_BASELINE"
        return "CHANGED_EXISTING"
    # Not in baseline → new
    if not is_video:
        return "NEW_NON_VIDEO"
    return "NEW_VIDEO"


def compute_delta(current_objects, baseline_map):
    current_keys = {o["key"] for o in current_objects}
    baseline_keys = set(baseline_map.keys())

    classifications = []
    for o in current_objects:
        cls = classify_object(o["key"], o, baseline_map, None)
        classifications.append({**o, "classification": cls})

    # Detect duplicates by size+etag among new videos
    new_videos = [c for c in classifications if c["classification"] == "NEW_VIDEO"]
    sig_map = {}  # (size, etag) -> first key
    for nv in new_videos:
        sig = (nv["size"], nv["etag"])
        if sig in sig_map:
            nv["classification"] = "DUPLICATE_CONTENT"
            nv["duplicate_of"] = sig_map[sig]
        else:
            sig_map[sig] = nv["key"]

    # Also check if new video duplicates a baseline video by size+etag
    for nv in new_videos:
        if nv["classification"] != "DUPLICATE_CONTENT":
            sig = (nv["size"], nv["etag"])
            for bk, bv in baseline_map.items():
                if bv.get("size") == sig[0] and bv.get("etag") == sig[1]:
                    nv["classification"] = "DUPLICATE_CONTENT"
                    nv["duplicate_of"] = bk
                    break

    # Baseline keys that disappeared
    missing_baseline = list(baseline_keys - current_keys)

    counts = {}
    for c in classifications:
        counts[c["classification"]] = counts.get(c["classification"], 0) + 1

    return {
        "baseline_total": len(baseline_map),
        "current_total": len(current_objects),
        "classifications": classifications,
        "counts": counts,
        "missing_baseline_keys": missing_baseline,
    }


# ─── Video → Lesson mapping ──────────────────────────────────────────────

# Pattern: tenants/{tenant}/courses/{course}/lessons/{lesson}/video/{filename}
KEY_RE = re.compile(
    r"^tenants/([^/]+)/courses/([^/]+)/lessons/([^/]+)/video/(.+)$"
)
# Legacy: lessons/{lesson}/{filename}
LEGACY_KEY_RE = re.compile(r"^lessons/([^/]+)/(.+)$")

# Filename patterns: nr06-aula-01.mp4, nr11-plataforma-aula-02.mp4, etc.
FILENAME_RE = re.compile(
    r"^(nr\d+)-([a-z0-9]+)-aula-(\d+)\.", re.IGNORECASE
)
# Simpler: nr06-aula-01.mp4
FILENAME_SIMPLE_RE = re.compile(r"^(nr\d+)-aula-(\d+)\.", re.IGNORECASE)


def parse_key(key):
    m = KEY_RE.match(key)
    if m:
        return {"tenant": m.group(1), "course": m.group(2), "lesson": m.group(3), "filename": m.group(4)}
    m = LEGACY_KEY_RE.match(key)
    if m:
        return {"tenant": None, "course": None, "lesson": m.group(1), "filename": m.group(2)}
    return None


def parse_filename(filename):
    """Extract (nr_code, variant, lesson_number) from filename."""
    base = Path(filename).stem.lower()
    m = FILENAME_RE.match(base)
    if m:
        return {"nr": m.group(1), "variant": m.group(2), "lesson_num": int(m.group(3))}
    m = FILENAME_SIMPLE_RE.match(base)
    if m:
        return {"nr": m.group(1), "variant": None, "lesson_num": int(m.group(2))}
    return None


def build_course_index(courses, lessons_by_course):
    """Build lookup indexes."""
    by_id = {c["id"]: c for c in courses}
    by_code = {c["code"]: c for c in courses}
    # Map lesson_id -> lesson, and (course_id, order) -> lesson
    lesson_by_id = {}
    lesson_by_course_order = {}
    all_lessons = []
    for cid, lessons in lessons_by_course.items():
        for l in lessons:
            lesson_by_id[l["id"]] = l
            lesson_by_course_order[(cid, l["order"])] = l
            all_lessons.append(l)
    return {
        "course_by_id": by_id,
        "course_by_code": by_code,
        "lesson_by_id": lesson_by_id,
        "lesson_by_course_order": lesson_by_course_order,
        "all_lessons": all_lessons,
    }


def map_video_to_lesson(video, index):
    """Map a new video to a lesson using deterministic evidence.

    Returns dict with status and evidence.
    Statuses: EXACT_EXISTING_LESSON, LESSON_NEEDS_CREATION, ALREADY_LINKED,
              DUPLICATE, CONFLICT, AMBIGUOUS, UNMAPPED
    """
    key = video["key"]
    parsed = parse_key(key)
    evidence = []

    if parsed:
        evidence.append(f"storage_key path: tenant={parsed['tenant']} course={parsed['course']} lesson={parsed['lesson']}")

        # Validate tenant
        if parsed["tenant"] != TENANT_ID:
            return {"status": "UNMAPPED", "evidence": evidence + [f"tenant mismatch: {parsed['tenant']}"], "reason": "wrong tenant"}

        # Check if course exists
        course = index["course_by_id"].get(parsed["course"])
        if not course:
            return {"status": "UNMAPPED", "evidence": evidence + [f"course {parsed['course']} not found"], "reason": "course not found"}

        # Check if lesson exists
        lesson = index["lesson_by_id"].get(parsed["lesson"])
        if lesson:
            # Check lesson belongs to course
            if lesson["course_id"] != course["id"]:
                return {"status": "CONFLICT", "evidence": evidence + [f"lesson belongs to different course {lesson['course_id']}"], "reason": "lesson-course mismatch"}
            # Check if already linked
            if lesson.get("storage_key") == key:
                return {"status": "ALREADY_LINKED", "lesson": lesson, "course": course, "evidence": evidence}
            elif lesson.get("storage_key"):
                return {"status": "CONFLICT", "lesson": lesson, "course": course, "evidence": evidence + [f"lesson already has storage_key: {lesson['storage_key']}"], "reason": "lesson already linked to different video"}
            else:
                return {"status": "EXACT_EXISTING_LESSON", "lesson": lesson, "course": course, "evidence": evidence}
        else:
            # Lesson doesn't exist → needs creation
            # Try to determine order from filename
            fn_info = parse_filename(parsed["filename"])
            order = fn_info["lesson_num"] if fn_info else None
            return {"status": "LESSON_NEEDS_CREATION", "course": course, "parsed": parsed, "order": order, "filename": parsed["filename"], "evidence": evidence}

    # Fallback: try metadata
    meta = video.get("metadata", {})
    if meta.get("course_code") and meta.get("lesson_number"):
        evidence.append(f"metadata: course_code={meta['course_code']} lesson_number={meta['lesson_number']}")
        course = index["course_by_code"].get(meta["course_code"])
        if course:
            try:
                order = int(meta["lesson_number"])
            except (ValueError, TypeError):
                return {"status": "UNMAPPED", "evidence": evidence, "reason": "invalid lesson_number metadata"}
            lesson = index["lesson_by_course_order"].get((course["id"], order))
            if lesson:
                if lesson.get("storage_key") == key:
                    return {"status": "ALREADY_LINKED", "lesson": lesson, "course": course, "evidence": evidence}
                elif lesson.get("storage_key"):
                    return {"status": "CONFLICT", "lesson": lesson, "course": course, "evidence": evidence + [f"lesson already has storage_key: {lesson['storage_key']}"], "reason": "lesson already linked"}
                return {"status": "EXACT_EXISTING_LESSON", "lesson": lesson, "course": course, "evidence": evidence}
            else:
                return {"status": "LESSON_NEEDS_CREATION", "course": course, "order": order, "filename": Path(key).name, "evidence": evidence, "parsed": parse_key(key)}

    # Fallback: filename pattern
    fn = Path(key).name
    fn_info = parse_filename(fn)
    if fn_info:
        evidence.append(f"filename pattern: nr={fn_info['nr']} variant={fn_info['variant']} lesson={fn_info['lesson_num']}")
        # Find course by NR code + variant
        nr = fn_info["nr"].upper()
        variant = fn_info["variant"]
        # Try to match course code: NR-06-F, NR-11-PLA, etc.
        candidate_codes = []
        if variant:
            # Try NR-XX-VARIANT (uppercase)
            v_upper = variant.upper()
            candidate_codes.append(f"{nr}-{v_upper}")
            # Try common mappings
        # Also try just NR-XX with all variants
        for code, course in index["course_by_code"].items():
            if code.startswith(f"{nr}-"):
                if variant:
                    # Check if variant matches
                    if v_upper in code.upper():
                        candidate_codes.append(code)
                else:
                    candidate_codes.append(code)

        # Deduplicate
        candidate_codes = list(dict.fromkeys(candidate_codes))
        if len(candidate_codes) == 1:
            course = index["course_by_code"][candidate_codes[0]]
            order = fn_info["lesson_num"]
            lesson = index["lesson_by_course_order"].get((course["id"], order))
            if lesson:
                if lesson.get("storage_key") == key:
                    return {"status": "ALREADY_LINKED", "lesson": lesson, "course": course, "evidence": evidence}
                elif lesson.get("storage_key"):
                    return {"status": "CONFLICT", "lesson": lesson, "course": course, "evidence": evidence + [f"lesson already has storage_key: {lesson['storage_key']}"], "reason": "lesson already linked"}
                return {"status": "EXACT_EXISTING_LESSON", "lesson": lesson, "course": course, "evidence": evidence}
            else:
                return {"status": "LESSON_NEEDS_CREATION", "course": course, "order": order, "filename": fn, "evidence": evidence, "parsed": parse_key(key)}
        elif len(candidate_codes) > 1:
            return {"status": "AMBIGUOUS", "candidate_courses": candidate_codes, "evidence": evidence, "reason": f"multiple courses match: {candidate_codes}"}

    return {"status": "UNMAPPED", "evidence": evidence, "reason": "no deterministic mapping"}


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reconcile-only", action="store_true")
    args = ap.parse_args()
    if not (args.dry_run or args.apply or args.reconcile_only):
        args.dry_run = True  # default safe

    # 1. List bucket
    print("=== Listing bucket (read-only) ===")
    s3, bucket = get_s3()
    current_objects = list_bucket(s3, bucket)
    print(f"  Total objects: {len(current_objects)}")
    video_count = sum(1 for o in current_objects if Path(o["key"]).suffix.lower() in VIDEO_EXTS)
    print(f"  Video objects: {video_count}")

    # Save current inventory
    current_doc = {
        "bucket": bucket,
        "endpoint": os.environ.get("STORAGE_ENDPOINT"),
        "region": os.environ.get("STORAGE_REGION"),
        "total_objects": len(current_objects),
        "video_objects": video_count,
        "objects": current_objects,
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    (ANALYSIS / "remote-video-inventory-current.json").write_text(
        json.dumps(current_doc, indent=2, ensure_ascii=False)
    )
    print(f"  Saved: analysis/storage/remote-video-inventory-current.json")

    # 2. Compute delta
    print("\n=== Computing delta vs baseline ===")
    baseline_map = load_baseline()
    delta = compute_delta(current_objects, baseline_map)
    print(f"  Baseline objects: {delta['baseline_total']}")
    print(f"  Current objects: {delta['current_total']}")
    for cls, cnt in sorted(delta["counts"].items()):
        print(f"  {cls}: {cnt}")
    if delta["missing_baseline_keys"]:
        print(f"  WARNING: {len(delta['missing_baseline_keys'])} baseline keys missing from current bucket!")

    (ANALYSIS / "new-video-delta.json").write_text(
        json.dumps(delta, indent=2, ensure_ascii=False)
    )

    # Write delta markdown
    new_videos = [c for c in delta["classifications"] if c["classification"] == "NEW_VIDEO"]
    changed = [c for c in delta["classifications"] if c["classification"] == "CHANGED_EXISTING"]
    duplicates = [c for c in delta["classifications"] if c["classification"] == "DUPLICATE_CONTENT"]
    new_non_video = [c for c in delta["classifications"] if c["classification"] == "NEW_NON_VIDEO"]

    lines = [
        "# New Video Delta Report",
        "",
        f"Baseline snapshot: `remote-video-inventory-after.json` ({delta['baseline_total']} objects)",
        f"Current bucket: {delta['current_total']} objects",
        "",
        "## Summary",
        "",
        "| Classification | Count |",
        "|---|---|",
    ]
    for cls, cnt in sorted(delta["counts"].items()):
        lines.append(f"| {cls} | {cnt} |")
    lines += [
        "",
        f"## New videos: {len(new_videos)}",
        "",
        "| Key | Size (MB) | ETag | Content-Type | Metadata |",
        "|---|---|---|---|---|",
    ]
    for v in new_videos:
        meta = v.get("metadata", {})
        meta_str = ", ".join(f"{k}={val}" for k, val in meta.items()) if meta else "-"
        lines.append(f"| `{v['key']}` | {v['size']/1e6:.1f} | `{v['etag']}` | {v.get('content_type','-')} | {meta_str} |")
    lines += [
        "",
        f"## Changed existing: {len(changed)}",
        "",
    ]
    for c in changed:
        lines.append(f"- `{c['key']}` (size={c['size']})")
    lines += [
        "",
        f"## Duplicates: {len(duplicates)}",
        "",
    ]
    for d in duplicates:
        lines.append(f"- `{d['key']}` → duplicate of `{d.get('duplicate_of','?')}`")
    lines += [
        "",
        f"## New non-video: {len(new_non_video)}",
        "",
    ]
    for n in new_non_video:
        lines.append(f"- `{n['key']}` ({n['size']} bytes)")
    (ANALYSIS / "new-video-delta.md").write_text("\n".join(lines) + "\n")
    print(f"  Saved: analysis/storage/new-video-delta.json + .md")

    if not new_videos:
        print("\n=== No new videos to reconcile ===")
        return

    # 3. Fetch courses + lessons from API
    print("\n=== Fetching courses + lessons from API ===")
    api = APIClient(
        os.environ.get("API_BASE_URL", "https://wr-api-production.up.railway.app"),
        os.environ["API_ADMIN_EMAIL"],
        os.environ["API_ADMIN_PASSWORD"],
    )
    courses = fetch_courses(api)
    print(f"  Courses: {len(courses)}")
    lessons_by_course = {}
    total_lessons = 0
    for c in courses:
        lessons = fetch_lessons(api, c["id"])
        lessons_by_course[c["id"]] = lessons
        total_lessons += len(lessons)
    print(f"  Total lessons: {total_lessons}")

    # Save current DB map
    db_map = {
        "tenant_id": TENANT_ID,
        "total_lessons": total_lessons,
        "courses": [{"id": c["id"], "code": c["code"], "name": c["name"]} for c in courses],
        "lessons": [],
    }
    for cid, lessons in lessons_by_course.items():
        for l in lessons:
            db_map["lessons"].append({
                "course_id": l["course_id"],
                "course_code": next(c["code"] for c in courses if c["id"] == l["course_id"]),
                "lesson_id": l["id"],
                "order": l["order"],
                "title": l["title"],
                "content_type": l["content_type"],
                "storage_key": l.get("storage_key"),
                "video_url": l.get("video_url"),
                "duration_seconds": l.get("duration_seconds"),
            })
    (ANALYSIS / "db-lesson-mapping-current.json").write_text(
        json.dumps(db_map, indent=2, ensure_ascii=False)
    )
    print(f"  Saved: analysis/storage/db-lesson-mapping-current.json")

    # 4. Map new videos to lessons
    print("\n=== Mapping new videos to lessons ===")
    index = build_course_index(courses, lessons_by_course)
    mappings = []
    for v in new_videos:
        result = map_video_to_lesson(v, index)
        result["video"] = {"key": v["key"], "size": v["size"], "etag": v["etag"],
                           "content_type": v.get("content_type"), "metadata": v.get("metadata", {})}
        mappings.append(result)
        print(f"  {v['key']}: {result['status']}")

    # Summary counts
    status_counts = {}
    for m in mappings:
        status_counts[m["status"]] = status_counts.get(m["status"], 0) + 1
    print("\n  Mapping summary:")
    for s, c in sorted(status_counts.items()):
        print(f"    {s}: {c}")

    # Write mapping matrix
    matrix = {
        "new_video_count": len(new_videos),
        "status_counts": status_counts,
        "mappings": mappings,
    }
    (ANALYSIS / "new-video-lesson-mapping.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False)
    )

    # Markdown matrix
    lines = [
        "# New Video → Lesson Mapping Matrix",
        "",
        f"New videos to reconcile: **{len(new_videos)}**",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|---|---|",
    ]
    for s, c in sorted(status_counts.items()):
        lines.append(f"| {s} | {c} |")
    lines += [
        "",
        "## Details",
        "",
        "| Video | Curso | Course ID | Aula | Lesson ID | Ordem | Status | Evidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in mappings:
        v = m["video"]
        course = m.get("course")
        lesson = m.get("lesson")
        course_code = course["code"] if course else "-"
        course_id = course["id"] if course else "-"
        lesson_title = lesson["title"] if lesson else "-"
        lesson_id = lesson["id"] if lesson else "-"
        order = lesson["order"] if lesson else m.get("order", "-")
        ev = "; ".join(m.get("evidence", []))
        lines.append(f"| `{Path(v['key']).name}` | {course_code} | `{course_id}` | {lesson_title} | `{lesson_id}` | {order} | {m['status']} | {ev} |")
    (ANALYSIS / "new-video-lesson-mapping.md").write_text("\n".join(lines) + "\n")
    print(f"  Saved: analysis/storage/new-video-lesson-mapping.json + .md")

    # 5. Apply phase
    to_create = [m for m in mappings if m["status"] == "LESSON_NEEDS_CREATION"]
    to_link = [m for m in mappings if m["status"] == "EXACT_EXISTING_LESSON"]
    already = [m for m in mappings if m["status"] == "ALREADY_LINKED"]
    conflicts = [m for m in mappings if m["status"] == "CONFLICT"]
    ambiguous = [m for m in mappings if m["status"] == "AMBIGUOUS"]
    unmapped = [m for m in mappings if m["status"] == "UNMAPPED"]

    print(f"\n=== Action plan ===")
    print(f"  Lessons to create: {len(to_create)}")
    print(f"  Lessons to link (update storage_key): {len(to_link)}")
    print(f"  Already correct: {len(already)}")
    print(f"  Conflicts: {len(conflicts)}")
    print(f"  Ambiguous: {len(ambiguous)}")
    print(f"  Unmapped: {len(unmapped)}")

    if args.dry_run or args.reconcile_only:
        print("\n=== Dry-run complete (no DB changes) ===")
        return

    # --apply
    print("\n=== Applying DB changes ===")
    results = {"created": [], "linked": [], "skipped": [], "errors": []}

    # Create lessons
    for m in to_create:
        course = m["course"]
        parsed = m.get("parsed") or {}
        order = m.get("order")
        filename = m.get("filename")
        if not order:
            results["errors"].append({"video": m["video"]["key"], "error": "cannot determine lesson order"})
            continue
        # Determine title
        title = f"Aula {order:02d}"
        # Build storage_key
        if parsed and parsed.get("lesson"):
            # Key already has a lesson UUID → use it
            storage_key = m["video"]["key"]
        else:
            # Need to create lesson first, then the key won't match
            # For now, we can't create a lesson with a specific storage_key that includes
            # the lesson_id before it exists. We'll set storage_key after creation.
            storage_key = m["video"]["key"]  # The key in the bucket

        print(f"  CREATE lesson in {course['code']} order={order} title={title}")
        # Use the lessons API to create
        r = api.post(
            f"/api/v1/lessons/courses/{course['id']}/lessons",
            json={
                "title": title,
                "order": order,
                "content_type": "UPLOAD",
                "storage_key": storage_key,
                "is_required": True,
            },
        )
        if r.status_code == 201:
            lesson = r.json()
            # If the created lesson's storage_key doesn't match the bucket key
            # (because the API may generate a different key), update it
            if lesson.get("storage_key") != storage_key:
                # Need to update storage_key to match the bucket
                # Use upload-complete endpoint to set the correct key
                r2 = api.post(
                    f"/api/v1/lessons/{lesson['id']}/upload-complete",
                    json={"storage_key": storage_key, "filename": filename},
                )
                if r2.status_code == 200:
                    lesson = r2.json()
            results["created"].append({"video": m["video"]["key"], "lesson_id": lesson["id"], "storage_key": lesson.get("storage_key")})
            print(f"    OK: lesson_id={lesson['id']}")
        else:
            results["errors"].append({"video": m["video"]["key"], "error": f"create failed: {r.status_code} {r.text}"})
            print(f"    FAILED: {r.status_code} {r.text[:200]}")
        time.sleep(0.3)

    # Link existing lessons (set storage_key)
    for m in to_link:
        lesson = m["lesson"]
        storage_key = m["video"]["key"]
        filename = Path(storage_key).name
        print(f"  LINK lesson {lesson['id']} → {storage_key}")
        r = api.post(
            f"/api/v1/lessons/{lesson['id']}/upload-complete",
            json={"storage_key": storage_key, "filename": filename},
        )
        if r.status_code == 200:
            results["linked"].append({"video": storage_key, "lesson_id": lesson["id"]})
            print(f"    OK")
        else:
            results["errors"].append({"video": storage_key, "error": f"link failed: {r.status_code} {r.text}"})
            print(f"    FAILED: {r.status_code} {r.text[:200]}")
        time.sleep(0.3)

    for m in already:
        results["skipped"].append({"video": m["video"]["key"], "reason": "already linked"})

    (ANALYSIS / "new-video-apply-result.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )
    print(f"\n=== Apply complete ===")
    print(f"  Created: {len(results['created'])}")
    print(f"  Linked: {len(results['linked'])}")
    print(f"  Skipped: {len(results['skipped'])}")
    print(f"  Errors: {len(results['errors'])}")


if __name__ == "__main__":
    main()
