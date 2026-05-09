from app.settings import Settings


def test_fallback_model_default() -> None:
    assert Settings.model_fields["openrouter_fallback_model"].default == "google/gemma-4-31b-it:free"


def test_max_tokens_default() -> None:
    assert Settings.model_fields["max_tokens"].default == 2048


def test_log_level_default() -> None:
    assert Settings.model_fields["log_level"].default == "INFO"


def test_langsmith_tracing_default() -> None:
    assert Settings.model_fields["langsmith_tracing"].default is False


def test_langsmith_endpoint_default() -> None:
    assert Settings.model_fields["langsmith_endpoint"].default == "https://api.smith.langchain.com"
