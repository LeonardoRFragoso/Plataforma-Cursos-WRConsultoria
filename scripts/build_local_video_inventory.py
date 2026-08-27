#!/usr/bin/env python3
"""Build a local MP4 inventory for WR priority course videos.

Reads all *.mp4 under Cursos-WR/output (excluding the preview/ subdir),
runs ffprobe on each, computes SHA-256, and writes:
  - analysis/storage/local-video-inventory.json
  - analysis/storage/local-video-inventory.md

Usage:
    python3 scripts/build_local_video_inventory.py [--output-dir analysis/storage]
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

OUTPUT_DIR = Path("/home/leonardo/dev/Cursos-WR/output")

# filename prefix -> course_code
FILE_TO_CODE = {
    "nr06-aula-": "NR-06-F",
    "nr10-basico-aula-": "NR-10-B",
    "nr10-sep-aula-": "NR-10-S",
    "nr11-empilhadeira-aula-": "NR-11-EMP",
    "nr11-guindauto-aula-": "NR-11-GUI",
    "nr11-minicarregadeira-aula-": "NR-11-MIN",
    "nr11-plataforma-aula-": "NR-11-PLA",
    "nr11-ponte-aula-": "NR-11-PON",
    "nr11-retroescavadeira-aula-": "NR-11-RET",
    "nr12-aula-": "NR-12-F",
    "nr18-aula-": "NR-18-F",
    "nr33-autorizado-aula-": "NR-33-AUT",
    "nr33-supervisor-aula-": "NR-33-SUP",
    "nr35-aula-": "NR-35-F",
}

BASELINE_PREFIX = "nr01-aula-"
LESSON_RE = re.compile(r"aula-(\d+)\.mp4$")


def classify(filename: str) -> tuple[str, int | None, str]:
    """Return (course_code, lesson_number, category)."""
    if filename.startswith(BASELINE_PREFIX):
        m = LESSON_RE.search(filename)
        return ("NR-01", int(m.group(1)) if m else None, "NR01_BASELINE")
    for prefix, code in FILE_TO_CODE.items():
        if filename.startswith(prefix):
            m = LESSON_RE.search(filename)
            return (code, int(m.group(1)) if m else None, "PRIORITY")
    return ("UNKNOWN", None, "UNKNOWN")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def ffprobe(path: Path) -> dict:
    """Run ffprobe and return stream/container metadata."""
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    astream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(fmt.get("duration") or vstream.get("duration") or 0)
    return {
        "duration": round(duration, 3),
        "duration_seconds": int(round(duration)),
        "resolution": f"{vstream.get('width')}x{vstream.get('height')}",
        "width": vstream.get("width"),
        "height": vstream.get("height"),
        "fps": _parse_fps(vstream.get("r_frame_rate")),
        "video_codec": vstream.get("codec_name"),
        "audio_codec": astream.get("codec_name"),
        "has_audio": bool(astream),
        "bit_rate": fmt.get("bit_rate"),
    }


def _parse_fps(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    if "/" in rate:
        num, den = rate.split("/")
        den = int(den) or 1
        return round(int(num) / den, 3)
    return float(rate)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="analysis/storage")
    ap.add_argument("--source", default=str(OUTPUT_DIR))
    args = ap.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in Path(args.source).glob("*.mp4"))
    records = []
    for p in files:
        code, num, category = classify(p.name)
        size = p.stat().st_size
        probe = ffprobe(p)
        sha = compute_sha256(p)
        rec = {
            "course_code": code,
            "lesson_number": num,
            "category": category,
            "filename": p.name,
            "absolute_path": str(p),
            "size_bytes": size,
            "sha256": sha,
            **probe,
        }
        records.append(rec)
        print(f"  {p.name:42s} {code:10s} L{num}  {probe['resolution']} {probe['fps']}fps {probe['video_codec']}/{probe['audio_codec']} {probe['duration_seconds']}s")

    priority = [r for r in records if r["category"] == "PRIORITY"]
    baseline = [r for r in records if r["category"] == "NR01_BASELINE"]
    unknown = [r for r in records if r["category"] == "UNKNOWN"]

    # Validation
    required = {"1920x1080", "h264", "aac"}
    issues = []
    for r in priority + baseline:
        if r["resolution"] != "1920x1080":
            issues.append(f"{r['filename']}: resolution {r['resolution']} != 1920x1080")
        if r["video_codec"] != "h264":
            issues.append(f"{r['filename']}: video codec {r['video_codec']} != h264")
        if r["audio_codec"] != "aac":
            issues.append(f"{r['filename']}: audio codec {r['audio_codec']} != aac")
        if not r["has_audio"]:
            issues.append(f"{r['filename']}: no audio stream")
        if r["duration_seconds"] <= 0:
            issues.append(f"{r['filename']}: duration <= 0")
        if r["fps"] and abs(r["fps"] - 30) > 0.5:
            issues.append(f"{r['filename']}: fps {r['fps']} != 30")

    summary = {
        "source_dir": str(args.source),
        "total_mp4": len(records),
        "priority_videos": len(priority),
        "nr01_baseline": len(baseline),
        "unknown": len(unknown),
        "validation_issues": issues,
    }
    doc = {"summary": summary, "videos": records}
    (out_dir / "local-video-inventory.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False))

    # Markdown
    lines = [
        "# Local Video Inventory",
        "",
        f"Source: `{args.source}`",
        "",
        f"- Total MP4: **{len(records)}**",
        f"- Priority videos: **{len(priority)}**",
        f"- NR-01 baseline: **{len(baseline)}**",
        f"- Unknown: **{len(unknown)}**",
        "",
        "## Validation",
        "",
        f"Required: 1920x1080, 30fps, h264, aac, duration>0, audio stream present.",
        "",
    ]
    if issues:
        lines.append(f"**ISSUES ({len(issues)}):**")
        for i in issues:
            lines.append(f"- {i}")
    else:
        lines.append("**All files pass validation.**")
    lines += ["", "## Files", "", "| Course | Lesson | Filename | Resolution | FPS | Codec | Duration | Size (MB) | SHA-256 (16) |", "|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        lines.append(f"| {r['course_code']} | {r['lesson_number']} | {r['filename']} | {r['resolution']} | {r['fps']} | {r['video_codec']}/{r['audio_codec']} | {r['duration_seconds']}s | {r['size_bytes']/1e6:.1f} | `{r['sha256'][:16]}` |")
    (out_dir / "local-video-inventory.md").write_text("\n".join(lines) + "\n")

    print()
    print(f"PRIORITY={len(priority)} BASELINE={len(baseline)} UNKNOWN={len(unknown)}")
    if issues:
        print(f"VALIDATION ISSUES: {len(issues)}")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    print("All files pass validation.")


if __name__ == "__main__":
    main()
