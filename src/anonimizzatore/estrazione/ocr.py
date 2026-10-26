"""OCR delle pagine scansionate con Tesseract, tutto in memoria.

La pagina diventa un'immagine PNG in memoria e arriva a Tesseract dallo standard input; il
risultato (TSV: una riga per parola, con posizione e confidenza) torna dallo standard output.
Nessun file temporaneo: niente `pytesseract`, che salva ogni immagine in %TEMP%.

Dalle posizioni delle parole si ricostruiscono righe e colonne, come fa `pdfplumber` con i PDF
di testo: due parole lontane sulla stessa riga restano separate da almeno due spazi, il
separatore di colonna che le etichette riconoscono.
"""

import io
import os
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from anonimizzatore.estrazione import normalizza

DPI = 300
# Sotto questa confidenza (0–100) una parola è "letta con poca sicurezza".
CONFIDENZA_INCERTA = 60
_TIMEOUT_PAGINA = 120  # secondi


@dataclass(frozen=True)
class Parola:
    testo: str
    sinistra: int
    alto: int
    larghezza: int
    altezza: int
    confidenza: float
    linea: tuple[int, int, int] = (0, 0, 0)  # blocco, paragrafo e riga secondo Tesseract

    @property
    def destra(self) -> int:
        return self.sinistra + self.larghezza

    @property
    def centro(self) -> float:
        return self.alto + self.altezza / 2


@dataclass(frozen=True)
class PaginaLetta:
    testo: str
    incerti: tuple[tuple[int, int], ...]  # intervalli nel testo della pagina
    parole: int
    confidenza_media: float


class OcrNonDisponibile(Exception):
    """Tesseract non si trova: né nel pacchetto, né in vendor/, né nel PATH."""


@cache
def tesseract() -> tuple[Path, Path]:
    """Percorsi di tesseract.exe e della cartella tessdata."""
    candidati = []
    if indicato := os.environ.get("ANONIMIZZATORE_TESSERACT"):
        indicato = Path(indicato)
        candidati.append(indicato / "tesseract.exe" if indicato.is_dir() else indicato)
    if getattr(sys, "frozen", False):  # il programma installato: tesseract/ accanto all'exe
        candidati.append(Path(sys.executable).parent / "tesseract" / "tesseract.exe")
    candidati.append(Path(__file__).resolve().parents[3] / "vendor" / "tesseract" / "tesseract.exe")
    if trovato := shutil.which("tesseract"):
        candidati.append(Path(trovato))
    for eseguibile in candidati:
        tessdata = eseguibile.parent / "tessdata"
        if eseguibile.is_file() and (tessdata / "ita.traineddata").is_file():
            return eseguibile, tessdata
    raise OcrNonDisponibile(
        "Il lettore OCR per i PDF scansionati non è disponibile su questo PC. "
        "Reinstalla il programma o avvisa il responsabile."
    )


def disponibile() -> bool:
    try:
        tesseract()
    except OcrNonDisponibile:
        return False
    return True


def leggi_pagina(pagina, dpi: int = DPI, psm: int = 3) -> PaginaLetta:
    """OCR di una pagina di pypdfium2, anche se è stata scansionata ruotata."""
    from PIL import ImageFilter, ImageOps

    immagine = pagina.render(scale=dpi / 72, grayscale=True).to_pil()
    # Il filtro mediano toglie i puntini delle fotocopie senza cancellare le lettere.
    immagine = immagine.convert("L").filter(ImageFilter.MedianFilter(3))

    def leggi(origine, gradi: int, risoluzione: int) -> list[Parola]:
        ruotata = ImageOps.autocontrast(origine.rotate(gradi, expand=True) if gradi else origine)
        dati = io.BytesIO()
        ruotata.save(dati, format="PNG")
        return leggi_immagine(dati.getvalue(), risoluzione, psm)

    parole = leggi(immagine, 0, dpi)
    # Una bolletta orizzontale in una pagina verticale: Tesseract legge lo stesso le parole,
    # ma girate, e le righe escono in ordine sbagliato. Lo si capisce dalla forma: le parole
    # sono più alte che larghe. Solo allora si prova a 90° e a 270° e si tiene la lettura
    # migliore.
    if _quota_verticali(parole) > 0.5:
        # 90° o 270°: si sceglie su una copia a metà risoluzione, quattro volte più veloce.
        ridotta = immagine.resize((immagine.width // 2, immagine.height // 2))
        prove = {gradi: leggi(ridotta, gradi, dpi // 2) for gradi in (90, 270)}
        gradi = max(prove, key=lambda g: (_quota_verticali(prove[g]) < 0.5, _confidenza(prove[g])))
        if _quota_verticali(prove[gradi]) < 0.5:
            parole = leggi(immagine, gradi, dpi)
    return impagina(parole)


def _quota_verticali(parole: list[Parola]) -> float:
    lunghe = [p for p in parole if len(p.testo) >= 3]
    return sum(p.altezza > p.larghezza for p in lunghe) / len(lunghe) if lunghe else 0.0


def _confidenza(parole: list[Parola]) -> float:
    return statistics.fmean(p.confidenza for p in parole) if parole else 0.0


def leggi_immagine(png: bytes, dpi: int = DPI, psm: int = 3) -> list[Parola]:
    eseguibile, tessdata = tesseract()
    comando = [
        str(eseguibile), "stdin", "stdout", "--tessdata-dir", str(tessdata), "-l", "ita",
        "--oem", "1", "--psm", str(psm), "--dpi", str(dpi), "tsv",
    ]  # fmt: skip
    risultato = subprocess.run(
        comando,
        input=png,
        capture_output=True,
        check=True,
        timeout=_TIMEOUT_PAGINA,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return _da_tsv(risultato.stdout.decode("utf-8", errors="replace"))


def _da_tsv(tsv: str) -> list[Parola]:
    parole = []
    righe = tsv.splitlines()
    for riga in righe[1:]:  # la prima riga è l'intestazione
        campi = riga.split("\t")
        if len(campi) < 12 or campi[0] != "5":  # livello 5 = parola
            continue
        # Ogni parola normalizzata da sola: così il testo della pagina è già normalizzato e
        # gli intervalli delle parole incerte restano validi.
        testo = normalizza(campi[11]).strip()
        if not testo:
            continue
        sinistra, alto, larghezza, altezza = (int(c) for c in campi[6:10])
        linea = (int(campi[2]), int(campi[3]), int(campi[4]))
        parole.append(Parola(testo, sinistra, alto, larghezza, altezza, float(campi[10]), linea))
    return parole


def impagina(parole: list[Parola]) -> PaginaLetta:
    """Righe e colonne dalle posizioni delle parole."""
    if not parole:
        return PaginaLetta("", (), 0, 0.0)
    altezza = statistics.median(p.altezza for p in parole) or 1
    carattere = statistics.median(p.larghezza / len(p.testo) for p in parole) or 1

    # Prima le righe di Tesseract, che seguono il testo anche su una pagina un po' storta.
    # Poi si uniscono le righe che stanno alla stessa altezza in blocchi diversi, come le
    # colonne di una busta paga: "Cognome e nome" e "ROSSI MARIO" tornano sulla stessa riga.
    linee: dict[tuple[int, int, int], list[Parola]] = {}
    for parola in parole:
        linee.setdefault(parola.linea, []).append(parola)
    righe: list[list[list[Parola]]] = []  # ogni riga: le sue linee di Tesseract
    for linea in sorted(linee.values(), key=_centro):
        if righe and abs(_centro(linea) - _centro(_parole(righe[-1]))) <= altezza * 0.6:
            righe[-1].append(linea)
        else:
            righe.append([linea])

    pezzi: list[str] = []
    incerti: list[tuple[int, int]] = []
    posizione = 0
    precedente = None
    for riga in righe:
        if precedente is not None:
            # Uno spazio verticale ampio diventa una riga vuota, come tra due paragrafi.
            distanza = _centro(_parole(riga)) - _centro(precedente)
            salto = "\n\n" if distanza > altezza * 2.2 else "\n"
            pezzi.append(salto)
            posizione += len(salto)
        fine_precedente = None
        # Le linee da sinistra a destra; dentro una linea l'ordine di lettura di Tesseract.
        for parola in _parole(sorted(riga, key=lambda linea: min(p.sinistra for p in linea))):
            if fine_precedente is not None:
                distanza = (parola.sinistra - fine_precedente) / carattere
                spazi = " " if distanza < 1.8 else " " * min(max(2, round(distanza)), 30)
                pezzi.append(spazi)
                posizione += len(spazi)
            if parola.confidenza < CONFIDENZA_INCERTA:
                incerti.append((posizione, posizione + len(parola.testo)))
            pezzi.append(parola.testo)
            posizione += len(parola.testo)
            fine_precedente = parola.destra
        precedente = _parole(riga)
    media = statistics.fmean(p.confidenza for p in parole)
    return PaginaLetta("".join(pezzi), tuple(incerti), len(parole), media)


def _centro(riga: list[Parola]) -> float:
    return statistics.fmean(p.centro for p in riga)


def _parole(linee: list[list[Parola]]) -> list[Parola]:
    return [p for linea in linee for p in linea]
