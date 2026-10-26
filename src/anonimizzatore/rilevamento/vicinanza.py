"""Decide se una partita IVA o un indirizzo appartengono a una persona.

Le regole li trovano con l'azione "segnala". Diventano "maschera" quando sono vicini a una
persona riconosciuta o a parole come "residente"; restano "segnala" quando il contesto è quello
di un'azienda ("con sede in", "S.r.l."). Va eseguita dopo aver trovato tutte le persone.
"""

import re
from dataclasses import replace

from anonimizzatore.rilevamento.modelli import Azione, Entita, Tipo

FINESTRA = 80  # caratteri prima e dopo
_FINESTRA_SEDE = 40

_CONTESTO_PERSONA = re.compile(
    r"(?i)(?<![\w])(?:residente|residenza|domiciliat[oa]|domicilio|abitante|abitazione"
    r"|ditta\s+individuale|libero\s+professionista|professionista)(?![\w])"
)
_CONTESTO_SEDE = re.compile(
    r"(?i)(?<![\w])(?:con\s+sede|sede\s+(?:legale|operativa|amministrativa|sociale)"
    r"|s\.r\.l\.?|srl|s\.p\.a\.?|spa|s\.n\.c\.?|snc|s\.a\.s\.?|sas)(?![\w])"
)
_DA_DECIDERE = {Tipo.PARTITA_IVA, Tipo.INDIRIZZO}


def applica(testo: str, entita: list[Entita]) -> list[Entita]:
    persone = [e for e in entita if e.tipo == Tipo.PERSONA and e.azione == Azione.MASCHERA]
    return [
        replace(e, azione=Azione.MASCHERA)
        if e.tipo in _DA_DECIDERE and e.azione == Azione.SEGNALA and _di_persona(testo, e, persone)
        else e
        for e in entita
    ]


def _di_persona(testo: str, dato: Entita, persone: list[Entita]) -> bool:
    inizio_riga = testo.rfind("\n", 0, dato.inizio) + 1
    # Un'azienda prima del dato, nella stessa riga o poco prima, vince su tutto: è la riga
    # d'intestazione di una busta paga o la sede di una società.
    inizio_sede = min(max(inizio_riga, dato.inizio - FINESTRA), dato.inizio - _FINESTRA_SEDE)
    if _CONTESTO_SEDE.search(testo, max(0, inizio_sede), dato.inizio):
        return False
    if _CONTESTO_PERSONA.search(testo, max(0, dato.inizio - FINESTRA), dato.inizio):
        return True
    fine_riga = testo.find("\n", dato.fine)
    fine_riga = len(testo) if fine_riga == -1 else fine_riga
    da, a = min(inizio_riga, dato.inizio - FINESTRA), max(fine_riga, dato.fine + FINESTRA)
    return any(p.fine > da and p.inizio < a for p in persone)
