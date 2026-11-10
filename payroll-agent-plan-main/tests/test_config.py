import pytest

from config import (
    FoundryConfigError,
    get_llm_base_url,
    require_foundry_settings,
    require_llm_api_key,
)


def test_require_foundry_settings_success(monkeypatch):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/Test")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    endpoint, model = require_foundry_settings()
    assert endpoint == "https://example.ai.azure.com/api/projects/Test"
    assert model == "gpt-4o"


def test_require_foundry_settings_missing_endpoint(monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    with pytest.raises(FoundryConfigError):
        require_foundry_settings()


def test_require_foundry_settings_missing_model(monkeypatch):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/Test")
    monkeypatch.delenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", raising=False)
    with pytest.raises(FoundryConfigError):
        require_foundry_settings()


def test_require_llm_api_key(monkeypatch):
    monkeypatch.delenv("AZURE_AI_API_KEY", raising=False)
    monkeypatch.delenv("FOUNDRY_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(FoundryConfigError):
        require_llm_api_key()
    monkeypatch.setenv("AZURE_AI_API_KEY", "sk-test")
    assert require_llm_api_key() == "sk-test"


def test_llm_base_url(monkeypatch):
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://example.ai.azure.com/api/projects/Test/",
    )
    monkeypatch.delenv("FOUNDRY_OPENAI_BASE_URL", raising=False)
    assert get_llm_base_url() == "https://example.ai.azure.com/api/projects/Test/openai/v1"
