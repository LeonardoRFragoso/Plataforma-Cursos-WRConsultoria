# New Video Location Audit — WR Course Videos

**Audit date**: 2026-08-27 21:00 UTC
**Audit type**: Read-only investigation (no changes made to bucket, DB, or application)
**Conclusion**: **NEW VIDEOS NOT FOUND IN ANY LOCATION**

---

## Executive Summary

A comprehensive read-only investigation was conducted to locate newly available WR
course videos across all accessible storage, local workspaces, Railway configurations,
and git history. **No new videos were found in any location.**

The production bucket, local workspace, and database are all in perfect sync with the
baseline established by commit `9c7fb63` (the previous reconciliation task). All 85
priority videos are present in the bucket, linked to lessons, and have exact SHA-256
matches with the local source files. No alternate buckets, alternate prefixes, or
untracked local videos exist.

---

## Production Bucket

| Metric | Value |
|---|---|
| Bucket | `wr-course-assets-rr3in3p0` |
| Endpoint | `https://t3.storageapi.dev` |
| Region | `iad` |
| Total objects | 132 |
| Video objects (MP4) | 85 |
| PDF objects | 47 |
| Baseline objects | 132 |
| Identical to baseline | **132** (100%) |
| New videos | **0** |
| Changed existing | **0** |
| Duplicates | **0** |
| Missing baseline keys | **0** |

### Prefix audit

All 132 objects are under the `tenants/` prefix. No objects exist under any other
prefix (`uploads/`, `videos/`, `courses/`, `lessons/`, `media/`, `tmp/`, `temp/`,
`incoming/`, `new/`, `wr/`, `curso/`, `cursos/`).

### Most recent uploads (LastModified)

All 132 objects have `LastModified` timestamps from 2026-08-27 (the day of the
previous reconciliation task). The 68 most recent objects (uploaded after 20:00 UTC)
are exactly the 68 videos that were uploaded during the previous reconciliation.

| Timestamp (UTC) | Size | Filename |
|---|---|---|
| 2026-08-27T20:28:16 | 59.9 MB | nr33-supervisor-aula-05.mp4 |
| 2026-08-27T20:27:57 | 52.1 MB | nr33-supervisor-aula-04.mp4 |
| 2026-08-27T20:27:41 | 60.7 MB | nr33-supervisor-aula-03.mp4 |
| 2026-08-27T20:27:18 | 61.2 MB | nr33-supervisor-aula-02.mp4 |
| 2026-08-27T20:26:58 | 54.3 MB | nr33-supervisor-aula-01.mp4 |
| 2026-08-27T20:26:41 | 68.5 MB | nr18-aula-07.mp4 |
| 2026-08-27T20:26:18 | 54.7 MB | nr18-aula-06.mp4 |
| 2026-08-27T20:25:58 | 54.4 MB | nr18-aula-05.mp4 |
| 2026-08-27T20:25:40 | 55.8 MB | nr18-aula-04.mp4 |
| 2026-08-27T20:25:23 | 50.6 MB | nr18-aula-03.mp4 |

**No objects have been uploaded after the baseline reconciliation.**

---

## Other Buckets

| Bucket | Objects | Videos | New |
|---|---:|---:|---:|
| wr-course-assets-rr3in3p0 | 132 | 85 | 0 |

`ListBuckets` API call returns `AccessDenied` (Tebi.io restricts per-key). The
following 15 candidate bucket names were tested directly via `ListObjectsV2`:

| Candidate | Result |
|---|---|
| wr-videos | NoSuchBucket |
| wr-materials | NoSuchBucket |
| wr-assets | NoSuchBucket |
| wr-media | NoSuchBucket |
| wr-upload | NoSuchBucket |
| wr-staging | NoSuchBucket |
| wr-course-assets | NoSuchBucket |
| wr-course-videos | NoSuchBucket |
| wr-cursos | NoSuchBucket |
| course-assets | NoSuchBucket |
| wr-course-assets-staging | NoSuchBucket |
| wr-course-assets-upload | NoSuchBucket |
| wr-course-assets-new | NoSuchBucket |
| wr-course-assets-dev | NoSuchBucket |
| wr-course-assets-test | NoSuchBucket |

**No alternate buckets exist or are accessible.**

---

## Workspace

| Situation | Quantity |
|---|---:|
| Local video files (total) | 87 |
| Priority videos (baseline) | 85 |
| NR-01 baseline | 1 |
| Preview derivatives | 1 |
| Already in bucket (baseline) | 85 |
| NR-01 baseline (not in bucket) | 1 |
| **New only locally** | **0** |
| Duplicates | 0 |

### SHA-256 verification

All 86 local video files (85 priority + 1 NR-01 baseline) were SHA-256 verified
against the baseline inventory (`local-video-inventory.json`):

- **Checked**: 86
- **Exact match**: 86 (100%)
- **Mismatches**: 0
- **New files**: 0

No local video has been silently replaced with a new version.

### Preview file

| File | Path | Size | Note |
|---|---|---|---|
| nr01-aula-01-preview.mp4 | output/preview/ | 23.4 MB | Derivative preview of NR-01 baseline, not a new course video |

### Cursos-WR repository

- **Repo**: `LeonardoRFragosto/WR-Course-Video-Generator`
- **HEAD**: `f62ecf1` — "feat: complete all 14 priority courses with full audiovisual production"
- **Date**: 2026-08-27 16:02 BRT
- **Status**: Clean, up to date with origin/main
- **MP4s in .gitignore**: Yes (not tracked in git)
- **Stash**: Empty
- **Worktrees**: Only main worktree

---

## Cross-comparison: Local vs Bucket vs Baseline

| Classification | Count |
|---|---:|
| LOCAL_AND_BUCKET_BASELINE | 85 |
| LOCAL_NR01_BASELINE_NOT_IN_BUCKET | 1 |
| LOCAL_NEW_NOT_UPLOADED | 0 |
| NEW_ALREADY_IN_OTHER_BUCKET | 0 |
| DUPLICATE_CONTENT | 0 |
| UNKNOWN | 0 |
| PREVIEW_DERIVATIVE | 1 |

---

## Railway Configuration

| Setting | Value |
|---|---|
| Project | wr-white-label-ceo-demo |
| Environment | production |
| STORAGE_BACKEND | s3 |
| STORAGE_BUCKET | wr-course-assets-rr3in3p0 |
| STORAGE_ENDPOINT | https://t3.storageapi.dev |
| STORAGE_REGION | iad |

- **Services checked**: wr-api, Postgres, Redis
- **Alternate storage configs**: 0
- **Second bucket config**: No
- **Staging bucket config**: No
- **Other Railway projects**: `independent-respect` (no storage config found)
- **Code default bucket**: `wr-videos` (in `api/app/core/config.py`, overridden by env var in production)

---

## Git History Search

Searched `LeonardoRFragosto/Plataforma-Cursos-WRConsultoria` for references to
alternate bucket names:

- `storageapi`, `bucket`, `S3_BUCKET`, `STORAGE_BUCKET`, `course-assets`, `video`, `upload`
- **Alternate production bucket references found**: 0
- **Test-only bucket names**: `wr-videos`, `wr-materials`, `bucket` (unit test mocks only)

---

## Content Manifests

| Metric | Value |
|---|---|
| Courses in manifests | 14 |
| Total planned lessons | 85 |
| Courses with videos | 14 |
| Lessons without videos | 0 |
| Planned courses without videos | 0 |

All 14 course manifests match exactly the 85 videos in the bucket and the 85 lessons
in the database. No additional courses or lessons are planned in the content manifests.

---

## Database State (via production API)

| Metric | Value |
|---|---|
| Total courses | 50 |
| Total lessons | 85 |
| Lessons with storage_key | 85 |
| Lessons without storage_key | 0 |
| content_type=UPLOAD | 85 |
| Bucket videos linked to lesson | 85/85 |
| Orphan bucket videos | 0 |
| DB storage_keys missing from bucket | 0 |

---

## Other Directories Searched

| Directory | WR Course Videos Found |
|---|---|
| /home/leonardo/dev/WR-Plataforma-Cursos-cert-demo | 0 |
| /home/leonardo/dev/WR-Plataforma-Cursos-cert-merge | 0 |
| /tmp/wr-compliance-worktree | 0 |
| /home/leonardo/dev/Fundativa | 0 (6 generic unrelated videos) |
| /home/leonardo/dev/Focon-Engenharia | 0 |
| /home/leonardo/dev/Leo | 0 |
| /home/leonardo/Downloads | 0 |
| /home/leonardo/Desktop | 0 |
| /home/leonardo/Documents | 0 |
| /tmp | 0 (1 temp Remotion render file, not a course video) |

---

## New Videos Found

**None.** No new videos were found in any location.

---

## Unmapped Videos

**None.**

---

## Conflicts

**None.**

---

## Conclusion

**NEW VIDEOS NOT FOUND IN ANY LOCATION.**

The investigation comprehensively checked:

1. **Production bucket** (`wr-course-assets-rr3in3p0`) — 132 objects, all identical to baseline, 0 new
2. **Alternate buckets** — 15 candidate names tested, all NoSuchBucket; ListBuckets AccessDenied
3. **All prefixes** in the production bucket — all 132 objects under `tenants/`, nothing elsewhere
4. **Local workspace** (`/home/leonardo/dev/Cursos-WR/output`) — 86 videos, all SHA-256 match baseline, 0 new
5. **Other directories** — 10 directories searched, 0 WR course videos found
6. **Railway config** — single bucket configured, no alternate storage settings
7. **Git history** — no references to alternate production buckets
8. **Content manifests** — 14 courses / 85 lessons, exactly matching bucket and DB
9. **Database** — 85/85 lessons linked, 0 orphans, 0 conflicts
10. **Bucket timestamps** — all objects from 2026-08-27 (baseline day), nothing newer

The new videos have **not yet been uploaded** to any accessible bucket, and no new
video files exist locally beyond the 85 priority + 1 NR-01 baseline that were already
reconciled in the previous task.

If new videos are expected, they may need to be:
- Produced (the Cursos-WR video generation pipeline is at 85/85 lessons complete)
- Uploaded to the production bucket after production
- Or provided via a different mechanism not yet configured
