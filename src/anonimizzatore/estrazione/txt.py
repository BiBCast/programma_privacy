import codecs
from pathlib import Path

from anonimizzatore.estrazione import TestoEstratto


def estrai_txt(percorso: Path) -> TestoEstratto:
    dati = percorso.read_bytes()
    # Il Blocco note salva in UTF-16 quando si sceglie "Unicode".
    if dati.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return TestoEstratto(dati.decode("utf-16"))
    try:
        return TestoEstratto(dati.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return TestoEstratto(dati.decode("cp1252", errors="replace"))
