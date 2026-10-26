"""Riga di comando, per sviluppo e test: anonimizza un file e ne scrive il testo pseudonimizzato.

Il riepilogo (--report) contiene tipi, posizioni e conteggi, mai i valori originali.
"""

import argparse
import json
import sys
from pathlib import Path

from anonimizzatore import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="anonimizzatore",
        description="Toglie i dati personali da un documento prima di darlo a un'AI.",
    )
    parser.add_argument("documento", nargs="?", type=Path, help="PDF, Word (.docx) o .txt")
    parser.add_argument("--out", type=Path, help="file .txt in cui scrivere il risultato")
    parser.add_argument("--report", type=Path, help="file .json con il riepilogo, senza valori")
    parser.add_argument("--senza-nota", action="store_true", help="non aggiungere la nota per l'AI")
    parser.add_argument("--versione", action="version", version=f"%(prog)s {__version__}")
    argomenti = parser.parse_args(argv)
    if argomenti.documento is None:
        parser.print_help()
        return 0

    # Import qui: caricano il modello linguistico, che serve solo per analizzare.
    from anonimizzatore.estrazione import DocumentoNonSupportato
    from anonimizzatore.motore import analizza_file, applica, riepilogo

    try:
        analisi = analizza_file(argomenti.documento)
    except DocumentoNonSupportato as errore:
        print(errore, file=sys.stderr)
        return 2

    risultato = applica(analisi, nota_per_ai=not argomenti.senza_nota)
    if argomenti.out:
        argomenti.out.write_text(risultato + "\n", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(risultato)
    if argomenti.report:
        dati = json.dumps(riepilogo(analisi), ensure_ascii=False, indent=2)
        argomenti.report.write_text(dati, encoding="utf-8")

    print(
        f"{len(analisi.mascherati)} dati mascherati, {len(analisi.segnalati)} da valutare.",
        file=sys.stderr,
    )
    for avviso in analisi.avvisi:
        print(f"Avviso: {avviso}", file=sys.stderr)
    return 0
