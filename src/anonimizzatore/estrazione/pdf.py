"""Testo dai PDF: con `pdfplumber` le pagine di testo, con l'OCR le pagine scansionate.

La modalità `layout` di pdfplumber conserva le colonne: nelle buste paga etichetta e valore
restano sulla stessa riga, separati da più spazi. L'OCR ricostruisce lo stesso formato.
Ogni pagina è normalizzata da sola, così gli intervalli delle parole incerte dell'OCR restano
validi nel testo finale.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

from anonimizzatore.estrazione import DocumentoNonSupportato, TestoEstratto, normalizza, ocr

# Sotto questa soglia una pagina è considerata senza testo, probabilmente scansionata.
_MIN_CARATTERI = 20
# Sotto questa confidenza media una pagina letta con l'OCR è "poco leggibile".
_CONFIDENZA_PAGINA_BASSA = 70


@dataclass(frozen=True)
class Pagina:
    numero: int
    metodo: str  # "testo", "ocr" o "vuota" (scansione senza OCR disponibile)
    testo: str  # già normalizzato
    incerti: tuple[tuple[int, int], ...]
    parole: int
    confidenza_media: float | None  # solo per l'OCR
    secondi: float


def leggi_pagine(percorso: Path, dpi: int = ocr.DPI, psm: int = 3) -> list[Pagina]:
    try:
        with pdfplumber.open(percorso) as documento:
            testi = [pagina.extract_text(layout=True) or "" for pagina in documento.pages]
    except Exception as errore:
        if _protetto(errore):
            raise DocumentoNonSupportato(
                "Il PDF è protetto da password. Toglila (o stampalo in un nuovo PDF) e riprova."
            ) from errore
        raise DocumentoNonSupportato("Il file PDF è danneggiato o non si può leggere.") from errore

    pagine = []
    scansioni = None
    try:
        for numero, testo in enumerate(testi, 1):
            inizio = time.perf_counter()
            if len(testo.strip()) >= _MIN_CARATTERI:
                testo = normalizza(testo)
                pagine.append(
                    Pagina(numero, "testo", testo, (), len(testo.split()), None, _da(inizio))
                )
                continue
            if not ocr.disponibile():
                pagine.append(Pagina(numero, "vuota", "", (), 0, None, _da(inizio)))
                continue
            if scansioni is None:
                import pypdfium2

                scansioni = pypdfium2.PdfDocument(str(percorso))
            letta = ocr.leggi_pagina(scansioni[numero - 1], dpi, psm)
            testo = normalizza(letta.testo)
            # Il testo dell'OCR nasce già normalizzato; se non lo fosse, gli intervalli delle
            # parole incerte non sarebbero più affidabili e si lasciano perdere.
            incerti = letta.incerti if testo == letta.testo else ()
            pagine.append(
                Pagina(
                    numero, "ocr", testo, incerti, letta.parole, letta.confidenza_media, _da(inizio)
                )
            )
    finally:
        if scansioni is not None:
            scansioni.close()
    return pagine


def estrai_pdf(percorso: Path) -> TestoEstratto:
    pagine = leggi_pagine(percorso)
    if not any(p.testo for p in pagine):
        if any(p.metodo == "vuota" for p in pagine):
            raise DocumentoNonSupportato(
                "Il PDF è una scansione, ma il lettore OCR non è disponibile su questo PC. "
                "Reinstalla il programma o avvisa il responsabile."
            )
        raise DocumentoNonSupportato(
            "Il PDF non contiene testo leggibile, neanche con il riconoscimento dei caratteri."
        )

    parti, incerti, posizione = [], [], 0
    for pagina in pagine:
        if not pagina.testo:
            continue
        if parti:
            parti.append("\n\n")
            posizione += 2
        incerti += [(posizione + a, posizione + b) for a, b in pagina.incerti]
        parti.append(pagina.testo)
        posizione += len(pagina.testo)
    letto_con_ocr = any(p.metodo == "ocr" and p.parole for p in pagine)
    return TestoEstratto("".join(parti), _avvisi(pagine), tuple(incerti), letto_con_ocr)


def _avvisi(pagine: list[Pagina]) -> tuple[str, ...]:
    def numeri(lista: list[Pagina]) -> str:
        return ", ".join(str(p.numero) for p in lista)

    avvisi = []
    lette = [p for p in pagine if p.metodo == "ocr" and p.parole]
    if lette:
        avvisi.append(
            f"Pagine scansionate lette con il riconoscimento dei caratteri ({numeri(lette)}): "
            "controlla con attenzione i dati trovati, l'OCR può sbagliare."
        )
    illeggibili = [p for p in lette if (p.confidenza_media or 0) < _CONFIDENZA_PAGINA_BASSA]
    if illeggibili:
        avvisi.append(
            f"Pagine poco leggibili ({numeri(illeggibili)}): qualche nome o codice potrebbe "
            "essere stato letto male e sfuggire. Controllale una per una."
        )
    vuote = [p for p in pagine if not p.testo]
    if vuote:
        avvisi.append(
            f"Alcune pagine non contengono testo leggibile ({numeri(vuote)}) e non sono incluse "
            "nel risultato."
        )
    return tuple(avvisi)


def _da(inizio: float) -> float:
    return round(time.perf_counter() - inizio, 2)


def _protetto(errore: BaseException) -> bool:
    # pdfplumber avvolge gli errori di pdfminer: si guarda anche dentro.
    da_controllare = [errore, *errore.args, errore.__cause__, errore.__context__]
    return any(isinstance(e, PDFPasswordIncorrect | PDFEncryptionError) for e in da_controllare)
