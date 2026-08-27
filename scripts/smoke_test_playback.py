#!/usr/bin/env python3
"""Smoke test playback for uploaded WR videos.

For a representative sample (1 video per NR family), generates a presigned
GET URL, checks HTTP accessibility, Content-Type, Content-Length, and a
Range request (expecting 206 Partial Content).

Reads STORAGE_* from environment. Never prints full signed URLs (only a
redacted prefix + query-token count).

Usage:
    python scripts/smoke_test_playback.py
    python scripts/smoke_test_playback.py --sample 7
"""
import argparse
import json
import os
import sys
from pathlib import Path

import boto3
import httpx
from botocore.config import Config

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "analysis" / "storage" / "video-storage-map.json"

# one representative per NR family
SAMPLE_CODES = ["NR-06-F", "NR-10-B", "NR-11-EMP", "NR-12-F", "NR-18-F", "NR-33-AUT", "NR-35-F"]


def get_client():
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("STORAGE_ENDPOINT") or None,
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_KEY"],
        region_name=os.environ.get("STORAGE_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )
    return s3, os.environ["STORAGE_BUCKET"]


def redact(url: str) -> str:
    # show scheme+host+path, hide query (contains signature token)
    if "?" in url:
        return url.split("?", 1)[0] + "?<REDACTED_TOKEN>"
    return url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="override sample size")
    args = ap.parse_args()

    s3, bucket = get_client()
    videos = json.loads(MAP_PATH.read_text())["videos"]

    # pick one per sample code (lesson 1)
    sample = []
    for code in SAMPLE_CODES:
        v = next((x for x in videos if x["course_code"] == code and x["lesson_number"] == 1), None)
        if v:
            sample.append(v)
    if args.sample:
        sample = sample[: args.sample]

    results = []
    for v in sample:
        key = v["storage_key"]
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
        )
        rec = {"course_code": v["course_code"], "lesson_number": v["lesson_number"], "key": key}
        # GET with a small Range (presigned GET URLs are method-bound; HEAD is
        # not authorized, so we use GET to inspect headers + content).
        try:
            r = httpx.get(url, headers={"Range": "bytes=0-1023"}, timeout=30, follow_redirects=True)
            rec["get_status"] = r.status_code
            rec["content_type"] = r.headers.get("content-type")
            rec["content_length"] = r.headers.get("content-length")
            rec["content_range"] = r.headers.get("content-range")
            rec["range_status"] = r.status_code
            rec["range_bytes_received"] = len(r.content)
            rec["range_support"] = r.status_code == 206
        except Exception as exc:  # noqa: BLE001
            rec["get_error"] = str(exc)
        rec["url_redacted"] = redact(url)
        results.append(rec)
        print(f"  {v['course_code']} L{v['lesson_number']}: get={rec.get('get_status')} ct={rec.get('content_type')} cr={rec.get('content_range')} range={rec.get('range_status')} ({'206 OK' if rec.get('range_status')==206 else 'no range'})")

    out = {"sample_size": len(results), "results": results}
    (ROOT / "analysis" / "storage" / "smoke-test-results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False))
    range_ok = sum(1 for r in results if r.get("range_status") == 206)
    ct_ok = sum(1 for r in results if r.get("content_type") == "video/mp4")
    print()
    print(f"GET 206 + video/mp4: {sum(1 for r in results if r.get('range_status')==206 and r.get('content_type')=='video/mp4')}/{len(results)}")
    print(f"Content-Type video/mp4: {ct_ok}/{len(results)}")
    print(f"Range 206 supported: {range_ok}/{len(results)}")


if __name__ == "__main__":
    main()
