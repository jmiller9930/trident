def test_import_main_app():
    from app.main import app  # noqa: F401

    assert app.title == "Trident API"


def test_import_settings():
    from app.config.settings import settings

    assert settings.env == "development"
