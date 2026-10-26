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
    testo: str,
    avvisi: tuple[str, ...] = (),
    elenchi: ElenchiUtente | None = None,
    incerti: tuple[tuple[int, int], ...] = (),
    letto_con_ocr: bool = False,
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
    entita += _codici_sulla_riga_della_persona(testo, entita)
    entita += _mai_da_mascherare(testo, elenchi.mai)
    entita += sensibili.trova(testo, elenchi.sensibili)
    entita += nomi.possibili(testo, entita)  # rete di sicurezza
    entita += _incerte(testo, incerti)  # parole lette male dall'OCR, per ultime
    if letto_con_ocr:
        entita += _iniziale_letta_male(testo, entita)
    scelte = risoluzione.risolvi(entita)
    segnaposto = pseudonimi.assegna(scelte)
    return Analisi(testo, tuple(map(Dato, scelte, segnaposto)), tuple(avvisi))


def analizza_file(percorso: str | Path, elenchi: ElenchiUtente | None = None) -> Analisi:
    estratto = estrai(percorso)
    return analizza(
        estratto.testo, estratto.avvisi, elenchi, estratto.incerti, estratto.letto_con_ocr
    )


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


def _incerte(testo: str, incerti: tuple[tuple[int, int], ...]) -> list[Entita]:
    """Parole lette con poca sicurezza che potrebbero essere un nome o un codice: da valutare."""
    trovate = []
    for inizio, fine in incerti:
        parola = testo[inizio:fine]
        if len(parola) >= 3 and (parola[0].isupper() or any(c.isdigit() for c in parola)):
            trovate.append(
                Entita(
                    inizio,
                    fine,
                    Tipo.DATO,
                    parola,
                    "ocr",
                    Priorita.SEGNALAZIONE,
                    Azione.SEGNALA,
                    nota="Letto con poca sicurezza dalla scansione: controlla che non sia un dato.",
                )
            )
    return trovate


_NUMERO_ISOLATO = re.compile(r"(?<![\w.,/-])\d{4,10}(?![\w.,/-])")


def _codici_sulla_riga_della_persona(testo: str, entita: list[Entita]) -> list[Entita]:
    """Nelle buste paga le etichette stanno in una riga e i valori in un'altra:
    "0004321   ROSSI MARIO   RSSMRA80A01H501U 007788". Su una riga con un nome mascherato
    e un codice fiscale, i numeri isolati di 4–10 cifre sono codice dipendente e matricola.
    """
    occupati = [(e.inizio, e.fine) for e in entita]
    trovati = []
    inizio_riga = 0
    for riga in testo.split("\n"):
        fine_riga = inizio_riga + len(riga)
        qui = [e for e in entita if inizio_riga <= e.inizio and e.fine <= fine_riga]
        persona = any(e.tipo == Tipo.PERSONA and e.azione == Azione.MASCHERA for e in qui)
        if persona and any(e.tipo == Tipo.CODICE_FISCALE for e in qui):
            for m in _NUMERO_ISOLATO.finditer(riga):
                inizio, fine = inizio_riga + m.start(), inizio_riga + m.end()
                if not any(a < fine and inizio < b for a, b in occupati):
                    trovati.append(
                        Entita(inizio, fine, Tipo.MATRICOLA, m[0], "riga", Priorita.REGOLA)
                    )
        inizio_riga = fine_riga + 1
    return trovati


_INIZIALE_L = re.compile(r"l[a-zà-ÿ'’-]{2,}")


def _iniziale_letta_male(testo: str, entita: list[Entita]) -> list[Entita]:
    """L'OCR legge spesso la I maiuscola come "l": "loana [PERSONA_1]" era "Ioana Mancini".

    Una parola che inizia per "l", attaccata a una persona mascherata, va tra i dati da
    valutare: potrebbe essere il resto del nome.
    """
    persone = [e for e in entita if e.tipo == Tipo.PERSONA and e.azione == Azione.MASCHERA]
    trovate = {}
    for persona in persone:
        prima = re.search(
            r"(?<![\w'’])(\S+) $", testo[max(0, persona.inizio - 40) : persona.inizio]
        )
        dopo = re.match(r" (\S+)", testo[persona.fine : persona.fine + 40])
        vicine = []
        if prima:
            vicine.append((persona.inizio - 1 - len(prima[1]), prima[1]))
        if dopo:
            vicine.append((persona.fine + 1, dopo[1].rstrip(".,;:")))
        for inizio, parola in vicine:
            if _INIZIALE_L.fullmatch(parola):
                trovate[inizio] = Entita(
                    inizio,
                    inizio + len(parola),
                    Tipo.PERSONA,
                    parola,
                    "ocr",
                    Priorita.SEGNALAZIONE,
                    Azione.SEGNALA,
                    nota="Forse parte del nome letta male dalla scansione (I letta come l).",
                )
    return list(trovate.values())


def _mai_da_mascherare(testo: str, voci: tuple[str, ...]) -> list[Entita]:
    return [
        Entita(m.start(), m.end(), Tipo.DATO, m[0], "utente", Priorita.UTENTE, Azione.ESCLUDI)
        for voce in voci
        for m in _occorrenze(testo, voce)
    ]
