from juus_server import Settings


def test_settings_loads_gateway_configuration_from_environment() -> None:
    settings = Settings.from_env(
        {
            "JUUS_ENV": "test",
            "JUUS_MODEL_BASE_URL": "https://gateway.invalid/v1",
            "JUUS_MODEL_API_KEY": "test-only-not-a-secret",
            "JUUS_MODEL_NAME": "fictional-model",
            "JUUS_DATABASE_URL": "sqlite:///:memory:",
        }
    )

    assert settings.environment == "test"
    assert settings.model_base_url == "https://gateway.invalid/v1"
    assert settings.model_name == "fictional-model"
    assert settings.database_url == "sqlite:///:memory:"
