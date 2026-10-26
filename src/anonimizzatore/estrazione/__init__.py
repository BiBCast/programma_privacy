"""Estrazione del testo da PDF, Word (.docx) e file di testo.

Ogni estrattore restituisce testo grezzo; `estrai` sceglie l'estrattore dall'estensione e
normalizza il risultato. Gli offset delle entità trovate dopo si riferiscono al testo
normalizzato.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestoEstratto:
    testo: str
    avvisi: tuple[str, ...] = ()


class DocumentoNonSupportato(Exception):
    """Il documento non si può leggere. Il messaggio è pensato per l'utente finale."""


# Spazi "speciali" che diventano spazi normali.
_SPAZI = dict.fromkeys(map(ord, "     "), " ")
# Caratteri invisibili che potrebbero spezzare un nome ("Ro​ssi") e far sfuggire il dato.
_INVISIBILI = dict.fromkeys(map(ord, "­​‌‍⁠﻿"), None)
_CONTROLLO = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RIGHE_VUOTE = re.compile(r"\n{3,}")


def normalizza(testo: str) -> str:
    testo = testo.replace("\r\n", "\n").replace("\r", "\n")
    testo = unicodedata.normalize("NFC", testo)
    testo = testo.translate(_SPAZI).translate(_INVISIBILI)
    testo = _CONTROLLO.sub("", testo)
    testo = "\n".join(riga.rstrip() for riga in testo.split("\n"))
    return _RIGHE_VUOTE.sub("\n\n", testo).strip("\n")


def _estrattori() -> dict[str, Callable[[Path], TestoEstratto]]:
    # Import qui per non caricare pdfplumber quando serve solo il testo.
    from anonimizzatore.estrazione import docx, pdf, txt

    return {".pdf": pdf.estrai_pdf, ".docx": docx.estrai_docx, ".txt": txt.estrai_txt}


def estrai(percorso: str | Path) -> TestoEstratto:
    percorso = Path(percorso)
    estensione = percorso.suffix.lower()
    if estensione == ".doc":
        raise DocumentoNonSupportato(
            "I file Word del vecchio formato (.doc) non sono supportati. "
            "Apri il file con Word, salvalo come .docx e riprova."
        )
    estrattore = _estrattori().get(estensione)
    if estrattore is None:
        raise DocumentoNonSupportato(
            "Formato non supportato. Puoi aprire file PDF, Word (.docx) o di testo (.txt)."
        )
    if not percorso.is_file():
        raise DocumentoNonSupportato("Il file non esiste o non è raggiungibile.")

    grezzo = estrattore(percorso)
    testo = normalizza(grezzo.testo)
    if not testo.strip():
        raise DocumentoNonSupportato("Il documento non contiene testo.")
    return TestoEstratto(testo, grezzo.avvisi)
