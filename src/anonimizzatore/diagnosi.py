"""Diagnosi della lettura di un PDF: quanto bene si legge, pagina per pagina.

Stampa solo numeri (metodo, parole, confidenza, parole incerte, secondi), mai il contenuto:
l'utente la lancia sui suoi documenti reali e può condividere il risultato senza rischi.

Uso: python -m anonimizzatore.diagnosi documento.pdf [altri.pdf ...]
"""

import argparse
import sys
from pathlib import Path

from anonimizzatore.estrazione import DocumentoNonSupportato
from anonimizzatore.estrazione import ocr as modulo_ocr
from anonimizzatore.estrazione.pdf import leggi_pagine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m anonimizzatore.diagnosi",
        description="Mostra quanto bene si legge ogni pagina di un PDF, senza mostrarne il testo.",
    )
    parser.add_argument("documenti", nargs="+", type=Path)
    parser.add_argument("--dpi", type=int, default=modulo_ocr.DPI)
    parser.add_argument("--psm", type=int, default=3, help="segmentazione di Tesseract (3, 6, 11)")
    argomenti = parser.parse_args(argv)

    print(f"OCR disponibile: {'sì' if modulo_ocr.disponibile() else 'no'}")
    for percorso in argomenti.documenti:
        print(f"\n{percorso.name}")
        try:
            pagine = leggi_pagine(percorso, argomenti.dpi, argomenti.psm)
        except DocumentoNonSupportato as errore:
            print(f"  non leggibile: {errore}")
            continue
        intestazione = ("pagina", "metodo", "parole", "confidenza", "incerte", "secondi")
        print("  {:>6}  {:6}  {:>6}  {:>10}  {:>7}  {:>7}".format(*intestazione))
        for p in pagine:
            confidenza = f"{p.confidenza_media:.1f}" if p.confidenza_media is not None else "-"
            incerte = f"{len(p.incerti) / p.parole:.0%}" if p.metodo == "ocr" and p.parole else "-"
            print(
                f"  {p.numero:>6}  {p.metodo:6}  {p.parole:>6}  {confidenza:>10}  {incerte:>7}"
                f"  {p.secondi:>7.2f}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
