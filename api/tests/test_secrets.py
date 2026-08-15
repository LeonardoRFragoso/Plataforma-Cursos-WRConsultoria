from unittest.mock import patch

from app.core.secrets import validate_allowed_hosts, validate_secret_key, validate_secrets


def test_validate_secret_key_flags_short_key():
    with patch("app.core.secrets.settings.SECRET_KEY", "short"):
        issues = validate_secret_key()
        assert any("32 characters" in issue for issue in issues)


def test_validate_secret_key_flags_default_placeholder():
    with patch("app.core.secrets.settings.SECRET_KEY", "your-secret-key-change-in-production"):
        issues = validate_secret_key()
        assert any("placeholder" in issue for issue in issues)


def test_validate_secret_key_passes_with_strong_key():
    with patch(
        "app.core.secrets.settings.SECRET_KEY",
        "a-strong-secret-key-at-least-32-characters-long",
    ):
        assert validate_secret_key() == []


def test_validate_allowed_hosts_flags_wildcard():
    with patch("app.core.secrets.settings.ALLOWED_HOSTS", ["*"]):
        issues = validate_allowed_hosts()
        assert any("wildcard" in issue for issue in issues)


def test_validate_allowed_hosts_passes_with_explicit_hosts():
    with patch("app.core.secrets.settings.ALLOWED_HOSTS", ["example.com"]):
        assert validate_allowed_hosts() == []
