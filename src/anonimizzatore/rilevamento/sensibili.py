"""Parole che indicano dati sensibili (art. 9 GDPR) o giudiziari (art. 10): solo segnalate.

L'elenco base sta in `risorse/parole_sensibili.yaml`; l'utente ne aggiunge altre nei suoi
elenchi personali. Se in revisione l'utente decide di mascherare, `con_dettaglio` allarga
l'entità alla parola e al suo dettaglio ("malattia dal 3 al 10 marzo").
"""

import re
from dataclasses import replace
from functools import cache
from importlib.resources import files

import yaml

from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo

_FONTE = "sensibili"
# Il dettaglio va fino alla virgola, al punto o all'a capo successivi, al massimo 8 parole.
_DETTAGLIO = re.compile(r"(?:[ \t]+[^\s,.;:\n]+){0,8}")


def espressione(voce: str) -> re.Pattern[str]:
    """Da una voce dell'elenco ("trattenut* sindacal*") all'espressione regolare."""
    parole = [
        re.escape(p[:-1]) + r"[\w]*" if p.endswith("*") else re.escape(p) for p in voce.split()
    ]
    corpo = r"\s+".join(parole)
    flag = 0 if voce.isupper() else re.IGNORECASE  # le sigle si cercano così come sono
    return re.compile(rf"(?<![\w]){corpo}(?![\w])", flag)


@cache
def _elenco_base() -> tuple[tuple[Tipo, re.Pattern[str]], ...]:
    testo = files("anonimizzatore.risorse").joinpath("parole_sensibili.yaml").read_text("utf-8")
    dati = yaml.safe_load(testo)
    return tuple(
        (Tipo(categoria), espressione(v)) for categoria, voci in dati.items() for v in voci
    )


def trova(testo: str, parole_utente: tuple[str, ...] = ()) -> list[Entita]:
    voci = [*_elenco_base(), *((Tipo.DATO_SENSIBILE, espressione(p)) for p in parole_utente)]
    trovate: dict[tuple[int, int], Entita] = {}
    for tipo, ricerca in voci:
        for m in ricerca.finditer(testo):
            entita = Entita(
                m.start(),
                m.end(),
                tipo,
                m[0],
                _FONTE,
                Priorita.SEGNALAZIONE,
                Azione.SEGNALA,
                nota=_nota(tipo),
            )
            trovate.setdefault((m.start(), m.end()), entita)
    return sorted(trovate.values(), key=lambda e: e.inizio)


def con_dettaglio(testo: str, entita: Entita) -> Entita:
    """L'entità da mascherare allargata al dettaglio che segue la parola."""
    fine = _DETTAGLIO.match(testo, entita.fine).end()
    return replace(entita, fine=fine, valore=testo[entita.inizio : fine], azione=Azione.MASCHERA)


def _nota(tipo: Tipo) -> str:
    if tipo == Tipo.DATO_GIUDIZIARIO:
        return "Possibile dato giudiziario (art. 10 GDPR): decidi se mascherarlo."
    if tipo == Tipo.DATO_SENSIBILE:
        return "Parola sensibile dei tuoi elenchi: decidi se mascherarla."
    return "Possibile dato sensibile (art. 9 GDPR): decidi se mascherarlo."
