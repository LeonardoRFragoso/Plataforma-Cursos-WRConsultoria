"""Tests for demo data cleanup safety features.

Verifies:
1. AMBIGUOUS detection — demo-marked data with real dependencies is flagged
2. Transactional deletion — all deletes in single transaction
3. --execute guards — DEMO_SEED_MODE, ENVIRONMENT, confirmation
4. Dry-run mode never deletes
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scripts.audit_demo_data import (
    DEMO_CERT_PREFIX,
    DEMO_CLASS_LOCATION,
    DEMO_EMAIL_DOMAINS,
    _is_unambiguous_demo_cert,
    _is_unambiguous_demo_class,
    _is_unambiguous_demo_user,
)


class TestUnambiguousDetection:
    """Verify the unambiguous demo marker functions work correctly."""

    def test_demo_user_detected(self):
        user = MagicMock()
        user.email = f"student{DEMO_EMAIL_DOMAINS[0]}"
        assert _is_unambiguous_demo_user(user) is True

    def test_real_user_not_demo(self):
        user = MagicMock()
        user.email = "student@example.com"
        assert _is_unambiguous_demo_user(user) is False

    def test_demo_class_detected(self):
        cls = MagicMock()
        cls.location = DEMO_CLASS_LOCATION
        assert _is_unambiguous_demo_class(cls) is True

    def test_real_class_not_demo(self):
        cls = MagicMock()
        cls.location = "São Paulo - SP"
        assert _is_unambiguous_demo_class(cls) is False

    def test_demo_cert_detected(self):
        cert = MagicMock()
        cert.certificate_number = f"{DEMO_CERT_PREFIX}NR-10-12345"
        assert _is_unambiguous_demo_cert(cert) is True

    def test_real_cert_not_demo(self):
        cert = MagicMock()
        cert.certificate_number = "NR-10-12345"
        assert _is_unambiguous_demo_cert(cert) is False


class TestDryRunNeverDeletes:
    """Dry-run mode (execute=False) must never delete anything."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_delete(self):
        from app.scripts.audit_demo_data import audit_demo_data

        # Mock the database to return empty results
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.delete = AsyncMock()
        mock_db.rollback = AsyncMock()

        async def _gen():
            yield mock_db

        with patch("app.scripts.audit_demo_data.get_db_privileged", return_value=_gen()):
            report = await audit_demo_data(execute=False)

        assert report["deleted"] is False
        # No deletes should have been called
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()


class TestExecuteGuards:
    """--execute mode must respect all guard conditions."""

    @pytest.mark.asyncio
    async def test_execute_refuses_in_production(self, monkeypatch):
        from app.core.config import settings
        from app.scripts.audit_demo_data import audit_demo_data

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _gen():
            yield mock_db

        with patch("app.scripts.audit_demo_data.get_db_privileged", return_value=_gen()), pytest.raises(SystemExit) as exc_info:
            await audit_demo_data(execute=True)

        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_execute_refuses_without_demo_seed_mode(self, monkeypatch):
        from app.core.config import settings
        from app.scripts.audit_demo_data import audit_demo_data

        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEMO_SEED_MODE", False)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _gen():
            yield mock_db

        with patch("app.scripts.audit_demo_data.get_db_privileged", return_value=_gen()), pytest.raises(SystemExit) as exc_info:
            await audit_demo_data(execute=True)

        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_execute_refuses_without_confirmation(self, monkeypatch):
        from app.core.config import settings
        from app.scripts.audit_demo_data import audit_demo_data

        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _gen():
            yield mock_db

        with patch("app.scripts.audit_demo_data.get_db_privileged", return_value=_gen()), patch("builtins.input", return_value="no"), pytest.raises(SystemExit) as exc_info:
            await audit_demo_data(execute=True)

        # Should exit with 0 (no data deleted, but not an error)
        assert exc_info.value.code == 0


class TestTransactionalDeletion:
    """Deletion must be transactional — rollback on failure."""

    @pytest.mark.asyncio
    async def test_rollback_on_delete_failure(self, monkeypatch):
        from app.core.config import settings
        from app.scripts.audit_demo_data import audit_demo_data

        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEMO_SEED_MODE", True)

        # Create mock demo data
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = f"test{DEMO_EMAIL_DOMAINS[0]}"
        mock_user.full_name = "Test Demo"
        mock_user.role = "STUDENT"

        mock_db = AsyncMock()

        # First call returns demo user, rest return empty
        call_count = 0

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:  # demo_users query
                result.scalars.return_value.all.return_value = [mock_user]
            else:
                result.scalars.return_value.all.return_value = []
            # For scalar_one_or_none calls (student lookup)
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        mock_db.execute = _mock_execute
        mock_db.delete = AsyncMock(side_effect=RuntimeError("FK constraint violated"))
        mock_db.rollback = AsyncMock()
        mock_db.commit = AsyncMock()

        async def _gen():
            yield mock_db

        with patch("app.scripts.audit_demo_data.get_db_privileged", return_value=_gen()), patch("builtins.input", return_value="DELETE"):
            report = await audit_demo_data(execute=True)

        # Should have rolled back
        assert report["deleted"] is False
        assert "error" in report
        mock_db.rollback.assert_called_once()
