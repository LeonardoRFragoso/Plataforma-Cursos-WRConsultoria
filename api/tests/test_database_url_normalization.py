"""Tests for DATABASE_URL scheme normalization.

Railway and other platforms may expose ``postgres://`` or
``postgresql://`` URLs. SQLAlchemy async requires
``postgresql+asyncpg://``. The config layer normalizes the scheme
before the engine sees it.
"""

from app.core.config import _normalize_database_url


class TestDatabaseUrlNormalization:
    """Verify scheme normalization preserves everything except the scheme."""

    def test_postgres_scheme_normalized(self):
        """postgres:// → postgresql+asyncpg://"""
        url = "postgres://user:pass@host:5432/db"
        result = _normalize_database_url(url)
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgresql_scheme_normalized(self):
        """postgresql:// → postgresql+asyncpg://"""
        url = "postgresql://user:pass@host:5432/db"
        result = _normalize_database_url(url)
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_existing_asyncpg_unchanged(self):
        """postgresql+asyncpg:// → unchanged"""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = _normalize_database_url(url)
        assert result == url

    def test_existing_psycopg_unchanged(self):
        """postgresql+psycopg:// → unchanged"""
        url = "postgresql+psycopg://user:pass@host:5432/db"
        result = _normalize_database_url(url)
        assert result == url

    def test_query_params_preserved(self):
        """Query parameters are preserved through normalization."""
        url = "postgres://user:pass@host:5432/db?sslmode=require&pool_size=10"
        result = _normalize_database_url(url)
        assert result == "postgresql+asyncpg://user:pass@host:5432/db?sslmode=require&pool_size=10"

    def test_postgres_query_params_preserved(self):
        """Query parameters preserved for postgresql:// scheme."""
        url = "postgresql://user:pass@host:5432/db?sslmode=require"
        result = _normalize_database_url(url)
        assert result == "postgresql+asyncpg://user:pass@host:5432/db?sslmode=require"

    def test_sqlite_not_converted(self):
        """Non-PostgreSQL schemes are NOT converted."""
        url = "sqlite:///./test.db"
        result = _normalize_database_url(url)
        assert result == "sqlite:///./test.db"

    def test_mysql_not_converted(self):
        """MySQL scheme is NOT converted to PostgreSQL."""
        url = "mysql://user:pass@host:3306/db"
        result = _normalize_database_url(url)
        assert result == "mysql://user:pass@host:3306/db"

    def test_empty_url_unchanged(self):
        """Empty string is returned as-is."""
        assert _normalize_database_url("") == ""

    def test_railway_style_url(self):
        """Typical Railway-style postgres:// URL with credentials."""
        url = "postgres://pguser:secretpass@containers-us.railway.app:6543/railway"
        result = _normalize_database_url(url)
        assert result == "postgresql+asyncpg://pguser:secretpass@containers-us.railway.app:6543/railway"

    def test_no_credentials_in_normalized_output_beyond_input(self):
        """Normalization does not add or remove credentials — only scheme changes."""
        url = "postgres://user:pass@host:5432/db"
        result = _normalize_database_url(url)
        # The credentials portion is identical after the scheme
        assert "user:pass@host:5432/db" in result
        assert result.startswith("postgresql+asyncpg://")
