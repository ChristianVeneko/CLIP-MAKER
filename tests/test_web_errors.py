import httpx
import openai
import pytest

from clipmaker.web.errors import friendly_error


def api_error(cls, status, code=None):
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(status, request=req)
    body = {"code": code, "message": "x"}  # the SDK exposes the inner "error" object
    return cls("Error code: %d" % status, response=resp, body=body)


def test_region_block():
    exc = api_error(openai.PermissionDeniedError, 403, "unsupported_country_region_territory")
    assert friendly_error(exc) == "OpenAI bloqueó la solicitud por región (403). Verifica tu VPN e inténtalo de nuevo."


def test_other_403_is_generic_permission():
    msg = friendly_error(api_error(openai.PermissionDeniedError, 403, "nope"))
    assert "403" in msg and "permiso" in msg.lower()


def test_invalid_key():
    assert "OPENAI_API_KEY" in friendly_error(api_error(openai.AuthenticationError, 401))


def test_rate_limit_and_quota():
    assert "límite" in friendly_error(api_error(openai.RateLimitError, 429, "rate_limit_exceeded")).lower()
    assert "cuota" in friendly_error(api_error(openai.RateLimitError, 429, "insufficient_quota")).lower()


def test_connection_error():
    exc = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    assert "conexión" in friendly_error(exc).lower()


@pytest.mark.parametrize("exc", [RuntimeError("boom"), ValueError("x")])
def test_unknown_errors_return_none(exc):
    assert friendly_error(exc) is None
