"""Il motore: dal testo ai dati trovati (`analizza`) e dai dati al testo pseudonimizzato
(`applica`). L'interfaccia e la riga di comando usano solo queste funzioni.

Tutto avviene in memoria: nessuna connessione, nessun file scritto.
"""

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from anonimizzatore import __version__, elenchi_utente, pseudonimi
from anonimizzatore.elenchi_utente import ElenchiUtente
from anonimizzatore.estrazione import estrai
from anonimizzatore.rilevamento import (
    etichette,
    nomi,
    propagazione,
    regole,
    risoluzione,
    sensibili,
    vicinanza,
)
from anonimizzatore.rilevamento.etichette import fine_persona
from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo

NOTA_PER_AI = (
    "Nota: i segnaposto tra parentesi quadre, come [PERSONA_1], sostituiscono dati personali "
    "rimossi. Lo stesso segnaposto indica sempre la stessa persona o lo stesso dato."
)


@dataclass(frozen=True)
class Dato:
    entita: Entita
    segnaposto: str  # "" per i dati solo segnalati


@dataclass(frozen=True)
class Analisi:
    testo: str
    dati: tuple[Dato, ...]  # in ordine di posizione, senza sovrapposizioni
    avvisi: tuple[str, ...] = ()

    @property
    def mascherati(self) -> list[Dato]:
        return [d for d in self.dati if d.entita.azione == Azione.MASCHERA]

    @property
    def segnalati(self) -> list[Dato]:
        return [d for d in self.dati if d.entita.azione == Azione.SEGNALA]


def analizza(
    testo: str, avvisi: tuple[str, ...] = (), elenchi: ElenchiUtente | None = None
) -> Analisi:
    elenchi = elenchi_utente.carica() if elenchi is None else elenchi
    entita = [
        *regole.trova(testo),
        *etichette.trova(testo),
        *nomi.trova(testo),
        *_sempre_da_mascherare(testo, elenchi.sempre),
    ]
    entita += propagazione.applica(testo, entita)
    # Dopo la propagazione tutte le persone sono note: si decide di chi sono P.IVA e indirizzi.
    entita = vicinanza.applica(testo, entita)
    entita += _mai_da_mascherare(testo, elenchi.mai)
    entita += sensibili.trova(testo, elenchi.sensibili)
    entita += nomi.possibili(testo, entita)  # rete di sicurezza, per ultima
    scelte = risoluzione.risolvi(entita)
    segnaposto = pseudonimi.assegna(scelte)
    return Analisi(testo, tuple(map(Dato, scelte, segnaposto)), tuple(avvisi))


def analizza_file(percorso: str | Path, elenchi: ElenchiUtente | None = None) -> Analisi:
    estratto = estrai(percorso)
    return analizza(estratto.testo, estratto.avvisi, elenchi)


def applica(analisi: Analisi, nota_per_ai: bool = True) -> str:
    parti, posizione = [], 0
    for dato in analisi.mascherati:
        parti += [analisi.testo[posizione : dato.entita.inizio], dato.segnaposto]
        posizione = dato.entita.fine
    parti.append(analisi.testo[posizione:])
    risultato = "".join(parti)
    return f"{NOTA_PER_AI}\n\n{risultato}" if nota_per_ai else risultato


def legenda(analisi: Analisi) -> list[tuple[str, str]]:
    """Segnaposto e valore originale, una riga per valore. Solo per l'utente, mai per l'AI."""
    righe = dict.fromkeys((d.segnaposto, d.entita.valore) for d in analisi.mascherati)
    return list(righe)


def riepilogo(analisi: Analisi) -> dict:
    """Conteggi e posizioni, senza nessun valore originale: si può salvare o mostrare."""
    return {
        "versione": __version__,
        "mascherati": dict(Counter(str(d.entita.tipo) for d in analisi.mascherati)),
        "segnalati": dict(Counter(str(d.entita.tipo) for d in analisi.segnalati)),
        "avvisi": list(analisi.avvisi),
        "dati": [
            {
                "inizio": d.entita.inizio,
                "fine": d.entita.fine,
                "tipo": str(d.entita.tipo),
                "azione": str(d.entita.azione),
                "fonte": d.entita.fonte,
                "segnaposto": d.segnaposto,
            }
            for d in analisi.dati
        ],
    }


def _occorrenze(testo: str, voce: str) -> list[re.Match[str]]:
    parole = r"\s+".join(map(re.escape, voce.split()))
    return list(re.finditer(rf"(?<![\w]){parole}(?![\w])", testo, re.IGNORECASE))


def _sempre_da_mascherare(testo: str, voci: tuple[str, ...]) -> list[Entita]:
    trovate = []
    for voce in voci:
        # Una voce che sembra un nome ("Rossi Mario") è una persona, il resto un dato generico.
        tipo = Tipo.PERSONA if fine_persona(voce, 0, len(voce)) == (0, len(voce)) else Tipo.DATO
        for m in _occorrenze(testo, voce):
            trovate.append(Entita(m.start(), m.end(), tipo, m[0], "utente", Priorita.UTENTE))
    return trovate


def _mai_da_mascherare(testo: str, voci: tuple[str, ...]) -> list[Entita]:
    return [
        Entita(m.start(), m.end(), Tipo.DATO, m[0], "utente", Priorita.UTENTE, Azione.ESCLUDI)
        for voce in voci
        for m in _occorrenze(testo, voce)
    ]
