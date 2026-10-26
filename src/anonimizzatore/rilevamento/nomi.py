"""Nomi di persona nel testo libero: modello spaCy ed elenco dei nomi propri.

Il modello riconosce male i nomi tutti maiuscoli e unisce le colonne delle buste paga. Per
questo lavora su una copia del testo con le maiuscole normalizzate ("ROSSI" → "Rossi") e con le
colonne separate da un a capo. La copia ha la stessa lunghezza, quindi gli offset valgono anche
per il testo originale.
"""

import re
from dataclasses import replace
from functools import cache

from anonimizzatore.rilevamento.etichette import fine_persona
from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo
from anonimizzatore.risorse import elenco

_COMPONENTI_INUTILI = [
    "parser",
    "lemmatizer",
    "morphologizer",
    "attribute_ruler",
    "tagger",
    "senter",
]
# Parole comuni che precedono un nome ma non ne fanno mai parte.
_TITOLI = frozenset({"signor", "signora", "signore", "egregio", "egregia", "caro", "cara"})
_SOCIETA_DOPO = re.compile(
    r"(?i)\s*,?\s*(?:s\.?r\.?l|s\.?p\.?a|s\.?n\.?c|s\.?a\.?s|onlus|coop|ltd|gmbh|inc)(?![\w])"
)
# Parole che aprono il nome di un luogo o di un'insegna: "Via Costa Rossa", "Sala Consiliare",
# "Monte Bianco". Davanti o in testa a una coppia maiuscola, la coppia non è una persona.
_PREFISSI_LUOGO = frozenset({
    "via", "viale", "piazza", "corso", "largo", "vicolo", "strada", "località", "studio",
    "banca", "hotel", "albergo", "ristorante", "bar", "farmacia", "cantina", "villa", "palazzo",
    "teatro", "cinema", "monte", "sala", "porta", "torre", "ponte", "lago", "costa", "riva",
    "rocca", "campo", "colle", "poggio", "piano", "isola", "capo", "punta", "bosco", "fonte",
    "castello", "borgo",
})  # fmt: skip
_PRIMA_DI_UN_LUOGO = re.compile(rf"(?i)(?<![\w])(?:{'|'.join(sorted(_PREFISSI_LUOGO))})\s+$")
# Una riga tutta maiuscola con più parole di così è prosa ("DICHIARA DI AVER RICEVUTO…"):
# le coppie maiuscole che contiene non si segnalano.
_MAX_PAROLE_RIGA_MAIUSCOLA = 5

_TUTTA_MAIUSCOLA = re.compile(r"(?<![\w])[A-ZÀ-Ý]{2,}(?:['’][A-ZÀ-Ý]+)*(?![\w])")
_PEZZO_MAIUSCOLO = re.compile(r"[A-ZÀ-Ý]+")
_COLONNE = re.compile(r"[ \t]{2,}|\t")

# Sequenze di 2–4 parole con l'iniziale maiuscola separate da un solo spazio.
_PAROLA = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+"
_SEQUENZA = re.compile(rf"(?<![\w'’]){_PAROLA}(?: {_PAROLA}){{1,3}}(?![\w])")


@cache
def _modello():
    import spacy

    return spacy.load("it_core_news_md", exclude=_COMPONENTI_INUTILI)


def testo_per_il_modello(testo: str) -> str:
    comuni = elenco("parole_comuni.txt")

    def normalizza(m: re.Match[str]) -> str:
        parola = m[0]
        if parola.casefold() in comuni:
            return parola  # le sigle restano maiuscole: INPS non diventa "Inps"
        return _PEZZO_MAIUSCOLO.sub(lambda p: p[0][0] + p[0][1:].lower(), parola)

    copia = _TUTTA_MAIUSCOLA.sub(normalizza, testo)
    copia = _COLONNE.sub(lambda m: "\n" + m[0][1:], copia)
    if len(copia) != len(testo):
        # Qualche carattere cambia lunghezza in minuscolo: meglio il testo così com'è.
        return _COLONNE.sub(lambda m: "\n" + m[0][1:], testo)
    return copia


def trova(testo: str) -> list[Entita]:
    """Persone trovate dal modello e dall'elenco dei nomi propri."""
    return sorted([*_dal_modello(testo), *_dall_elenco(testo)], key=lambda e: (e.inizio, -e.fine))


def _dal_modello(testo: str) -> list[Entita]:
    copia = testo_per_il_modello(testo)
    trovate = []
    for ent in _modello()(copia).ents:
        if ent.label_ != "PER":
            continue
        inizio, fine = ent.start_char, ent.end_char
        a_capo = copia.find("\n", inizio, fine)
        if a_capo != -1:
            fine = a_capo  # il nome finisce dove inizia la colonna successiva
        entita = _persona(testo, inizio, fine, "ner", Priorita.NER)
        if entita:
            trovate.append(entita)
    return trovate


def _dall_elenco(testo: str) -> list[Entita]:
    nomi_propri = elenco("nomi_propri.txt")
    trovate = []
    for m in _SEQUENZA.finditer(testo):
        parole = m[0].split(" ")
        nome_noto = any(p.casefold() in nomi_propri for p in parole)
        if nome_noto or _coppia_con_cognome(testo, m.start(), parole):
            entita = _persona(testo, m.start(), m.end(), "elenco_nomi", Priorita.ELENCO_NOMI)
            if entita and " " in entita.valore:
                trovate.append(entita)
    return trovate


def _coppia_con_cognome(testo: str, inizio: int, parole: list[str]) -> bool:
    """ "Ngozi Caruso", "VALLE OFELIA": un cognome noto accanto a una parola sconosciuta."""
    if _PRIMA_DI_UN_LUOGO.search(testo[max(0, inizio - 15) : inizio]):
        return False
    cognomi, comuni = elenco("cognomi.txt"), elenco("parole_comuni.txt")
    altre = comuni | elenco("luoghi.txt")
    parole = [p.casefold() for p in parole]
    if len(parole) == 3 and parole[0] in comuni:
        parole = parole[1:]  # "Gentile Zeno Valle": la cortesia davanti non conta
    if len(parole) != 2 or parole[0] in _PREFISSI_LUOGO:
        return False
    prima, seconda = parole
    return (prima in cognomi and seconda not in altre) or (
        seconda in cognomi and prima not in altre
    )


def possibili(testo: str, entita: list[Entita]) -> list[Entita]:
    """Rete di sicurezza: coppie e terne di parole maiuscole che nessuno ha riconosciuto.

    Non si mascherano: vanno nell'elenco "Da valutare" della revisione come possibili nomi.
    Va eseguita per ultima, dopo la propagazione, con tutte le entità già trovate.
    """
    occupati = [(e.inizio, e.fine) for e in entita]
    comuni = elenco("parole_comuni.txt")
    trovate = []
    for m in _SEQUENZA.finditer(testo):
        parole = [p.casefold() for p in m[0].split(" ")]
        if any(a < m.end() and m.start() < b for a, b in occupati):
            continue
        if parole[0] in _PREFISSI_LUOGO or _PRIMA_DI_UN_LUOGO.search(
            testo[max(0, m.start() - 15) : m.start()]
        ):
            continue
        if _SOCIETA_DOPO.match(testo, m.end()):
            continue  # "Alfa Beta S.r.l."
        if sum(p in comuni for p in parole) >= 2:
            continue  # una frase scritta Con Tutte Le Iniziali Maiuscole
        if m[0].isupper() and _parole_nel_segmento(testo, m) > _MAX_PAROLE_RIGA_MAIUSCOLA:
            continue
        entita_nome = _persona(testo, m.start(), m.end(), "possibile_nome", Priorita.SEGNALAZIONE)
        if entita_nome and " " in entita_nome.valore:
            trovate.append(
                replace(
                    entita_nome,
                    azione=Azione.SEGNALA,
                    nota="Possibile nome non riconosciuto: verificare.",
                )
            )
    return trovate


def _parole_nel_segmento(testo: str, m: re.Match[str]) -> int:
    """Parole nella colonna (o riga) che contiene la sequenza."""
    inizio = max(testo.rfind("\n", 0, m.start()), testo.rfind("  ", 0, m.start())) + 1
    fine_riga = [i for i in (testo.find("\n", m.end()), testo.find("  ", m.end())) if i != -1]
    return len(testo[inizio : min(fine_riga, default=len(testo))].split())


def _persona(testo: str, inizio: int, fine: int, fonte: str, priorita: int) -> Entita | None:
    """Toglie titoli e parole comuni in testa, poi valida come un nome."""
    comuni = elenco("parole_comuni.txt")
    nomi_propri = elenco("nomi_propri.txt")
    parole = list(re.finditer(r"\S+", testo[inizio:fine]))
    for i, parola in enumerate(parole):
        pulita = parola[0].rstrip(",;:").casefold()
        # "GENTILE ANNA": in una coppia cognome + nome la parola comune è un cognome.
        cognome = len(parole) == 2 and i == 0 and pulita not in _TITOLI
        cognome = cognome and (
            parole[1][0].casefold() in nomi_propri or pulita in elenco("cognomi.txt")
        )
        if cognome or (pulita not in comuni and pulita.rstrip(".") not in comuni):
            inizio += parola.start()
            break
    else:
        return None
    intervallo = fine_persona(testo, inizio, fine)
    if not intervallo:
        return None
    inizio, fine = intervallo
    # Fatto solo di luoghi è un luogo: "Ordinario di Padova" in un'intestazione.
    parole = [p.casefold() for p in re.findall(r"[^\W\d_][\w'’]*", testo[inizio:fine])]
    significative = [p for p in parole if p not in comuni]
    if all(p in elenco("luoghi.txt") for p in significative):
        return None
    return Entita(inizio, fine, Tipo.PERSONA, testo[inizio:fine], fonte, priorita)
