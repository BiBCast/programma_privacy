"""Segnaposto coerenti: la stessa persona o lo stesso codice ha sempre lo stesso segnaposto.

"Mario Rossi", "ROSSI MARIO" e "il sig. Rossi" diventano tutti [PERSONA_1]; lo stesso IBAN
scritto con o senza spazi diventa sempre [IBAN_1]. I numeri seguono l'ordine di prima comparsa.
"""

import re
from collections.abc import Hashable

from anonimizzatore.rilevamento.modelli import Azione, Entita, Tipo
from anonimizzatore.rilevamento.propagazione import chiave_di

_CODICI = {Tipo.CODICE_FISCALE, Tipo.IBAN, Tipo.PARTITA_IVA, Tipo.DOCUMENTO, Tipo.MATRICOLA}


def chiave(entita: Entita) -> Hashable:
    """Il valore normalizzato: due entità con la stessa chiave sono lo stesso dato."""
    valore = entita.valore
    if entita.tipo == Tipo.PERSONA:
        return chiave_di(entita) or frozenset({valore.casefold()})
    if entita.tipo in _CODICI:
        return re.sub(r"[\s./-]", "", valore).upper()
    if entita.tipo == Tipo.TELEFONO:
        cifre = re.sub(r"\D", "", valore)
        return re.sub(r"^(?:0039|39)(?=\d{9,10}$)", "", cifre)
    if entita.tipo == Tipo.EMAIL:
        return valore.lower()
    if entita.tipo == Tipo.DATA_NASCITA:
        # "01/03/1975" e "1.3.1975" sono la stessa data; "1 marzo 1975" resta distinta.
        return tuple(
            int(p) if p.isdigit() else p.casefold() for p in re.findall(r"\d+|\w+", valore)
        )
    return " ".join(valore.casefold().split())


def assegna(entita: list[Entita]) -> list[str]:
    """Il segnaposto di ogni entità da mascherare ("" per le altre), nello stesso ordine."""
    da_mascherare = [e for e in entita if e.azione == Azione.MASCHERA]
    canoniche = _chiavi_canoniche(da_mascherare)

    numeri: dict[tuple[Tipo, Hashable], int] = {}
    contatori: dict[Tipo, int] = {}
    for e in sorted(da_mascherare, key=lambda e: e.inizio):
        identita = (e.tipo, canoniche[e])
        if identita not in numeri:
            contatori[e.tipo] = contatori.get(e.tipo, 0) + 1
            numeri[identita] = contatori[e.tipo]
    return [
        f"[{e.tipo}_{numeri[(e.tipo, canoniche[e])]}]" if e.azione == Azione.MASCHERA else ""
        for e in entita
    ]


def _chiavi_canoniche(entita: list[Entita]) -> dict[Entita, Hashable]:
    """Chiave di ogni entità; per le persone, la forma più completa ("Rossi" → "mario rossi")."""
    canoniche: dict[Entita, Hashable] = {e: chiave(e) for e in entita}
    persone = [e for e in entita if e.tipo == Tipo.PERSONA]
    chiavi = {canoniche[e] for e in persone}
    complete = [c for c in chiavi if not any(c < altra for altra in chiavi)]
    for e in persone:
        k = canoniche[e]
        if k in complete:
            continue
        candidate = [c for c in complete if k < c]
        if len(candidate) == 1:
            canoniche[e] = candidate[0]
        elif candidate:
            # Omonimia ("Rossi" con Mario e Anna Rossi): la persona citata più vicino.
            canoniche[e] = min(
                candidate,
                key=lambda c: min(abs(p.inizio - e.inizio) for p in persone if canoniche[p] == c),
            )
    return canoniche
