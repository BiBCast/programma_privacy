"""Misura la copertura dei nomi sul corpus sintetico, per categoria.

Uso: python tests/misura_nomi.py [quanti] [seme]
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from anonimizzatore.rilevamento import etichette, nomi, propagazione  # noqa: E402
from anonimizzatore.rilevamento.modelli import Azione, Tipo  # noqa: E402
from generatori.corpus import CATEGORIE, genera  # noqa: E402


def persone_trovate(testo):
    base = etichette.trova(testo) + nomi.trova(testo)
    tutte = base + propagazione.applica(testo, base)
    possibili = nomi.possibili(testo, tutte)
    persone = [e for e in tutte + possibili if e.tipo == Tipo.PERSONA]
    mascherate = [e for e in persone if e.azione == Azione.MASCHERA]
    segnalate = [e for e in persone if e.azione == Azione.SEGNALA]
    return mascherate, segnalate


def coperto(testo, inizio, fine, persone):
    caratteri = set()
    for e in persone:
        caratteri.update(range(max(inizio, e.inizio), min(fine, e.fine)))
    return all(i in caratteri or testo[i] == " " for i in range(inizio, fine))


def misura(quanti=300, seme=7):
    totali, mascherati, visti = Counter(), Counter(), Counter()
    falsi_mascherati = falsi_segnalati = 0
    mancati = []
    for documento in genera(quanti, seme):
        mascherate, segnalate = persone_trovate(documento.testo)
        for (inizio, fine), categoria in zip(documento.nomi, documento.categorie, strict=True):
            totali[categoria] += 1
            if coperto(documento.testo, inizio, fine, mascherate):
                mascherati[categoria] += 1
                visti[categoria] += 1
            elif coperto(documento.testo, inizio, fine, mascherate + segnalate):
                visti[categoria] += 1
            else:
                mancati.append((categoria, documento.testo[inizio:fine], documento.testo))
        for e in mascherate:
            falsi_mascherati += not any(e.inizio < b and a < e.fine for a, b in documento.nomi)
        for e in segnalate:
            falsi_segnalati += not any(e.inizio < b and a < e.fine for a, b in documento.nomi)
    return totali, mascherati, visti, falsi_mascherati, falsi_segnalati, mancati


if __name__ == "__main__":
    quanti = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seme = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    totali, mascherati, visti, falsi_m, falsi_s, mancati = misura(quanti, seme)
    print(f"{'categoria':22} {'nomi':>5} {'mascherati':>11} {'+ segnalati':>12}")
    for categoria in CATEGORIE:
        n = totali[categoria]
        if n:
            quota_m, quota_v = mascherati[categoria] / n, visti[categoria] / n
            print(f"{categoria:22} {n:5} {quota_m:10.1%} {quota_v:11.1%}")
    n = sum(totali.values())
    print(
        f"{'totale':22} {n:5} {sum(mascherati.values()) / n:10.1%} {sum(visti.values()) / n:11.1%}"
    )
    print(f"falsi positivi: mascherati {falsi_m}, segnalati {falsi_s}")
    for categoria, nome, testo in mancati[:15]:
        print(f"  mancato [{categoria}] {nome!r} | {testo}")
