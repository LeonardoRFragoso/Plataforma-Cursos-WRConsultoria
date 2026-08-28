"""Test manifest hash determinism and change detection.

Verifies that:
1. compute_manifest_hash is deterministic (same bytes → same hash).
2. A change in the manifest bytes changes the hash.
3. The hash is a valid SHA-256 (64 hex chars).
"""

from app.scripts.import_wr_catalog import compute_manifest_hash


def test_manifest_hash_deterministic():
    """Same bytes → same hash."""
    data = b'{"courses": [{"code": "NR-10-B"}]}'
    h1 = compute_manifest_hash(data)
    h2 = compute_manifest_hash(data)
    assert h1 == h2


def test_manifest_hash_changes_on_content_change():
    """Different bytes → different hash."""
    data1 = b'{"courses": [{"code": "NR-10-B"}]}'
    data2 = b'{"courses": [{"code": "NR-10-S"}]}'
    h1 = compute_manifest_hash(data1)
    h2 = compute_manifest_hash(data2)
    assert h1 != h2


def test_manifest_hash_is_sha256():
    """Hash must be a valid SHA-256 (64 hex chars)."""
    data = b'{"test": true}'
    h = compute_manifest_hash(data)
    assert len(h) == 64
    int(h, 16)  # raises if not hex


def test_manifest_hash_empty_input():
    """Empty bytes → valid SHA-256 of empty string."""
    h = compute_manifest_hash(b"")
    assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
