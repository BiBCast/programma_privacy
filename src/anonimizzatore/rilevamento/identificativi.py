"""Altri identificativi di persona (milestone M4b): carte, tessera sanitaria, targhe, numeri dei
procedimenti, polizze, telefoni esteri, identificativi online, età e data di morte.

Come in `regole.py`, ogni funzione `trova_*` lavora da sola; `trova` le esegue tutte.
"""

import re

from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo
from anonimizzatore.rilevamento.regole import DATA

_FONTE = "regola"


def _entita(m, tipo, priorita=Priorita.REGOLA, azione=Azione.MASCHERA, gruppo=0, nota=""):
    return Entita(
        m.start(gruppo), m.end(gruppo), tipo, m[gruppo], _FONTE, priorita, azione, nota=nota
    )


def luhn(cifre: str) -> bool:
    totale = 0
    for i, c in enumerate(reversed(cifre)):
        n = int(c) * (2 if i % 2 else 1)
        totale += n - 9 if n > 9 else n
    return totale % 10 == 0


# --- Carte di pagamento -----------------------------------------------------------------------

_CARTA = re.compile(r"(?<![\d])\d(?:[ -]?\d){12,18}(?![\d])")
_CARTA_ETICHETTA = re.compile(
    r"(?i)(?:carta(?:\s+di\s+(?:credito|debito|pagamento))?|n\.\s?carta|pan|visa|mastercard"
    r"|maestro|american\s+express|amex|bancomat|postepay)(?:\W{0,3}(?:n|nr|n°|numero))?\W{0,10}$"
)
# Lunghezze ammesse per i circuiti più diffusi: un codice a barre di 18 cifre che inizia per 4
# non è una Visa.
_CIRCUITI = (
    (re.compile(r"4"), {13, 16, 19}),  # Visa
    (re.compile(r"5[1-5]|2(?:2[2-9]|[3-6]\d|7[01]|720)"), {16}),  # Mastercard
    (re.compile(r"3[47]"), {15}),  # American Express
    (re.compile(r"6(?:011|5)"), {16, 19}),  # Discover
    (re.compile(r"5[06-9]|6\d"), {12, 13, 14, 15, 16, 17, 18, 19}),  # Maestro
)


def trova_carte(testo: str) -> list[Entita]:
    trovate = []
    for m in _CARTA.finditer(testo):
        cifre = re.sub(r"\D", "", m[0])
        if not luhn(cifre) or len(set(cifre)) == 1:
            continue
        circuito = any(p.match(cifre) and len(cifre) in lunghezze for p, lunghezze in _CIRCUITI)
        a_gruppi = bool(re.fullmatch(r"\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,3})?", m[0]))
        etichetta = _CARTA_ETICHETTA.search(testo[max(0, m.start() - 40) : m.start()])
        # Serve il circuito giusto e in più la scrittura a gruppi di 4 o un'etichetta: un numero
        # lungo qualsiasi che per caso passa il controllo di Luhn non basta.
        if circuito and (a_gruppi or etichetta):
            trovate.append(_entita(m, Tipo.CARTA, Priorita.REGOLA_VALIDATA))
    return trovate


# --- Tessera sanitaria ------------------------------------------------------------------------

# Numero della tessera europea (TEAM): 20 cifre che iniziano con 80380.
_TESSERA = re.compile(r"(?<![\d])80380(?:[ -]?\d){15}(?![\d])")
_TESSERA_ETICHETTA = re.compile(
    r"(?i)(?:tessera\s+sanitaria|tessera\s+team|n\.\s?tessera|numero\s+tessera)\s*[:.]?\s*(?:n\.?\s*)?"
    r"(?P<v>\d(?:[ -]?\d){9,19})(?![\d])"
)


def trova_tessere_sanitarie(testo: str) -> list[Entita]:
    trovate = {m.start(): _entita(m, Tipo.TESSERA_SANITARIA) for m in _TESSERA.finditer(testo)}
    for m in _TESSERA_ETICHETTA.finditer(testo):
        trovate.setdefault(m.start("v"), _entita(m, Tipo.TESSERA_SANITARIA, gruppo="v"))
    return list(trovate.values())


# --- Targhe -----------------------------------------------------------------------------------

# Formato attuale: due lettere, tre cifre, due lettere; non si usano I, O, Q, U.
_LETTERA_TARGA = "A-HJ-NPR-TV-Z"
_TARGA = re.compile(
    rf"(?<![A-Za-z0-9])[{_LETTERA_TARGA}]{{2}} ?\d{{3}} ?[{_LETTERA_TARGA}]{{2}}(?![A-Za-z0-9])"
)
_TARGA_ETICHETTA = re.compile(
    r"(?i)(?:targa|targat[oa]|veicolo|autovettura|auto|motociclo|ciclomotore|autocarro)\W{0,20}$"
)


def trova_targhe(testo: str) -> list[Entita]:
    trovate = []
    for m in _TARGA.finditer(testo):
        if _TARGA_ETICHETTA.search(testo[max(0, m.start() - 30) : m.start()]):
            trovate.append(_entita(m, Tipo.TARGA))
        else:
            # Senza "targa" vicino può essere un codice qualsiasi: si segnala soltanto.
            trovate.append(
                _entita(
                    m, Tipo.TARGA, Priorita.SEGNALAZIONE, Azione.SEGNALA, nota="Forse una targa."
                )
            )
    return trovate


# --- Numeri dei procedimenti ------------------------------------------------------------------

_NUMERO_ANNO = r"\d{1,7}\s?/\s?(?:19|20)?\d{2}"
_PROCEDIMENTO = re.compile(
    r"(?i:\bR\.?\s?G\.?\s?(?:N\.?\s?R\.?|G\.?\s?I\.?\s?P\.?|L\.?|E\.?|A\.?\s?C\.?)?|ruolo\s+generale"
    r"|proc(?:\.|edimento)(?:\s+penale|\s+civile)?|n\.\s?r\.?\s?g\.?)"
    rf"\s*(?:n\.?|nr\.?|n°)?\s*[:.]?\s*(?P<v>{_NUMERO_ANNO})(?!\d)"
)
# Anche con il numero prima: "n. 1234/2025 R.G."
_PROCEDIMENTO_DOPO = re.compile(
    rf"(?<![\d/])(?P<v>{_NUMERO_ANNO})(?!\d)\s*(?i:R\.?\s?G\.?(?:\s?N\.?\s?R\.?)?)(?![A-Za-z])"
)


def trova_procedimenti(testo: str) -> list[Entita]:
    trovati: dict[int, Entita] = {}
    for espressione in (_PROCEDIMENTO, _PROCEDIMENTO_DOPO):
        for m in espressione.finditer(testo):
            trovati.setdefault(m.start("v"), _entita(m, Tipo.PROCEDIMENTO, gruppo="v"))
    return list(trovati.values())


# --- Polizze, sinistri, pratiche --------------------------------------------------------------

_POLIZZA = re.compile(
    r"(?i:polizza|n\.\s?polizza|numero\s+polizza|sinistro|n\.\s?sinistro|numero\s+sinistro"
    r"|pratica|n\.\s?pratica|numero\s+pratica|contratto\s+assicurativo)"
    r"\s*(?:n\.?|nr\.?|n°|numero)?\s*[:.]?\s*(?P<v>[A-Z0-9][A-Z0-9/.-]{3,24})(?![A-Za-z0-9])"
)


def trova_polizze(testo: str) -> list[Entita]:
    return [
        _entita(m, Tipo.CODICE_CLIENTE, gruppo="v")
        for m in _POLIZZA.finditer(testo)
        if sum(c.isdigit() for c in m["v"]) >= 4
        and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", m["v"])
    ]


# --- Telefoni esteri --------------------------------------------------------------------------

_TELEFONO_ESTERO = re.compile(
    r"(?<![\w+])(?:\+|00)(?!39)[1-9]\d{0,2}[ .-]?\(?\d{1,4}\)?(?:[ .-]?\d){5,11}(?![\w])"
)


def trova_telefoni_esteri(testo: str) -> list[Entita]:
    trovati = []
    for m in _TELEFONO_ESTERO.finditer(testo):
        cifre = sum(c.isdigit() for c in m[0])
        if 8 <= cifre <= 15:
            trovati.append(_entita(m, Tipo.TELEFONO))
    return trovati


# --- Identificativi online --------------------------------------------------------------------

_OTTETTO = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_IPV4 = re.compile(rf"(?<![\d.]){_OTTETTO}(?:\.{_OTTETTO}){{3}}(?![\d.])")
_IPV6 = re.compile(
    r"(?<![\w:])(?:(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,6}:(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4})(?![\w:])"
)
_PROFILO = re.compile(
    r"(?i)(?:https?://)?(?:www\.|[a-z]{2}\.)?(?:facebook|instagram|linkedin|twitter|x|tiktok"
    r"|youtube|threads)\.com/[^\s<>\"')]+"
)
_HANDLE = re.compile(r"(?<![\w@.])@[A-Za-z][A-Za-z0-9_.]{2,29}(?![\w@])")


def trova_identificativi_online(testo: str) -> list[Entita]:
    trovati = [_entita(m, Tipo.ID_ONLINE) for m in _IPV4.finditer(testo)]
    trovati += [
        _entita(m, Tipo.ID_ONLINE)
        for m in _IPV6.finditer(testo)
        if sum(c == ":" for c in m[0]) >= 3 and any(c.isalpha() or c == ":" for c in m[0])
    ]
    trovati += [_entita(m, Tipo.ID_ONLINE) for m in _PROFILO.finditer(testo)]
    trovati += [_entita(m, Tipo.ID_ONLINE) for m in _HANDLE.finditer(testo)]
    return trovati


# --- Età e data di morte ----------------------------------------------------------------------

_ETA = re.compile(
    r"(?i)(?:\bdi\s+anni\s+(?P<a>\d{1,3})\b|\bet[àa]\s*[:.]?\s*(?P<b>\d{1,3})(?:\s+anni)?\b"
    r"|\b(?P<c>\d{1,3})\s?-?enne\b|\banni\s+(?P<d>\d{1,3})\s*,)"
)
_MORTE = re.compile(
    rf"(?i:decedut[oa]|mort[oa]|scompars[oa]|deceduta/o|data\s+(?:di|del)\s+(?:morte|decesso)"
    rf"|decesso\s+avvenuto)(?:\s+(?:a|ad|in)\s+[A-ZÀ-Ý][\w'’]*(?:\s+\([A-Z]{{2}}\))?)?"
    rf"\s*,?\s*(?:(?i:il|in\s+data|in\s+data\s+del|del)\s+)?[:.]?\s*(?P<v>{DATA})"
)


def trova_eta(testo: str) -> list[Entita]:
    trovate = []
    for m in _ETA.finditer(testo):
        gruppo = next(g for g in "abcd" if m[g])
        if int(m[gruppo]) <= 120:
            trovate.append(
                _entita(
                    m,
                    Tipo.ETA,
                    Priorita.SEGNALAZIONE,
                    Azione.SEGNALA,
                    gruppo=gruppo,
                    nota="Età di una persona: insieme ad altri dati può identificarla.",
                )
            )
    return trovate


def trova_date_di_morte(testo: str) -> list[Entita]:
    return [_entita(m, Tipo.DATA_MORTE, gruppo="v") for m in _MORTE.finditer(testo)]


# --- Codice fiscale numerico ------------------------------------------------------------------

# Il codice fiscale di 11 cifre è quello delle società, ma anche di alcune persone: come la
# partita IVA si segnala, e la vicinanza a una persona decide se mascherarlo.
_CF_NUMERICO = re.compile(
    r"(?i:codice\s+fiscale|cod\.?\s*fisc\.?|c\.\s?f\.)\s*[:.]?\s*(?P<v>\d{11})(?!\d)"
)


def trova_codici_fiscali_numerici(testo: str) -> list[Entita]:
    return [
        _entita(m, Tipo.CODICE_FISCALE, Priorita.REGOLA, Azione.SEGNALA, gruppo="v")
        for m in _CF_NUMERICO.finditer(testo)
    ]


# --- Insieme ----------------------------------------------------------------------------------

_TUTTE = (
    trova_codici_fiscali_numerici,
    trova_carte,
    trova_tessere_sanitarie,
    trova_targhe,
    trova_procedimenti,
    trova_polizze,
    trova_telefoni_esteri,
    trova_identificativi_online,
    trova_eta,
    trova_date_di_morte,
)


def trova(testo: str) -> list[Entita]:
    entita = [e for funzione in _TUTTE for e in funzione(testo)]
    return sorted(entita, key=lambda e: (e.inizio, -e.fine))
