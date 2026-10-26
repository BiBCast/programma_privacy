"""Dati che seguono un'etichetta: "Cognome e nome: …", "Matricola …", "Sig. …", "nato il …".

Il valore va dall'etichetta fino al primo separatore di colonna (due spazi, tabulazione, `|` o
a capo), così funziona anche con le buste paga impaginate a colonne. Ogni tipo ha una
validazione che accorcia o scarta il valore.
"""

import re
from collections.abc import Callable
from dataclasses import replace

from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo
from anonimizzatore.rilevamento.propagazione import chiave_persona, testo_chiave
from anonimizzatore.rilevamento.regole import DATA, LUOGO, taglia_coda
from anonimizzatore.risorse import elenco

_FONTE = "etichetta"

_VALORE = r"[ \t]*[:.\-–]?[ \t]*(?P<v>[^\s|](?:[^\n\t|]*?[^\s|])?)(?=[ ]*\||[ ]{2,}|\t|\n|$)"
_ETICHETTE: list[tuple[str, Tipo, Azione]] = [
    (
        r"cognome\s+e\s+nome|nome\s+e\s+cognome|cognome\s+nome|nominativo|cognome|nome"
        r"|dipendente|lavorat(?:ore|rice)|intestatari[oa]|beneficiari[oa]|richiedente",
        Tipo.PERSONA,
        Azione.MASCHERA,
    ),
    (
        r"n\.\s?matricola|matricola|matr\.|codice\s+dipendente|cod\.\s?dip\.",
        Tipo.MATRICOLA,
        Azione.MASCHERA,
    ),
    (
        r"data\s+di\s+nascita|data\s+nascita|nat[oa](?:/[ao])?\s+il",
        Tipo.DATA_NASCITA,
        Azione.MASCHERA,
    ),
    (
        r"luogo\s+di\s+nascita|luogo\s+nascita|comune\s+di\s+nascita",
        Tipo.LUOGO_NASCITA,
        Azione.MASCHERA,
    ),
    (
        r"residente\s+(?:in|a)|domiciliat[oa]\s+(?:in|a)|residenza|domicilio",
        Tipo.INDIRIZZO,
        Azione.MASCHERA,
    ),
    # "Indirizzo" può essere quello di un'azienda: decide la vicinanza a una persona.
    (r"indirizzo", Tipo.INDIRIZZO, Azione.SEGNALA),
    (r"tel\.|tel|telefono|cell\.|cell|cellulare|mobile", Tipo.TELEFONO, Azione.MASCHERA),
]
_COMPILATE = [
    (re.compile(rf"(?<![\w])(?P<etichetta>(?i:{etichetta}))(?![A-Za-zÀ-ÿ]){_VALORE}"), tipo, azione)
    for etichetta, tipo, azione in _ETICHETTE
]
# "Cognome: Rossi" e "Nome: Mario" così vicini sono la stessa persona.
_DISTANZA_COGNOME_NOME = 80

_TITOLI = (
    r"sig\.(?:ra|na)?|signor[ae]?|sigg\.|dott\.(?:ssa)?|dr\.|avv\.(?:to)?|ing\.|geom\.|rag\."
    r"|prof\.(?:ssa)?|arch\."
)
_CORTESIA = r"(?:(?i:egr\.|egregio|gent\.(?:mo|ma|ile)?|gentile|spett\.(?:le)?)\s*)?"
# Solo le parole che possono formare un nome, così non si ingloba il titolo successivo.
_NOMI_DOPO = (
    r"(?P<v>[A-ZÀ-Ý][\w'’.-]*"
    r"(?: (?:[A-ZÀ-Ý][\w'’.-]*|(?:de|di|da|del|della|dal|dalla|la|lo|van|von)(?![\w'’])"
    r"|d['’]\S+)){0,4})"
)
_RUOLI_ATTI = (
    r"(?:il|la|l['’]|lo)\s*(?:ricorrente|resistente|convenut[oa]|attore|attrice|appellante"
    r"|appellat[oa]|testimone|teste|dichiarante|esponente|istante|imputat[oa]|indagat[oa]"
    r"|creditore|creditrice|debitore|debitrice|locatore|locatrice|conduttore|conduttrice"
    r"|comodante|comodatari[oa]|mandante|mandatari[oa]|delegat[oa]|delegante|tutore|tutrice"
    r"|curatore|curatrice|erede|defunt[oa]|de\s+cuius)"
    r"|in\s+persona\s+(?:del|della|di)(?:\s+(?:suo\s+)?(?:legale\s+rappresentante|amministratore"
    r"(?:\s+unico)?|titolare|procuratore))?(?:\s+pro\s+tempore)?"
    r"|nella\s+persona\s+(?:del|della|di)(?:\s+(?:legale\s+rappresentante|amministratore"
    r"(?:\s+unico)?))?"
    r"|(?:assistit[oa]|rappresentat[oa](?:\s+e\s+difes[oa])?|difes[oa])\s+da(?:ll['’]\s*avv\.?)?"
    r"|(?:propost[oa]|promoss[oa]|presentat[oa])\s+da"
    r"|conviene\s+in\s+giudizio|nei\s+confronti\s+di|contro"
    r"|testimone\s*:|teste\s*:"
)
_PERSONE_SENZA_DUEPUNTI = [
    re.compile(rf"(?<![\w]){_CORTESIA}(?i:{_TITOLI})\s*{_NOMI_DOPO}"),
    re.compile(
        r"(?<![\w])(?i:(?:il|la|io)\s+sottoscritt[oa](?:/[ao])?|i\s+sottoscritti)\s*,?\s*"
        rf"(?:(?i:{_TITOLI})\s*)?{_NOMI_DOPO}"
    ),
    # Ruoli e formule degli atti dopo cui viene un nome, anche se nessun elenco lo conosce.
    re.compile(rf"(?<![\w])(?i:{_RUOLI_ATTI})\s*,?\s*(?:(?i:{_TITOLI})\s*)?{_NOMI_DOPO}"),
]

# --- Validazioni ------------------------------------------------------------------------------

_PAROLA_NOME = re.compile(r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]*\.?")
_PARTICELLE = frozenset({
    "de", "di", "da", "del", "della", "dal", "dalla", "la", "lo", "le", "van", "von", "der",
    "d'", "dell'",
})  # fmt: skip
_SOCIETA = re.compile(
    r"(?i)(?<![\w])(?:s\.?r\.?l\.?s?|s\.?p\.?a\.?|s\.?n\.?c\.?|s\.?a\.?s\.?|onlus|coop\.?"
    r"|cooperativa|ltd|gmbh|inc\.?)(?![\w])"
)
_STOP_INDIRIZZO = re.compile(
    r"(?i)[,;]?\s+(?:c\.\s?f\.|cod(?:ice)?\.?\s+fisc|tel\b|cell\b|e-?mail|pec\b|p\.?\s?iva|nat[oa]\b"
    r"|in\s+qualit[àa]|di\s+seguito)|;"
)
_CODA_LUOGO = frozenset({"il", "in", "e", "ed", "residente", "domiciliato", "domiciliata"})

Intervallo = tuple[int, int] | None


def fine_persona(testo: str, inizio: int, fine: int) -> Intervallo:
    """Tiene le parole iniziali che possono formare un nome; scarta i valori che non lo sono."""
    valore = testo[inizio:fine]
    if _SOCIETA.search(valore):
        return None
    comuni = elenco("parole_comuni.txt")
    parole = []
    for parola in re.finditer(r"\S+", valore):
        pulita = _parola(parola)
        nome = _PAROLA_NOME.fullmatch(pulita)
        particella = pulita.casefold() in _PARTICELLE and parole
        if not (nome or particella):
            break
        # "OLUWASEUN MOKOENA DICHIARA DI AVER": dopo due parole del nome, il verbo lo chiude.
        comune = len(parole) >= 2 and not particella and pulita.casefold() in comuni
        if comune and not _e_cognome(pulita, _parola(parole[-1])):
            break
        parole.append(parola)
        if pulita != parola[0] or len(parole) == 5:
            break  # una virgola o un punto finale chiudono il nome
    while parole and _parola(parole[-1]).casefold() in comuni | _PARTICELLE:
        if len(parole) >= 2 and _e_cognome(_parola(parole[-1]), _parola(parole[-2])):
            break
        parole.pop()
    if not parole or all(_parola(p).casefold() in comuni | _PARTICELLE for p in parole):
        return None
    return inizio, inizio + parole[-1].start() + len(_parola(parole[-1]))


def _e_cognome(parola: str, precedente: str) -> bool:
    """Una parola comune che è anche un cognome, dopo un nome: "Anna Gentile", "Xavier Gentile".

    Non vale per le altre parole comuni: in "ROSSI MARIO DICHIARA" il verbo non è un cognome.
    """
    if not parola[0].isupper() or parola.casefold() in _PARTICELLE:
        return False
    return parola.casefold() in elenco("cognomi.txt") and precedente.casefold() not in elenco(
        "parole_comuni.txt"
    )


def _parola(trovata: re.Match[str]) -> str:
    """La parola senza la punteggiatura finale; il punto resta solo nelle iniziali ("M.")."""
    parola = trovata[0].rstrip(",;:")
    return parola[:-1] if parola.endswith(".") and len(parola) > 2 else parola


def _matricola(testo: str, inizio: int, fine: int) -> Intervallo:
    m = re.match(r"(?:n\.?\s*)?([A-Za-z0-9][A-Za-z0-9/-]*)", testo[inizio:fine])
    if m and any(c.isdigit() for c in m[1]):
        return inizio + m.start(1), inizio + m.end(1)
    return None


def _data(testo: str, inizio: int, fine: int) -> Intervallo:
    m = re.match(DATA, testo[inizio:fine])
    return (inizio, inizio + m.end()) if m else None


def _luogo(testo: str, inizio: int, fine: int) -> Intervallo:
    m = re.match(LUOGO, testo[inizio:fine])
    if not m:
        return None
    nuova_fine = taglia_coda(testo, inizio, inizio + m.end(), _CODA_LUOGO)
    return (inizio, nuova_fine) if nuova_fine > inizio else None


def _indirizzo(testo: str, inizio: int, fine: int) -> Intervallo:
    valore = testo[inizio:fine]
    stop = _STOP_INDIRIZZO.search(valore)
    if stop:
        valore = valore[: stop.start()]
    valore = valore.rstrip(" ,.")
    if len(valore) < 3 or not any(c.isalpha() for c in valore):
        return None
    return inizio, inizio + len(valore)


def _telefono(testo: str, inizio: int, fine: int) -> Intervallo:
    m = re.match(r"[+\d][\d ./-]{4,18}\d", testo[inizio:fine])
    if m and sum(c.isdigit() for c in m[0]) >= 6:
        return inizio, inizio + m.end()
    return None


_VALIDAZIONI: dict[Tipo, Callable[[str, int, int], Intervallo]] = {
    Tipo.PERSONA: fine_persona,
    Tipo.MATRICOLA: _matricola,
    Tipo.DATA_NASCITA: _data,
    Tipo.LUOGO_NASCITA: _luogo,
    Tipo.INDIRIZZO: _indirizzo,
    Tipo.TELEFONO: _telefono,
}

# --- Ricerca ----------------------------------------------------------------------------------


def trova(testo: str) -> list[Entita]:
    trovate: dict[tuple[int, int, Tipo], Entita] = {}
    parti: dict[tuple[int, int, Tipo], str] = {}  # entità venute da "Cognome:" o "Nome:"

    def aggiungi(m: re.Match[str], tipo: Tipo, azione: Azione) -> None:
        intervallo = _VALIDAZIONI[tipo](testo, m.start("v"), m.end("v"))
        if intervallo:
            inizio, fine = intervallo
            entita = Entita(
                inizio, fine, tipo, testo[inizio:fine], _FONTE, Priorita.ETICHETTA, azione
            )
            trovate.setdefault((inizio, fine, tipo), entita)
            etichetta = (m.groupdict().get("etichetta") or "").casefold()
            if tipo == Tipo.PERSONA and etichetta in ("cognome", "nome"):
                parti[(inizio, fine, tipo)] = etichetta

    for espressione, tipo, azione in _COMPILATE:
        for m in espressione.finditer(testo):
            aggiungi(m, tipo, azione)
    for espressione in _PERSONE_SENZA_DUEPUNTI:
        for m in espressione.finditer(testo):
            aggiungi(m, Tipo.PERSONA, Azione.MASCHERA)
    _unisci_cognome_e_nome(trovate, parti)
    return sorted(trovate.values(), key=lambda e: (e.inizio, -e.fine))


def _unisci_cognome_e_nome(trovate: dict, parti: dict[tuple[int, int, Tipo], str]) -> None:
    """Dà a "Cognome: Rossi" e al "Nome: Mario" più vicino la stessa chiave di persona."""
    cognomi = [trovate[k] for k, parte in parti.items() if parte == "cognome"]
    nomi = [trovate[k] for k, parte in parti.items() if parte == "nome"]
    for cognome in sorted(cognomi, key=lambda e: e.inizio):
        vicini = [n for n in nomi if abs(n.inizio - cognome.inizio) <= _DISTANZA_COGNOME_NOME]
        if not vicini:
            continue
        nome = min(vicini, key=lambda n: abs(n.inizio - cognome.inizio))
        nomi.remove(nome)
        chiave = testo_chiave(chiave_persona(f"{nome.valore} {cognome.valore}"))
        for e in (cognome, nome):
            trovate[(e.inizio, e.fine, e.tipo)] = replace(e, persona=chiave)
