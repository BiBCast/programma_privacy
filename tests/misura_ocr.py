"""Misura quanti nomi del corpus sintetico spariscono dal testo finale dopo una scansione finta.

Uso: python tests/misura_ocr.py [quanti] [dpi,dpi] [psm,psm]
Esempio: python tests/misura_ocr.py 60 300,200 3,6
"""

import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from anonimizzatore.estrazione import estrai  # noqa: E402
from anonimizzatore.estrazione import pdf as modulo_pdf  # noqa: E402
from anonimizzatore.motore import analizza, applica  # noqa: E402
from generatori.corpus import CATEGORIE, MODELLI, genera  # noqa: E402
from generatori.scansioni import pdf_di_testo, scansiona  # noqa: E402

_MASSIMO_RIGA = 95


def righe_del_documento(testo: str) -> list[str]:
    """Spezza solo dopo un punto o un punto e virgola, così un nome non va mai a capo."""
    righe, corrente = [], ""
    for pezzo in testo.replace("; ", ";\n").replace(". ", ".\n").split("\n"):
        if corrente and len(corrente) + 1 + len(pezzo) > _MASSIMO_RIGA:
            righe.append(corrente)
            corrente = pezzo
        else:
            corrente = f"{corrente} {pezzo}".strip()
    return [*righe, corrente, ""]


def _quasi_uguale(a: str, b: str) -> bool:
    """Uguali o diverse per un solo carattere (sostituito, aggiunto o tolto)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    corta, lunga = sorted((a, b), key=len)
    return any(lunga[:i] + lunga[i + 1 :] == corta for i in range(len(lunga)))


def misura(quanti: int, dpi: int, psm: int, cartella: Path) -> None:
    documenti = genera(quanti, seme=11)
    righe = [riga for d in documenti for riga in righe_del_documento(d.testo)]
    testo_pdf = pdf_di_testo(cartella / "corpus.pdf", righe)
    scansione = scansiona(testo_pdf, cartella / f"corpus_{dpi}.pdf", dpi=dpi)

    inizio = time.perf_counter()
    pagine = modulo_pdf.leggi_pagine(scansione, psm=psm)
    secondi = time.perf_counter() - inizio
    estratto = estrai(scansione)
    analisi = analizza(
        estratto.testo, incerti=estratto.incerti, letto_con_ocr=estratto.letto_con_ocr
    )
    risultato = applica(analisi, nota_per_ai=False)
    segnalate = {
        p.casefold()
        for d in analisi.segnalati
        for p in re.findall(r"[^\W\d_][\w'’]*", d.entita.valore)
    }

    # Un nome è sfuggito se nel testo finale resta una sua parola, anche letta con una lettera
    # sbagliata ("Rossl"): l'OCR può far "sparire" un nome senza mascherarlo.
    parole_finali = {p.casefold() for p in re.findall(r"[^\W\d_][\w'’]*", risultato)}
    parole_dei_modelli = {p.casefold() for m in MODELLI for p in re.findall(r"[^\W\d_]+", m)}
    totali, spariti, visti = Counter(), Counter(), Counter()
    for documento in documenti:
        for (a, b), categoria in zip(documento.nomi, documento.categorie, strict=True):
            totali[categoria] += 1
            parole_nome = [
                p.casefold()
                for p in re.findall(r"[^\W\d_][\w'’]*", documento.testo[a:b])
                if len(p) >= 3 and p.casefold() not in parole_dei_modelli
            ]
            rimaste = {f for p in parole_nome for f in parole_finali if _quasi_uguale(p, f)}
            spariti[categoria] += not rimaste
            visti[categoria] += rimaste <= segnalate  # ciò che resta è tra i dati da valutare
    n = sum(totali.values())
    confidenza = sum(p.confidenza_media or 0 for p in pagine) / len(pagine)
    print(
        f"\n{dpi} dpi, psm {psm}: {len(pagine)} pagine, {secondi / len(pagine):.1f} s/pagina, "
        f"confidenza media {confidenza:.1f}"
    )
    for categoria in CATEGORIE:
        if totali[categoria]:
            _riga(categoria, totali[categoria], spariti[categoria], visti[categoria])
    _riga("totale", n, sum(spariti.values()), sum(visti.values()))


def _riga(nome: str, totale: int, nascosti: int, visti: int) -> None:
    print(
        f"  {nome:22} {totale:4} nomi  {nascosti / totale:6.1%} nascosti"
        f"  {visti / totale:6.1%} con i segnalati"
    )


if __name__ == "__main__":
    quanti = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    risoluzioni = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "300,200").split(",")]
    modalita = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "3").split(",")]
    with tempfile.TemporaryDirectory() as cartella:
        for dpi in risoluzioni:
            for psm in modalita:
                misura(quanti, dpi, psm, Path(cartella))
