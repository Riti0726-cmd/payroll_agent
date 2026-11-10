import os
from typing import Literal


class FoundryConfigError(ValueError):
    """Raised when required Microsoft Foundry settings are missing."""


def require_foundry_settings() -> tuple[str, str]:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "").strip()
    if not endpoint or not model:
        raise FoundryConfigError(
            "FOUNDRY_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME must be set."
        )
    return endpoint, model


def require_llm_api_key() -> str:
    """Static API key for Foundry / OpenAI-compatible Responses calls (no Entra ID)."""
    for name in (
        "AZURE_AI_API_KEY",
        "FOUNDRY_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
    ):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    raise FoundryConfigError(
        "Set AZURE_AI_API_KEY (or FOUNDRY_API_KEY / AZURE_OPENAI_API_KEY) for LLM API-key auth."
    )


def get_llm_base_url(project_endpoint: str | None = None) -> str:
    endpoint = (project_endpoint or os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")).strip().rstrip("/")
    if not endpoint:
        raise FoundryConfigError("FOUNDRY_PROJECT_ENDPOINT must be set.")
    override = os.environ.get("FOUNDRY_OPENAI_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    return f"{endpoint}/openai/v1"


def get_default_lookback_days() -> int:
    raw = os.environ.get("DEFAULT_LOOKBACK_DAYS", "7").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 7


def get_default_interval_hours() -> int:
    raw = os.environ.get("DEFAULT_INTERVAL_HOURS", "4").strip()
    try:
        value = int(raw)
    except ValueError:
        return 4
    if value not in (2, 4, 24):
        return 4
    return value


IntervalHours = Literal[2, 4, 24]


def get_database_url() -> str | None:
    """Neon/Postgres URL for email_processing. None if unset (local mock path)."""
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None
