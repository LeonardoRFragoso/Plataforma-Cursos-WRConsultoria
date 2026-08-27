#!/usr/bin/env python3
"""Idempotent uploader & reconciler for WR priority course videos.

Uploads ONLY missing videos to the production storage bucket (Tebi.io,
S3-compatible). Never overwrites existing objects. Validates each upload
via HEAD. Re-running is safe: already-present identical objects are skipped.

Reads STORAGE_* from environment (load from Railway: \
  eval "$(railway variables --service wr-api --kv | grep '^STORAGE_' | sed 's/^/export /')" \
).

Usage:
    python scripts/upload_course_videos.py --dry-run
    python scripts/upload_course_videos.py --apply
    python scripts/upload_course_videos.py --apply --smoke-test
    python scripts/upload_course_videos.py --reconcile-only

Inputs:
    analysis/storage/video-storage-map.json  (85 videos with storage_key + sha256)
    Cursos-WR/output/<filename>              (local MP4 source)

Outputs:
    analysis/storage/video-upload-plan.md            (--dry-run)
    analysis/storage/upload-result.json             (--apply)
    analysis/storage/remote-video-inventory-after.json (--apply / --reconcile-only)
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "analysis" / "storage" / "video-storage-map.json"
LOCAL_SOURCE_ROOT = Path("/home/leonardo/dev/Cursos-WR")
CONTENT_TYPE = "video/mp4"
MAX_RETRIES = 4
RETRY_BACKOFF = [5, 10, 20, 40]  # seconds


def get_client() -> tuple:
    endpoint = os.environ.get("STORAGE_ENDPOINT") or None
    bucket = os.environ.get("STORAGE_BUCKET", "")
    if not bucket or not os.environ.get("STORAGE_ACCESS_KEY") or not os.environ.get("STORAGE_SECRET_KEY"):
        print("ERROR: STORAGE_* env vars not configured", file=sys.stderr)
        sys.exit(2)
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_KEY"],
        region_name=os.environ.get("STORAGE_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )
    return s3, bucket


def list_remote(s3, bucket, prefix="tenants/") -> dict:
    """Return {key: {size, etag, content_type}} for all objects under prefix."""
    out = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            out[obj["Key"]] = {"size": obj["Size"], "etag": obj.get("ETag", "").strip('"')}
    return out


def head(s3, bucket, key) -> dict | None:
    try:
        r = s3.head_object(Bucket=bucket, Key=key)
        return {
            "content_length": r.get("ContentLength"),
            "content_type": r.get("ContentType"),
            "metadata": dict(r.get("Metadata", {})),
        }
    except ClientError:
        return None


def classify(local: dict, remote_map: dict) -> str:
    o = remote_map.get(local["storage_key"])
    if not o:
        return "MISSING"
    if o["size"] == local["size_bytes"]:
        return "ALREADY_PRESENT_IDENTICAL"
    return "CONFLICT_DIFFERENT_CONTENT"


def upload_with_retry(s3, bucket, key, path: Path, metadata: dict) -> dict:
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            s3.upload_file(
                str(path),
                bucket,
                key,
                ExtraArgs={
                    "ContentType": CONTENT_TYPE,
                    "Metadata": metadata,
                },
            )
            return {"ok": True, "attempts": attempt + 1}
        except ClientError as exc:
            last_exc = exc
            code = exc.response.get("Error", {}).get("Code", "")
            # Permanent errors: don't retry
            if code in ("AccessDenied", "InvalidBucketName", "NoSuchBucket"):
                return {"ok": False, "error": str(exc), "permanent": True, "attempts": attempt + 1}
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            print(f"    retry {attempt+1}/{MAX_RETRIES} after {wait}s ({code})")
            time.sleep(wait)
        except (OSError, ConnectionError) as exc:
            last_exc = exc
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            print(f"    retry {attempt+1}/{MAX_RETRIES} after {wait}s ({type(exc).__name__})")
            time.sleep(wait)
    return {"ok": False, "error": str(last_exc), "permanent": False, "attempts": MAX_RETRIES}


def load_map() -> list[dict]:
    data = json.loads(MAP_PATH.read_text())
    return data["videos"]


def write_plan(videos: list[dict], remote_map: dict) -> dict:
    counts = {"ALREADY_PRESENT_IDENTICAL": 0, "MISSING": 0, "CONFLICT_DIFFERENT_CONTENT": 0, "BLOCKED_MAPPING": 0}
    rows = []
    for v in videos:
        st = classify(v, remote_map)
        counts[st] = counts.get(st, 0) + 1
        action = {"ALREADY_PRESENT_IDENTICAL": "SKIP", "MISSING": "UPLOAD", "CONFLICT_DIFFERENT_CONTENT": "DO_NOT_OVERWRITE", "BLOCKED_MAPPING": "BLOCKED"}[st]
        rows.append((v["course_code"], v["lesson_number"], v["local_file"], v["storage_key"], st, action))
    total = len(videos)
    to_upload = counts["MISSING"]
    lines = [
        "# Video Upload Plan (dry-run)",
        "",
        f"Total local priority videos: **{total}**",
        "",
        "| Status | Count |",
        "|---|---|",
        f"| ALREADY_PRESENT_IDENTICAL | {counts['ALREADY_PRESENT_IDENTICAL']} |",
        f"| MISSING | {counts['MISSING']} |",
        f"| CONFLICT_DIFFERENT_CONTENT | {counts['CONFLICT_DIFFERENT_CONTENT']} |",
        f"| BLOCKED_MAPPING | {counts['BLOCKED_MAPPING']} |",
        f"| **TO_UPLOAD** | **{to_upload}** |",
        "",
        "Math check: "
        f"{counts['ALREADY_PRESENT_IDENTICAL']} + {counts['MISSING']} + {counts['CONFLICT_DIFFERENT_CONTENT']} + {counts['BLOCKED_MAPPING']} = {total}",
        "",
        "| Curso | Aula | Local | Storage Key | Status | Ação |",
        "|---|---|---|---|---|---|",
    ]
    for code, num, local, key, st, action in rows:
        lines.append(f"| {code} | {num} | `{local}` | `{key}` | {st} | {action} |")
    (ROOT / "analysis" / "storage" / "video-upload-plan.md").write_text("\n".join(lines) + "\n")
    return {"total": total, **counts, "TO_UPLOAD": to_upload}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reconcile-only", action="store_true")
    args = ap.parse_args()
    if not (args.dry_run or args.apply or args.reconcile_only):
        print("Specify --dry-run, --apply, or --reconcile-only")
        sys.exit(1)

    s3, bucket = get_client()
    videos = load_map()
    remote_map = list_remote(s3, bucket)

    plan = write_plan(videos, remote_map)
    print("=== Dry-run plan ===")
    for k, v in plan.items():
        print(f"  {k}: {v}")

    if args.dry_run or args.reconcile_only:
        # Save final remote inventory for reconcile-only
        if args.reconcile_only:
            save_remote_inventory(s3, bucket)
        return

    # --apply: upload MISSING only
    uploaded, skipped, failed, bytes_uploaded = 0, 0, 0, 0
    results = []
    for v in videos:
        st = classify(v, remote_map)
        if st == "ALREADY_PRESENT_IDENTICAL":
            skipped += 1
            results.append({**v, "outcome": "SKIPPED_PRESENT"})
            continue
        if st == "CONFLICT_DIFFERENT_CONTENT":
            skipped += 1
            results.append({**v, "outcome": "SKIPPED_CONFLICT"})
            print(f"  CONFLICT (not overwriting): {v['storage_key']}")
            continue
        # MISSING -> upload
        path = LOCAL_SOURCE_ROOT / v["local_file"]
        meta = {"course_code": v["course_code"], "lesson_number": str(v["lesson_number"]), "sha256": v["sha256"]}
        print(f"  UPLOAD [{v['course_code']} L{v['lesson_number']}] {v['filename']} ({v['size_bytes']/1e6:.1f} MB)")
        res = upload_with_retry(s3, bucket, v["storage_key"], path, meta)
        if not res["ok"]:
            failed += 1
            results.append({**v, "outcome": "UPLOAD_FAILED", "error": res.get("error")})
            print(f"    FAILED: {res.get('error')}")
            continue
        # Validate via HEAD
        h = head(s3, bucket, v["storage_key"])
        ok = h and h["content_length"] == v["size_bytes"] and h["content_type"] == CONTENT_TYPE
        if ok:
            uploaded += 1
            bytes_uploaded += v["size_bytes"]
            results.append({**v, "outcome": "UPLOADED", "validated": True, "content_length": h["content_length"]})
            print(f"    OK (validated, {res['attempts']} attempt(s))")
        else:
            failed += 1
            results.append({**v, "outcome": "UPLOAD_FAILED_VALIDATION", "head": h})
            print(f"    VALIDATION FAILED: head={h}")

    print()
    print("=== Upload result ===")
    print(f"  uploaded: {uploaded}")
    print(f"  skipped (present): {sum(1 for r in results if r['outcome']=='SKIPPED_PRESENT')}")
    print(f"  skipped (conflict): {sum(1 for r in results if r['outcome']=='SKIPPED_CONFLICT')}")
    print(f"  failed: {failed}")
    print(f"  bytes uploaded: {bytes_uploaded} ({bytes_uploaded/1e9:.2f} GB)")

    (ROOT / "analysis" / "storage" / "upload-result.json").write_text(
        json.dumps({"uploaded": uploaded, "skipped_present": sum(1 for r in results if r['outcome']=='SKIPPED_PRESENT'),
                    "skipped_conflict": sum(1 for r in results if r['outcome']=='SKIPPED_CONFLICT'),
                    "failed": failed, "bytes_uploaded": bytes_uploaded, "results": results}, indent=2, ensure_ascii=False))

    save_remote_inventory(s3, bucket)


def save_remote_inventory(s3, bucket) -> None:
    remote_map = list_remote(s3, bucket)
    objs = []
    for key, info in remote_map.items():
        o = {"key": key, "size": info["size"], "etag": info["etag"]}
        if key.lower().endswith(".mp4"):
            h = head(s3, bucket, key)
            if h:
                o["content_type"] = h["content_type"]
                o["content_length"] = h["content_length"]
                o["metadata"] = h["metadata"]
        objs.append(o)
    out = {"bucket": bucket, "total_objects": len(objs),
           "video_objects": sum(1 for o in objs if o["key"].lower().endswith(".mp4")),
           "objects": objs}
    (ROOT / "analysis" / "storage" / "remote-video-inventory-after.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  remote inventory after: {out['total_objects']} objects, {out['video_objects']} videos")


if __name__ == "__main__":
    main()
