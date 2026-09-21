import pytest


@pytest.fixture(autouse=True)
def legacy_test_installation(monkeypatch):
    """Existing mission fixtures use the original explicitly enabled installation."""
    monkeypatch.setenv("AGORA_LEGACY_INSTALLATION", "1")
    monkeypatch.delenv("AGORA_AGENTS_FILE", raising=False)
