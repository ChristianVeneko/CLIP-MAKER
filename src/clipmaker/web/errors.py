"""Map provider errors to short user-facing messages (Spanish UI copy)."""

from __future__ import annotations

import openai

REGION_BLOCKED = "OpenAI bloqueó la solicitud por región (403). Verifica tu VPN e inténtalo de nuevo."


def friendly_error(exc: BaseException) -> str | None:
    """A readable message for known OpenAI failures, or None to keep the raw error."""
    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        return "No se pudo conectar con OpenAI. Revisa tu conexión de red e inténtalo de nuevo."
    if not isinstance(exc, openai.APIStatusError):
        return None
    code = getattr(exc, "code", None)
    if exc.status_code == 403:
        if code == "unsupported_country_region_territory":
            return REGION_BLOCKED
        return "OpenAI rechazó la solicitud (403): la clave no tiene permiso para este modelo."
    if exc.status_code == 401:
        return "OpenAI rechazó la clave (401). Revisa que OPENAI_API_KEY sea válida."
    if exc.status_code == 429:
        if code == "insufficient_quota":
            return "Se agotó la cuota de OpenAI (429). Revisa tu plan y facturación."
        return "OpenAI alcanzó el límite de solicitudes (429). Espera un momento e inténtalo de nuevo."
    return None
