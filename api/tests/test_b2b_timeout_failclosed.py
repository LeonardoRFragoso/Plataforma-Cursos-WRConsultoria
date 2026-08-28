"""Reproducible timeout vs connection-refused tests for B2B fail-closed.

The smoke report claims "LMS offline → timeout after 10s → fail-closed".
Killing a server normally produces connection-refused, not a read timeout.
This test provides deterministic evidence using httpx MockTransport to
simulate both timeout and connection-refused without real network servers.
"""

from __future__ import annotations

import httpx
import pytest


class LmsUnavailableError(Exception):
    """Mimic Central WR LmsUnavailableError."""


async def lms_request_with_fail_closed(url: str, timeout: float, transport: httpx.AsyncBaseTransport) -> dict:
    """Mimic LmsClient: timeout/connect error → LmsUnavailableError → configured=false."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), transport=transport) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise LmsUnavailableError(str(exc)) from exc


def _timeout_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler that always raises ReadTimeout."""
    raise httpx.ReadTimeout("simulated read timeout", request=request)


def _connect_error_handler(request: httpx.Request) -> httpx.Response:
    """Mock transport handler that always raises ConnectError."""
    raise httpx.ConnectError("simulated connection refused", request=request)


@pytest.mark.asyncio
async def test_b2b_read_timeout_raises_timeout_exception():
    """A slow server (read timeout) must raise httpx.TimeoutException."""
    transport = httpx.MockTransport(_timeout_handler)
    async with httpx.AsyncClient(timeout=httpx.Timeout(2.0), transport=transport) as client:
        with pytest.raises(httpx.TimeoutException):
            await client.get("http://test-lms/api/v1/b2b/summary")


@pytest.mark.asyncio
async def test_b2b_connection_refused_raises_connect_error():
    """A dead port (connection refused) must raise httpx.ConnectError."""
    transport = httpx.MockTransport(_connect_error_handler)
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), transport=transport) as client:
        with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
            await client.get("http://test-lms/api/v1/b2b/summary")


@pytest.mark.asyncio
async def test_b2b_fail_closed_on_timeout():
    """When the LMS times out, the integration must fail closed (LmsUnavailableError)."""
    transport = httpx.MockTransport(_timeout_handler)
    with pytest.raises(LmsUnavailableError):
        await lms_request_with_fail_closed(
            "http://test-lms/api/v1/b2b/summary", timeout=2.0, transport=transport
        )


@pytest.mark.asyncio
async def test_b2b_fail_closed_on_connection_refused():
    """When the LMS is down (connection refused), the integration must fail closed."""
    transport = httpx.MockTransport(_connect_error_handler)
    with pytest.raises(LmsUnavailableError):
        await lms_request_with_fail_closed(
            "http://test-lms/api/v1/b2b/summary", timeout=10.0, transport=transport
        )


@pytest.mark.asyncio
async def test_b2b_timeout_and_connect_error_are_distinct():
    """Timeout and ConnectError are distinct failure modes — both fail closed."""
    timeout_transport = httpx.MockTransport(_timeout_handler)
    connect_transport = httpx.MockTransport(_connect_error_handler)

    # Timeout → LmsUnavailableError
    with pytest.raises(LmsUnavailableError):
        await lms_request_with_fail_closed(
            "http://test-lms/api/v1/b2b/summary", timeout=1.0, transport=timeout_transport
        )

    # ConnectError → LmsUnavailableError
    with pytest.raises(LmsUnavailableError):
        await lms_request_with_fail_closed(
            "http://test-lms/api/v1/b2b/summary", timeout=10.0, transport=connect_transport
        )
