from shared.config.settings import load_settings


def test_settings_use_default_port_and_optional_supabase_values(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    settings = load_settings()

    assert settings.port == 8000
    assert settings.supabase_url is None
    assert settings.supabase_service_key is None


def test_settings_read_environment_overrides(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")

    settings = load_settings()

    assert settings.port == 9000
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_key == "service-key"
