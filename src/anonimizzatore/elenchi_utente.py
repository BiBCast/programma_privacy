"""Elenchi personali di ogni utente, in %APPDATA%\\Anonimizzatore.

- `sempre_da_mascherare.txt`: parole o nomi da mascherare sempre (clienti, codici interni);
- `mai_da_mascherare.txt`: parole da non mascherare mai (il nome dello studio);
- `parole_sensibili_mie.txt`: parole sensibili in più, da segnalare in revisione.

Una voce per riga; le righe che iniziano con # sono commenti. L'analisi legge soltanto: i file
li crea `prepara()` al primo avvio dell'applicazione, mai durante l'analisi di un documento.
"""

import os
from dataclasses import dataclass
from pathlib import Path

SEMPRE = "sempre_da_mascherare.txt"
MAI = "mai_da_mascherare.txt"
SENSIBILI = "parole_sensibili_mie.txt"

_INTESTAZIONI = {
    SEMPRE: "# Parole o nomi da mascherare sempre, una per riga.",
    MAI: "# Parole da non mascherare mai, una per riga.",
    SENSIBILI: "# Parole sensibili da segnalare in revisione, una per riga. L'asterisco finale "
    "accetta qualunque desinenza (malatti*).",
}


@dataclass(frozen=True)
class ElenchiUtente:
    sempre: tuple[str, ...] = ()
    mai: tuple[str, ...] = ()
    sensibili: tuple[str, ...] = ()


def cartella() -> Path:
    # ANONIMIZZATORE_DATI serve ai test e a chi vuole tenere gli elenchi altrove.
    personalizzata = os.environ.get("ANONIMIZZATORE_DATI")
    if personalizzata:
        return Path(personalizzata)
    base = os.environ.get("APPDATA") or Path.home()
    return Path(base) / "Anonimizzatore"


def prepara() -> Path:
    """Crea la cartella e i file vuoti, se mancano. Da chiamare all'avvio dell'applicazione."""
    radice = cartella()
    radice.mkdir(parents=True, exist_ok=True)
    for nome, intestazione in _INTESTAZIONI.items():
        percorso = radice / nome
        if not percorso.exists():
            percorso.write_text(intestazione + "\n", encoding="utf-8")
    return radice


def carica() -> ElenchiUtente:
    radice = cartella()
    return ElenchiUtente(*(_voci(radice / nome) for nome in (SEMPRE, MAI, SENSIBILI)))


def _voci(percorso: Path) -> tuple[str, ...]:
    if not percorso.is_file():
        return ()
    righe = (riga.strip() for riga in percorso.read_text(encoding="utf-8").splitlines())
    return tuple(dict.fromkeys(riga for riga in righe if riga and not riga.startswith("#")))
