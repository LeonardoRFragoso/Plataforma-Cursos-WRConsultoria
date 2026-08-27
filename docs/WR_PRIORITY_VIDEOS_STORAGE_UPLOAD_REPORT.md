# WR Priority Course Videos — Storage Upload Report

**Date:** 2026-08-27
**Task:** Reconcile and upload all missing WR priority course videos to the
production storage bucket. No videos were regenerated; no existing objects were
overwritten or deleted; no student progress, enrollments, or certificates were
modified.

> **Operator decision:** Production had lessons+storage_keys for only 4 of 14
> courses (17/85 videos). The other 10 courses (68 videos) had **no lessons** in
> the DB, so their storage_keys could not be resolved. The operator authorized
> creating the missing Lesson rows (lessons only — no courses, enrollments,
> progress, or certificates touched) so all 85 could be uploaded. See
> "Lesson creation" below.

---

## 1. Storage

| Field        | Value                                      |
|--------------|--------------------------------------------|
| Provider     | Tebi.io (S3-compatible object storage)     |
| Backend      | `s3` (`STORAGE_BACKEND=s3`)                |
| Endpoint     | `https://t3.storageapi.dev`                |
| Bucket       | `wr-course-assets-rr3in3p0`                |
| Region       | `iad` (US East)                            |
| Signature    | `s3v4`                                     |
| Credentials  | CONFIGURED (read from Railway env; never written to disk or committed) |

Source of truth: `api/app/core/storage.py` (`_tenant_key_for_video`).

## 2. Storage key convention

Tenant-aware, as implemented by the platform:

```
tenants/{tenant_id}/courses/{course_id}/lessons/{lesson_id}/video/{filename}
```

- `tenant_id` = `11111111-1111-1111-1111-111111111111` (WR tenant)
- `course_id` / `lesson_id` = real UUIDs resolved from the production DB
- `filename` = the original local MP4 filename, preserved verbatim

All 85 priority videos use this format. The legacy `lessons/{id}/{filename}`
format exists in code for backward compatibility but is not used by any current
record.

## 3. Local inventory

| Category       | Count |
|----------------|-------|
| Priority videos | 85    |
| NR-01 baseline  | 1     |
| Unknown         | 0     |

All 85 priority + 1 baseline pass validation: **1920x1080, 30fps, h264, aac,
duration > 0, audio stream present**. NR-01 baseline SHA-256 matches the
expected value
`e454e56637d14bf1f363fd7a075d7645cfafd394bb0bd7e280a9684b0f7a09da`.

Artifacts: `analysis/storage/local-video-inventory.{json,md}`

## 4. Lesson creation (DB write — lessons only)

Production DB (queried read-only via `railway ssh`) had lessons for only 4
courses. 68 lessons were created for the 10 missing courses, idempotently
(matched by `(course_id, order)`; re-running creates nothing new):

| Course     | Lessons created |
|------------|-----------------|
| NR-10-B    | 6 |
| NR-10-S    | 6 |
| NR-11-EMP  | 7 |
| NR-11-GUI  | 7 |
| NR-11-MIN  | 6 |
| NR-11-PLA  | 7 |
| NR-11-PON  | 10 |
| NR-11-RET  | 7 |
| NR-18-F    | 7 |
| NR-33-SUP  | 5 |
| **Total**  | **68** |

Each new lesson: `content_type=UPLOAD`, `is_free_preview=False`,
`is_required=True`, `duration_seconds` from ffprobe, `title` from the content
manifest (`Cursos-WR/content/*/course.json`), and a tenant-aware `storage_key`
using its DB-generated UUID. **No courses, enrollments, progress, certificates,
users, or tenants were modified.**

## 5. Initial remote inventory

| Metric                          | Value |
|---------------------------------|-------|
| Total objects under `tenants/`  | 64    |
| Video (`.mp4`) objects          | 17    |

Artifact: `analysis/storage/remote-video-inventory.json`

## 6. Reconciliation before upload

| Status                       | Count |
|------------------------------|-------|
| ALREADY_PRESENT_IDENTICAL    | 17    |
| MISSING                      | 68    |
| CONFLICT_DIFFERENT_CONTENT   | 0     |
| BLOCKED_MAPPING              | 0     |
| **Total**                    | **85** |

Math check: 17 + 68 + 0 + 0 = 85. No conflicts, no blocked → proceeded
automatically to upload per task rules.

Artifact: `analysis/storage/reconciliation.json`, `analysis/storage/video-upload-plan.md`

## 7. Upload

| Metric              | Value                         |
|---------------------|-------------------------------|
| Uploaded            | 68                            |
| Skipped (present)   | 17                            |
| Skipped (conflict)  | 0                             |
| Failed              | 0                             |
| Bytes uploaded      | 3,708,511,214 (3.71 GB)       |

- Only `status=MISSING` objects were uploaded.
- `Content-Type: video/mp4` set on every object.
- Non-sensitive metadata attached: `course_code`, `lesson_number`, `sha256`.
- No MP4 was recompressed, transcodified, renamed, or re-containered — bytes
  preserved exactly.
- Retry policy: up to 4 attempts with backoff (5/10/20/40s) for transient
  errors; permanent errors recorded as `UPLOAD_FAILED`. **All 68 succeeded on
  the first attempt.**
- Each upload validated via `head_object`: `content-length == local size` and
  `content-type == video/mp4`. All 68 validated.

Artifact: `analysis/storage/upload-result.json`

## 8. Reconciliation after upload

| Status                       | Count |
|------------------------------|-------|
| ALREADY_PRESENT_IDENTICAL    | 85    |
| MISSING                      | 0     |
| CONFLICT_DIFFERENT_CONTENT   | 0     |
| BLOCKED_MAPPING              | 0     |
| UPLOAD_FAILED                | 0     |

Bucket: 132 total objects, 85 video objects.

Artifact: `analysis/storage/remote-video-inventory-after.json`

## 9. Second dry-run (idempotency gate)

```
total: 85
ALREADY_PRESENT_IDENTICAL: 85
MISSING: 0
CONFLICT_DIFFERENT_CONTENT: 0
BLOCKED_MAPPING: 0
TO_UPLOAD: 0
```

**TO_UPLOAD = 0** — acceptance criterion met. Re-running the uploader creates no
duplicates.

## 10. Smoke tests (playback)

Sample: 1 video per NR family (NR-06, NR-10, NR-11, NR-12, NR-18, NR-33, NR-35),
lesson 1 of each.

| Check                          | Result |
|--------------------------------|--------|
| Presigned GET URL generated    | 7/7    |
| GET accessible (HTTP 206)      | 7/7    |
| Content-Type `video/mp4`       | 7/7    |
| Content-Range confirms size    | 7/7    |
| Range request `bytes=0-1023` → 206 Partial Content | 7/7 |

Note: presigned URLs are method-bound (GET), so `HEAD` against a presigned GET
URL returns 403 — this is expected S3 behavior; the GET (with Range) is the
correct playback path. Signed URLs are redacted in the artifact
(`?<REDACTED_TOKEN>`).

Artifact: `analysis/storage/smoke-test-results.json`

## 11. NR-01 baseline (audited separately)

| Field                  | Value |
|------------------------|-------|
| Local file             | `output/nr01-aula-01.mp4` |
| Local SHA-256          | matches expected `e454e566...f7a09da` |
| Present in bucket      | No (no object with `nr01` in the bucket) |
| Storage mapping        | None — no lesson references the NR-01 baseline |
| Action                 | NOT uploaded (no safe storage mapping) |

The baseline is **not** part of the 85 priority videos. It was not uploaded
because there is no lesson/storage_key that references it; uploading it would
create an orphan object with no platform reference. Status:
`NOT_PRESENT_NO_MAPPING`.

## 12. Final per-course status

| Course     | Expected | Present in bucket | Uploads | Status            |
|------------|----------|-------------------|---------|-------------------|
| NR-06-F    | 5        | 5                 | 0       | STORAGE COMPLETE  |
| NR-10-B    | 6        | 6                 | 6       | STORAGE COMPLETE  |
| NR-10-S    | 6        | 6                 | 6       | STORAGE COMPLETE  |
| NR-11-EMP  | 7        | 7                 | 7       | STORAGE COMPLETE  |
| NR-11-GUI  | 7        | 7                 | 7       | STORAGE COMPLETE  |
| NR-11-MIN  | 6        | 6                 | 6       | STORAGE COMPLETE  |
| NR-11-PLA  | 7        | 7                 | 7       | STORAGE COMPLETE  |
| NR-11-PON  | 10       | 10                | 10      | STORAGE COMPLETE  |
| NR-11-RET  | 7        | 7                 | 7       | STORAGE COMPLETE  |
| NR-12-F    | 4        | 4                 | 0       | STORAGE COMPLETE  |
| NR-18-F    | 7        | 7                 | 7       | STORAGE COMPLETE  |
| NR-33-AUT  | 4        | 4                 | 0       | STORAGE COMPLETE  |
| NR-33-SUP  | 5        | 5                 | 5       | STORAGE COMPLETE  |
| NR-35-F    | 4        | 4                 | 0       | STORAGE COMPLETE  |
| **Total**  | **85**   | **85**            | **68**  | **85/85**         |

## 13. Scripts created

| Script | Purpose |
|--------|---------|
| `scripts/build_local_video_inventory.py` | ffprobe + SHA-256 inventory of local MP4s |
| `scripts/list_bucket_inventory.py` | List bucket objects (remote inventory) |
| `scripts/upload_course_videos.py` | Idempotent uploader + reconciler (`--dry-run` / `--apply` / `--reconcile-only`) |
| `scripts/smoke_test_playback.py` | Presigned-URL + Range-request smoke tests |

## 14. Acceptance criteria

- [x] 85 priority videos local
- [x] 85 priority videos present & identical in bucket
- [x] MISSING = 0
- [x] CONFLICT = 0
- [x] BLOCKED = 0
- [x] UPLOAD_FAILED = 0
- [x] Second dry-run TO_UPLOAD = 0
- [x] No videos regenerated, no objects overwritten/deleted, no student data
      modified, no courses altered

## 15. Orphan review

No remote-only video orphans were found among the 85 target keys. Other
non-video objects in the bucket (materials, etc.) were not touched and are out
of scope for this task.
