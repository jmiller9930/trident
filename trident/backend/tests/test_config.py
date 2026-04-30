from app.config.settings import Settings


def test_settings_defaults():
    s = Settings()
    assert s.log_level == "INFO"
    assert s.db_host == "trident-db"
