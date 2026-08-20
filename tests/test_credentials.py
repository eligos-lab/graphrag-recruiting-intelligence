from pydantic import SecretStr

from app.llm.credentials import first_secret_value


def test_first_secret_value_skips_empty_configured_secrets() -> None:
    assert first_secret_value(SecretStr(""), SecretStr("fallback-key")) == "fallback-key"
    assert first_secret_value(None, SecretStr("  primary-key  ")) == "primary-key"
    assert first_secret_value(None, SecretStr("")) == ""
