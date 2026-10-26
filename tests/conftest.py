import pytest


@pytest.fixture(autouse=True)
def elenchi_utente_isolati(tmp_path, monkeypatch):
    """Ogni test usa una cartella degli elenchi personali vuota, mai quella vera dell'utente."""
    cartella = tmp_path / "dati_utente"
    monkeypatch.setenv("ANONIMIZZATORE_DATI", str(cartella))
    return cartella
