#!/usr/bin/env python3
"""List all objects in the WR storage bucket and write a remote inventory.

Reads STORAGE_* from environment (loaded from Railway --kv, never printed).
Outputs analysis/storage/remote-video-inventory.json.

Optionally filter by a prefix (default: "tenants/").
"""
import argparse
import json
import os
from pathlib import Path

import boto3
from botocore.config import Config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="analysis/storage/remote-video-inventory.json")
    ap.add_argument("--prefix", default="tenants/")
    ap.add_argument("--bucket", default=os.environ.get("STORAGE_BUCKET", ""))
    args = ap.parse_args()

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("STORAGE_ENDPOINT") or None,
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_KEY"],
        region_name=os.environ.get("STORAGE_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )

    objects = []
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=args.bucket, Prefix=args.prefix)
    for page in pages:
        for obj in page.get("Contents", []):
            objects.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "etag": obj.get("ETag", "").strip('"'),
                "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
            })

    # Enrich with content-type via head_object for video keys only (to limit calls)
    video_objs = [o for o in objects if o["key"].lower().endswith(".mp4")]
    for o in video_objs:
        try:
            head = s3.head_object(Bucket=args.bucket, Key=o["key"])
            o["content_type"] = head.get("ContentType")
            o["metadata"] = dict(head.get("Metadata", {}))
            o["content_length"] = head.get("ContentLength")
        except Exception as exc:  # noqa: BLE001
            o["head_error"] = str(exc)

    doc = {
        "bucket": args.bucket,
        "endpoint": os.environ.get("STORAGE_ENDPOINT"),
        "region": os.environ.get("STORAGE_REGION"),
        "prefix": args.prefix,
        "total_objects": len(objects),
        "video_objects": len(video_objs),
        "objects": objects,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"Bucket: {args.bucket}")
    print(f"Total objects under '{args.prefix}': {len(objects)}")
    print(f"Video (.mp4) objects: {len(video_objs)}")
    # quick summary of which are under video/ paths
    video_path = [o for o in objects if "/video/" in o["key"]]
    print(f"Objects under '.../video/': {len(video_path)}")


if __name__ == "__main__":
    main()
