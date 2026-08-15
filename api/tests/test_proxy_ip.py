"""Testa trusted proxy IP resolution para rate limiting."""

from unittest.mock import Mock

from app.core.proxy import _is_trusted_proxy, get_client_ip


def _make_request(client_host: str, forwarded_for: str | None = None) -> Mock:
    """Cria um mock Request com client.host e headers."""
    headers = {}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for
    return Mock(
        client=Mock(host=client_host),
        headers=headers,
    )


class TestTrustedProxy:
    def test_no_trusted_proxies_returns_direct_ip(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.TRUSTED_PROXY_CIDRS", "")
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        request = _make_request("203.0.113.1", forwarded_for="198.51.100.1")
        assert get_client_ip(request) == "203.0.113.1"

    def test_trusted_proxy_returns_forwarded_ip(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        request = _make_request("10.0.0.1", forwarded_for="203.0.113.1, 10.0.0.1")
        assert get_client_ip(request) == "203.0.113.1"

    def test_untrusted_proxy_returns_direct_ip(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        # Connection from public IP claiming forwarded — should NOT trust
        request = _make_request("203.0.113.99", forwarded_for="198.51.100.1")
        assert get_client_ip(request) == "203.0.113.99"

    def test_trusted_proxy_no_forwarded_header(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        request = _make_request("10.0.0.1", forwarded_for=None)
        assert get_client_ip(request) == "10.0.0.1"

    def test_multiple_trusted_cidrs(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.TRUSTED_PROXY_CIDRS",
            "10.0.0.0/8,172.16.0.0/12",
        )
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        assert _is_trusted_proxy("10.0.0.1") is True
        assert _is_trusted_proxy("172.16.0.1") is True
        assert _is_trusted_proxy("192.168.1.1") is False
        assert _is_trusted_proxy("203.0.113.1") is False

    def test_invalid_cidr_silently_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.TRUSTED_PROXY_CIDRS",
            "invalid,10.0.0.0/8",
        )
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        assert _is_trusted_proxy("10.0.0.1") is True
        assert _is_trusted_proxy("203.0.113.1") is False

    def test_unknown_client_returns_unknown(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.TRUSTED_PROXY_CIDRS", "")
        from app.core import proxy
        proxy._TRUSTED_NETWORKS = None  # reset cache

        request = Mock(client=None, headers={})
        assert get_client_ip(request) == "unknown"
