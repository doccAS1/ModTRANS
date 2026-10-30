import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path_factory, monkeypatch):
    """La memoria delle traduzioni non deve mai finire nella home vera di chi esegue i test."""
    monkeypatch.setenv("SKYRIMTRANS_HOME", str(tmp_path_factory.mktemp("skyrimtrans_home")))
