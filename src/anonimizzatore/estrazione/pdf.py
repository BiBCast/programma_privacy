"""Testo dai PDF che contengono testo selezionabile.

La modalità `layout` conserva le colonne: nelle buste paga etichetta e valore restano sulla
stessa riga, separati da più spazi.
"""

from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

from anonimizzatore.estrazione import DocumentoNonSupportato, TestoEstratto

# Sotto questa soglia una pagina è considerata senza testo, probabilmente scansionata.
_MIN_CARATTERI = 20


def estrai_pdf(percorso: Path) -> TestoEstratto:
    try:
        with pdfplumber.open(percorso) as documento:
            pagine = [pagina.extract_text(layout=True) or "" for pagina in documento.pages]
    except Exception as errore:
        if _protetto(errore):
            raise DocumentoNonSupportato(
                "Il PDF è protetto da password. Toglila (o stampalo in un nuovo PDF) e riprova."
            ) from errore
        raise DocumentoNonSupportato("Il file PDF è danneggiato o non si può leggere.") from errore

    vuote = [n for n, testo in enumerate(pagine, 1) if len(testo.strip()) < _MIN_CARATTERI]
    if not pagine or len(vuote) * 2 > len(pagine):
        raise DocumentoNonSupportato(
            "Il PDF sembra una scansione (un'immagine) e non contiene testo da leggere. "
            "Per ora questi PDF non sono supportati."
        )
    avvisi = ()
    if vuote:
        elenco = ", ".join(map(str, vuote))
        avvisi = (
            f"Alcune pagine non contengono testo (pagine {elenco}): potrebbero essere "
            "scansionate e non sono incluse nel risultato.",
        )
    return TestoEstratto("\n\n".join(pagine), avvisi)


def _protetto(errore: BaseException) -> bool:
    # pdfplumber avvolge gli errori di pdfminer: si guarda anche dentro.
    da_controllare = [errore, *errore.args, errore.__cause__, errore.__context__]
    return any(isinstance(e, PDFPasswordIncorrect | PDFEncryptionError) for e in da_controllare)
