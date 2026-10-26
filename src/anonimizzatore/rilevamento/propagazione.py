"""La stessa persona in tutto il testo.

Una persona trovata una volta ("Mario Rossi") si cerca ovunque: "il sig. Rossi", "ROSSI", "Mario"
da solo. Contano solo le occorrenze con l'iniziale maiuscola, per non toccare "rosa" in "lista
rosa". Ogni occorrenza porta in `persona` la chiave della persona, così in M4 riceve lo stesso
pseudonimo.
"""

import re

from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo
from anonimizzatore.risorse import elenco

_MIN_LETTERE = 3
_PARTICELLE = frozenset(
    {"de", "di", "da", "del", "della", "dal", "dalla", "la", "lo", "van", "von"}
)
_PAROLE = re.compile(r"[A-Za-zÀ-ÿ'’-]+")
# "in Padova", "di Ferrara": dopo una preposizione di luogo un cognome-città è la città.
_DOPO_PREPOSIZIONE = re.compile(r"(?i)(?<![\w])(?:a|in|di|da|per|presso|verso)\s+$")


def chiave_persona(valore: str) -> frozenset[str]:
    """Le parole che identificano una persona, senza maiuscole, titoli e particelle.

    Una parola comune resta se è anche un cognome: in "Zeno Gentile" conta anche "gentile".
    """
    comuni, cognomi = elenco("parole_comuni.txt"), elenco("cognomi.txt")
    return frozenset(
        p
        for p in (parola.casefold() for parola in _PAROLE.findall(valore))
        if len(p) >= _MIN_LETTERE and (p not in comuni or p in cognomi) and p not in _PARTICELLE
    )


def testo_chiave(chiave: frozenset[str]) -> str:
    return " ".join(sorted(chiave))


def chiave_di(entita: Entita) -> frozenset[str]:
    """La chiave della persona: quella indicata (propagazione, Cognome + Nome) o dal valore."""
    return chiave_persona(entita.persona or entita.valore)


def applica(testo: str, entita: list[Entita]) -> list[Entita]:
    """Nuove entità per le altre occorrenze delle persone già trovate."""
    persone = [e for e in entita if e.tipo == Tipo.PERSONA and e.azione == Azione.MASCHERA]
    chiavi = {chiave_di(p) for p in persone} - {frozenset()}
    # Una chiave contenuta in un'altra è la stessa persona scritta in modo più breve ("Rossi").
    complete = [c for c in chiavi if not any(c < altra for altra in chiavi)]
    if not complete:
        return []

    parole = {p for c in complete for p in c}
    ricerca = re.compile(
        r"(?<![\w'’])(?:"
        + "|".join(re.escape(p) for p in sorted(parole, key=len, reverse=True))
        + r")(?![\w'’])",
        re.IGNORECASE,
    )
    # Un "possibile nome" segnalato non blocca la propagazione: se è una persona nota va
    # mascherato. Gli altri dati segnalati (un indirizzo, una P.IVA) invece sì.
    occupati = [
        (e.inizio, e.fine)
        for e in entita
        if not (e.tipo == Tipo.PERSONA and e.azione == Azione.SEGNALA)
    ]
    luoghi = elenco("luoghi.txt")
    occorrenze = [
        m
        for m in ricerca.finditer(testo)
        if m[0][0].isupper()
        and not any(a < m.end() and m.start() < b for a, b in occupati)
        and not (
            m[0].casefold() in luoghi
            and _DOPO_PREPOSIZIONE.search(testo[max(0, m.start() - 12) : m.start()])
        )
    ]

    nuove = []
    for gruppo in _unisci_vicine(testo, occorrenze):
        inizio, fine = gruppo[0].start(), gruppo[-1].end()
        candidate = [c for c in complete if chiave_persona(testo[inizio:fine]) <= c]
        if not candidate and len(gruppo) > 1:
            # Parole vicine ma di persone diverse: si trattano una per una.
            for m in gruppo:
                nuove.extend(_nuova(testo, m.start(), m.end(), complete, persone))
            continue
        nuove.extend(_nuova(testo, inizio, fine, complete, persone))
    return nuove


def _nuova(
    testo: str, inizio: int, fine: int, complete: list[frozenset[str]], persone: list[Entita]
) -> list[Entita]:
    candidate = [c for c in complete if chiave_persona(testo[inizio:fine]) <= c]
    if not candidate:
        return []
    scelta = min(candidate, key=lambda c: _distanza(inizio, c, persone))
    nota = ""
    if len(candidate) > 1:
        nomi = " o ".join(sorted(testo_chiave(c) for c in candidate))
        nota = f"Omonimia: potrebbe essere {nomi}."
    return [
        Entita(
            inizio,
            fine,
            Tipo.PERSONA,
            testo[inizio:fine],
            "propagazione",
            Priorita.PROPAGAZIONE,
            persona=testo_chiave(scelta),
            nota=nota,
        )
    ]


def _unisci_vicine(testo: str, occorrenze: list[re.Match[str]]) -> list[list[re.Match[str]]]:
    """Raggruppa le parole separate da un solo spazio: "Mario" + "Rossi" → "Mario Rossi"."""
    gruppi: list[list[re.Match[str]]] = []
    for m in occorrenze:
        if gruppi and testo[gruppi[-1][-1].end() : m.start()] == " ":
            gruppi[-1].append(m)
        else:
            gruppi.append([m])
    return gruppi


def _distanza(posizione: int, chiave: frozenset[str], persone: list[Entita]) -> int:
    """Distanza dalla menzione più vicina di quella persona: decide le omonimie."""
    return min(
        (abs(p.inizio - posizione) for p in persone if chiave_di(p) <= chiave),
        default=10**9,
    )
