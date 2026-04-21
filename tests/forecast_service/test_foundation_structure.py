from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_requested_python_service_boundaries_exist():
    assert (ROOT / "apps" / "forecast_service").is_dir()
    assert (ROOT / "apps" / "llm_service").is_dir()
    assert (ROOT / "shared" / "config").is_dir()
    assert (ROOT / "shared" / "logging").is_dir()
    assert (ROOT / "shared" / "utils").is_dir()


def test_forecast_service_source_excludes_language_generation_concerns():
    forbidden_terms = ("grok", "prompt", "chat", "explanation")
    service_files = (ROOT / "apps" / "forecast_service").rglob("*.py")

    combined_source = "\n".join(path.read_text() for path in service_files).lower()

    for term in forbidden_terms:
        assert term not in combined_source


def test_prophet_is_declared_for_real_forecasting():
    dependency_files = [
        ROOT / "pyproject.toml",
        ROOT / "requirements.txt",
        ROOT / "requirements-dev.txt",
    ]

    combined_dependencies = "\n".join(path.read_text().lower() for path in dependency_files)

    assert "prophet" in combined_dependencies


def test_forecast_service_has_independent_dockerfile():
    dockerfile = ROOT / "apps" / "forecast_service" / "Dockerfile"

    assert dockerfile.is_file()

    contents = dockerfile.read_text()
    assert "apps.forecast_service.app.main:app" in contents
    assert "PORT:-8000" in contents
