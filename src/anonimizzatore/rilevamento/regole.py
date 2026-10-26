"""Dati con un formato fisso: codici, recapiti, indirizzi, documenti e dati di nascita.

Ogni funzione `trova_*` lavora da sola sul testo; `trova` le esegue tutte. Le sovrapposizioni
tra entità si risolvono dopo, in base alla priorità.
"""

import re

from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo
from anonimizzatore.risorse import elenco

_FONTE = "regola"

# --- Codice fiscale ---------------------------------------------------------------------------

# Nelle posizioni numeriche l'omocodia sostituisce le cifre con queste lettere.
_NUM = "0-9LMNPQRSTUV"
_CF = re.compile(
    rf"(?<![A-Za-z0-9])[A-Z]{{6}}[{_NUM}]{{2}}[ABCDEHLMPRST][{_NUM}]{{2}}[A-Z][{_NUM}]{{3}}[A-Z]"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_CF_DISPARI = dict(
    zip(
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [1, 0, 5, 7, 9, 13, 15, 17, 19, 21] * 2
        + [2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23],
        strict=True,
    )
)


def cf_valido(cf: str) -> bool:
    cf = cf.upper()
    somma = 0
    for i, c in enumerate(cf[:15]):
        if i % 2 == 0:
            somma += _CF_DISPARI[c]
        else:
            somma += int(c) if c.isdigit() else ord(c) - ord("A")
    return chr(ord("A") + somma % 26) == cf[15]


def trova_codici_fiscali(testo: str) -> list[Entita]:
    # Un codice con il carattere di controllo errato si maschera comunque: può essere un
    # errore di battitura, ma resta il codice di una persona. Serve almeno una cifra, perché
    # senza il formato coincide con alcune parole minuscole di 16 lettere.
    trovati = []
    for m in _CF.finditer(testo):
        if any(c.isdigit() for c in m[0]):
            priorita = Priorita.REGOLA_VALIDATA if cf_valido(m[0]) else Priorita.REGOLA
            trovati.append(_entita(m, Tipo.CODICE_FISCALE, priorita))
    return trovati


# --- IBAN -------------------------------------------------------------------------------------

_LUNGHEZZE_IBAN = {
    "IT": 27, "SM": 27, "VA": 22, "DE": 22, "FR": 27, "MC": 27, "ES": 24, "PT": 25, "CH": 21,
    "LI": 21, "AT": 20, "BE": 16, "NL": 18, "LU": 20, "GB": 22, "IE": 22, "PL": 28, "RO": 24,
    "HR": 21, "SI": 19, "MT": 31, "GR": 27,
}  # fmt: skip
_IBAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]){10,30}", re.IGNORECASE)
_IBAN_IT = re.compile(r"IT\d{2}[A-Z]\d{10}[A-Z0-9]{12}")


def iban_valido(compatto: str) -> bool:
    riordinato = compatto[4:] + compatto[:4]
    return int("".join(str(int(c, 36)) for c in riordinato)) % 97 == 1


def trova_iban(testo: str) -> list[Entita]:
    trovati = []
    for m in _IBAN.finditer(testo):
        paese = m[0][:2].upper()
        lunghezza = _LUNGHEZZE_IBAN.get(paese)
        fine = _fine_dopo_caratteri(testo, m.start(), lunghezza) if lunghezza else None
        if fine is None:
            continue
        compatto = testo[m.start() : fine].replace(" ", "").upper()
        valido = iban_valido(compatto)
        if paese == "IT" and _IBAN_IT.fullmatch(compatto):
            priorita = Priorita.REGOLA_VALIDATA if valido else Priorita.REGOLA
        elif valido:
            priorita = Priorita.REGOLA_VALIDATA
        else:
            continue
        trovati.append(_crea(testo, m.start(), fine, Tipo.IBAN, priorita))
    return trovati


def _fine_dopo_caratteri(testo: str, inizio: int, quanti: int) -> int | None:
    """Fine dell'IBAN dopo `quanti` caratteri alfanumerici, con spazi singoli tra i gruppi."""
    contati = 0
    for i in range(inizio, len(testo)):
        c = testo[i]
        if c.isalnum():
            contati += 1
            if contati == quanti:
                dopo = testo[i + 1 : i + 2]
                return None if dopo.isalnum() else i + 1
        elif c != " " or testo[i - 1] == " ":
            return None
    return None


# --- Partita IVA ------------------------------------------------------------------------------

_PIVA = re.compile(r"(?<![\w])(?:IT ?)?(\d{11})(?!\d)")
_PIVA_ETICHETTA = re.compile(
    r"(?i:p\.? ?iva|partita\s+iva|p\. ?i\.|c\.f\. ?/ ?p\.? ?iva)\s*[:.]?\s*(?:IT ?)?(\d{11})(?!\d)"
)


def piva_valida(cifre: str) -> bool:
    somma = 0
    for i, c in enumerate(cifre):
        n = int(c)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        somma += n
    return somma % 10 == 0 and len(set(cifre)) > 1


def trova_partite_iva(testo: str) -> list[Entita]:
    # Azione "segnala": diventa "maschera" solo se la partita IVA è di una persona (vicinanza).
    per_posizione: dict[int, Entita] = {}
    for m in _PIVA_ETICHETTA.finditer(testo):
        per_posizione[m.start(1)] = _entita(m, Tipo.PARTITA_IVA, Priorita.REGOLA, Azione.SEGNALA, 1)
    for m in _PIVA.finditer(testo):
        if piva_valida(m[1]):
            per_posizione[m.start(1)] = _entita(
                m, Tipo.PARTITA_IVA, Priorita.REGOLA_VALIDATA, Azione.SEGNALA, 1
            )
    return list(per_posizione.values())


# --- Email ------------------------------------------------------------------------------------

_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![\w-])"
)
# Indirizzi di uffici, non di persone: restano visibili.
_EMAIL_GENERICHE = frozenset({
    "info", "amministrazione", "segreteria", "protocollo", "ufficio", "contatti", "privacy",
    "pec", "posta", "direzione", "commerciale", "vendite", "supporto", "assistenza", "noreply",
    "no-reply", "personale", "contabilita", "fatture", "fatturazione", "ordini", "acquisti",
    "clienti", "anagrafe", "urp", "tributi", "ragioneria", "servizi", "comune", "sindaco",
    "servizioclienti", "assistenzaclienti", "helpdesk",
})  # fmt: skip


def trova_email(testo: str) -> list[Entita]:
    return [
        _entita(m, Tipo.EMAIL, Priorita.REGOLA_VALIDATA)
        for m in _EMAIL.finditer(testo)
        if m[0].split("@")[0].lower() not in _EMAIL_GENERICHE
    ]


# --- Telefono ---------------------------------------------------------------------------------

_TELEFONO = re.compile(
    r"(?<![\w+])(?<!\d[./-])(?P<prefisso>(?:\+|00)39[ .-]?)?"
    r"(?P<numero>3\d{2}(?:[ .-]?\d){6,7}|0\d{1,3}(?:[ ./-]?\d){4,8})(?![\w])"
)
_FORMA_DATA = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}")


def trova_telefoni(testo: str) -> list[Entita]:
    trovati = []
    for m in _TELEFONO.finditer(testo):
        numero = m["numero"]
        cifre = sum(c.isdigit() for c in numero)
        # Fissi da almeno 8 cifre: sotto sono quasi sempre matricole o codici con zeri davanti.
        minimo, massimo = (9, 10) if numero.startswith("3") else (8, 11)
        # Una data, anche seguita dall'ora ("07-09-2026 14:27"), non è un telefono.
        if not minimo <= cifre <= massimo or _FORMA_DATA.search(numero):
            continue
        if numero.isdigit() and len(numero) == 11 and piva_valida(numero):
            continue  # è una partita IVA che inizia con 0
        trovati.append(_entita(m, Tipo.TELEFONO, Priorita.REGOLA))
    return trovati


# --- Indirizzi --------------------------------------------------------------------------------

_TOPONIMI = (
    r"via|viale|v\.le|piazza|p\.zza|p\.za|piazzale|p\.le|piazzetta|corso|c\.so|largo|vicolo|"
    r"vico|strada|str\.|stradella|località|loc\.|contrada|c\.da|frazione|fraz\.|borgo|"
    r"lungomare|lungotevere|salita|galleria|traversa|circonvallazione|calle|campo|fondamenta|"
    r"rione|riva"
)
# Parole maiuscole che di solito iniziano la frase successiva, non il nome di una via o città.
_NON_NOME = r"(?!(?:Il|La|Lo|Le|Gli|Tel|Cell|Codice|Partita|Nato|Nata|Email|Pec|Residente|Data)\b)"
_PAROLA = rf"{_NON_NOME}(?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'’.-]*|[IVXL]{{1,5}}\b|\d{{1,2}}(?=\s+[A-ZÀ-Ý]))"
_CONN = r"(?:d[aei]|del|dello|della|dei|degli|delle|al|alla|ai|alle|agli|e|sul|sulla|in)"
_TOKEN = rf"(?:(?:dell|all|sull|nell|d|l)['’])?{_PAROLA}"
_NOME_VIA = rf"(?:{_CONN}\s+)?{_TOKEN}(?:\s+(?:{_CONN}\s+)?{_TOKEN}){{0,5}}"
_CIVICO = (
    r"(?:,?\s*(?:n\.?|nr\.?|n°|num\.?)?\s*\d{1,4}(?!\d)(?:\s?/\s?\d{1,3}|/?[A-Za-z](?![A-Za-z]))?"
    r"|,?\s*s\.?n\.?c\.?)"
)
_PAROLA_COMUNE = rf"{_NON_NOME}[A-ZÀ-Ý][A-Za-zÀ-ÿ'’]+"
_CAP_COMUNE = (
    rf"\d{{5}}\s+{_PAROLA_COMUNE}(?:[\s-]+(?:d[ei]|del|sul|{_PAROLA_COMUNE})){{0,3}}"
    r"(?:\s*\(\s*[A-Z]{2}\s*\)|\s+[A-Z]{2}(?![A-Za-z]))?"
)
_INDIRIZZO = re.compile(
    rf"(?<![\w])(?:(?i:{_TOPONIMI})\s+{_NOME_VIA}{_CIVICO}(?:\s*[,-]?\s*{_CAP_COMUNE})?"
    rf"|(?<![\d,.]){_CAP_COMUNE})"
)


def trova_indirizzi(testo: str) -> list[Entita]:
    # Azione "segnala": diventa "maschera" solo se l'indirizzo è di una persona (vicinanza).
    trovati = []
    for m in _INDIRIZZO.finditer(testo):
        # CAP + comune da solo: la parola dopo le cinque cifre deve poter essere un comune, non
        # "ORE" di "-57,38000 ORE" o "CAB" di "ABI 08450 CAB 10200".
        if m[0][0].isdigit():
            parola = m[0][5:].split()[0].casefold()
            prima = testo[max(0, m.start() - 4) : m.start()].strip().casefold()
            if parola in elenco("parole_comuni.txt") or prima in ("abi", "cab"):
                continue
        trovati.append(_entita(m, Tipo.INDIRIZZO, Priorita.REGOLA, Azione.SEGNALA))
    return trovati


# --- Documenti d'identità ---------------------------------------------------------------------

_DOCUMENTO = re.compile(
    r"(?i:carta\s+d['’] ?identit[àa]|c\. ?i\.|documento(?:\s+d['’] ?identit[àa])?|passaporto"
    r"|patente(?:\s+di\s+guida)?)"
    r"(?:\s+(?i:n\.?|nr\.?|n°|numero|num\.?))?\s*[:.]?\s*(?P<v>[A-Z]{0,3}\d[A-Z0-9]{4,11})"
    r"(?![A-Za-z0-9])"
)


def trova_documenti(testo: str) -> list[Entita]:
    return [
        _entita(m, Tipo.DOCUMENTO, Priorita.REGOLA, gruppo="v")
        for m in _DOCUMENTO.finditer(testo)
        if sum(c.isdigit() for c in m["v"]) >= 4
    ]


# --- Data e luogo di nascita ------------------------------------------------------------------

_MESI = (
    "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
)
DATA = (
    rf"(?:\d{{1,2}} ?[./-] ?\d{{1,2}} ?[./-] ?\d{{2,4}}|\d{{1,2}}°?\s+(?i:{_MESI})\s+\d{{4}})"
    r"(?!\d)"
)
# Nei testi tutti maiuscoli "IL" dopo il luogo introduce la data: "NATO A PADOVA IL …".
_DOPO_LUOGO = r"(?!(?i:il|in|ed?|residente)\b)"
LUOGO = (
    rf"{_PAROLA_COMUNE}(?:[\s-]+(?:d[ei]|del|della|sul|sull['’]|{_DOPO_LUOGO}{_PAROLA_COMUNE}))"
    r"{0,3}"
)
_PROVINCIA = r"(?:\s*\(\s*[A-Z]{2}\s*\))?"
_NATO = r"(?i:nat[oa](?:/[ao])?)"
_NASCITA = (
    re.compile(
        rf"(?<![\w]){_NATO}\s+(?i:a|ad|in)\s+(?P<luogo>{LUOGO}){_PROVINCIA}\s*,?\s*"
        rf"(?:(?i:il)\s+(?P<data>{DATA}))?"
    ),
    re.compile(
        rf"(?<![\w]){_NATO}\s+(?i:il)\s+(?P<data>{DATA})"
        rf"(?:\s*,?\s*(?i:a|ad|in)\s+(?P<luogo>{LUOGO}))?"
    ),
)
# Parole maiuscole che nei testi tutti maiuscoli seguono il luogo: "NATO A PADOVA IL …".
_CODA_LUOGO = frozenset(
    {"il", "in", "e", "ed", "residente", "domiciliato", "domiciliata", "cod", "codice"}
)


def trova_nascita(testo: str) -> list[Entita]:
    trovati = []
    for espressione in _NASCITA:
        for m in espressione.finditer(testo):
            if m["luogo"]:
                fine = taglia_coda(testo, m.start("luogo"), m.end("luogo"), _CODA_LUOGO)
                if fine > m.start("luogo"):
                    trovati.append(
                        _crea(testo, m.start("luogo"), fine, Tipo.LUOGO_NASCITA, Priorita.REGOLA)
                    )
            if m["data"]:
                trovati.append(_entita(m, Tipo.DATA_NASCITA, Priorita.REGOLA, gruppo="data"))
    return trovati


def taglia_coda(testo: str, inizio: int, fine: int, scarta: frozenset[str]) -> int:
    """Nuova fine di testo[inizio:fine] senza le ultime parole che stanno in `scarta`."""
    parole = list(re.finditer(r"\S+", testo[inizio:fine]))
    while parole and parole[-1][0].casefold() in scarta:
        parole.pop()
    return inizio + parole[-1].end() if parole else inizio


# --- Codici letti male dall'OCR ---------------------------------------------------------------
# Nelle scansioni l'OCR confonde lettere e cifre che si somigliano (O e 0, I e 1, B e 8…) e
# aggiunge spazi. Un codice si corregge solo dove il formato vuole una cifra o una lettera, e si
# accetta solo se il carattere di controllo torna: così una sequenza qualsiasi non diventa un
# codice per caso.

_A_LETTERA = str.maketrans("012345678", "OIZEASGTB")
# Nelle posizioni numeriche del codice fiscale L, M, N, P, Q, R, S, T, U, V sono omocodia
# valida: si correggono solo le lettere che non possono stare lì.
_A_CIFRA_CF = str.maketrans("ODIZBG", "001286")
_A_CIFRA = str.maketrans("OoDIlZSB", "00011258")
_LETTERE_CF = {0, 1, 2, 3, 4, 5, 8, 11, 15}
_CF_COMPATTO = re.compile(
    rf"[A-Z]{{6}}[{_NUM}]{{2}}[ABCDEHLMPRST][{_NUM}]{{2}}[A-Z][{_NUM}]{{3}}[A-Z]"
)
# Inizio possibile di un codice ad ogni posizione: la ricerca deve poter sovrapporre i candidati.
_CF_OCR = re.compile(r"(?<![A-Za-z0-9])(?=([A-Za-z0-9](?: ?[A-Za-z0-9]){15})(?![A-Za-z0-9]))")
_IBAN_OCR = re.compile(r"(?<![A-Za-z0-9])(?=([I1l][T7](?: ?[A-Za-z0-9]){25})(?![A-Za-z0-9]))")
_PIVA_OCR = re.compile(
    r"(?i:p\.? ?iva|partita\s+iva)\s*[:.]?\s*(?:IT ?)?([0-9OoIl]{11})(?![0-9A-Za-z])"
)


def trova_codici_letti_male(testo: str, gia_trovati: list[Entita]) -> list[Entita]:
    # Conta solo dove c'è già un codice: un telefono trovato per sbaglio dentro un IBAN letto
    # male non deve impedire di riconoscere l'IBAN (che vince poi per priorità).
    codici = {Tipo.CODICE_FISCALE, Tipo.IBAN, Tipo.PARTITA_IVA}
    occupati = [(e.inizio, e.fine) for e in gia_trovati if e.tipo in codici]
    trovati: list[Entita] = []

    def libero(inizio: int, fine: int) -> bool:
        intervalli = occupati + [(e.inizio, e.fine) for e in trovati]
        return not any(a < fine and inizio < b for a, b in intervalli)

    for m in _CF_OCR.finditer(testo):
        candidato = m[1]
        if sum(c.isdigit() for c in candidato) < 3 or not libero(m.start(1), m.end(1)):
            continue
        compatto = candidato.replace(" ", "").upper()
        corretto = "".join(
            c.translate(_A_LETTERA if i in _LETTERE_CF else _A_CIFRA_CF)
            for i, c in enumerate(compatto)
        )
        if corretto != candidato and _CF_COMPATTO.fullmatch(corretto) and cf_valido(corretto):
            trovati.append(_entita(m, Tipo.CODICE_FISCALE, Priorita.REGOLA_VALIDATA, gruppo=1))

    for m in _IBAN_OCR.finditer(testo):
        if not libero(m.start(1), m.end(1)):
            continue
        compatto = m[1].replace(" ", "")
        corretto = (
            "IT"
            + compatto[2:4].translate(_A_CIFRA)
            + compatto[4].upper().translate(_A_LETTERA)
            + compatto[5:15].translate(_A_CIFRA)
            + compatto[15:].upper()
        )
        if _IBAN_IT.fullmatch(corretto) and iban_valido(corretto):
            trovati.append(_entita(m, Tipo.IBAN, Priorita.REGOLA_VALIDATA, gruppo=1))

    for m in _PIVA_OCR.finditer(testo):
        cifre = m[1].translate(_A_CIFRA)
        if cifre != m[1] and cifre.isdigit() and piva_valida(cifre) and libero(*m.span(1)):
            trovati.append(
                _entita(m, Tipo.PARTITA_IVA, Priorita.REGOLA_VALIDATA, Azione.SEGNALA, 1)
            )
    return trovati


# --- Insieme ----------------------------------------------------------------------------------

_TUTTE = (
    trova_codici_fiscali,
    trova_iban,
    trova_partite_iva,
    trova_email,
    trova_telefoni,
    trova_indirizzi,
    trova_documenti,
    trova_nascita,
)


def trova(testo: str) -> list[Entita]:
    entita = [e for funzione in _TUTTE for e in funzione(testo)]
    entita += trova_codici_letti_male(testo, entita)
    entita += trova_codici_fiscali_dopo_etichetta(testo, entita)
    entita += trova_date_dal_codice_fiscale(testo, entita)
    return sorted(entita, key=lambda e: (e.inizio, -e.fine))


# --- Codice fiscale dopo l'etichetta e data di nascita dal codice -----------------------------

_CF_ETICHETTA = re.compile(
    r"(?i:codice\s+fiscale|cod\.?\s*fisc\.?|c\.\s?f\.|\bcf\b)\s*[:.]?\s*"
    r"(?P<v>[A-Za-z0-9]{15,17})(?![A-Za-z0-9])"
)


def trova_codici_fiscali_dopo_etichetta(testo: str, gia_trovati: list[Entita]) -> list[Entita]:
    """Dopo "codice fiscale" anche un codice di 15–17 caratteri: l'OCR ne aggiunge o ne perde.

    Se togliendo un carattere esce un codice valido, il codice è sicuro; altrimenti basta la
    forma (lettere e almeno 4 cifre), perché subito dopo l'etichetta c'è comunque un codice.
    """
    fiscali = [e for e in gia_trovati if e.tipo == Tipo.CODICE_FISCALE]
    trovati = []
    for m in _CF_ETICHETTA.finditer(testo):
        valore = m["v"]
        if any(e.inizio < m.end("v") and m.start("v") < e.fine for e in fiscali):
            continue
        if len(valore) == 16 or sum(c.isdigit() for c in valore) < 4:
            continue  # 16 caratteri: se era valido l'hanno già trovato le altre regole
        varianti = {valore[:i] + valore[i + 1 :] for i in range(len(valore))}
        validi = len(valore) == 17 and any(
            _CF_COMPATTO.fullmatch(v.upper()) and cf_valido(v) for v in varianti
        )
        priorita = Priorita.REGOLA_VALIDATA if validi else Priorita.ETICHETTA
        trovati.append(_entita(m, Tipo.CODICE_FISCALE, priorita, gruppo="v"))
    return trovati


_MESI_CF = "ABCDEHLMPRST"
_OMOCODIA = str.maketrans("LMNPQRSTUV", "0123456789")
_DATA_NUMERICA = re.compile(r"(?<![\d])(\d{1,2})\s?[./-]\s?(\d{1,2})\s?[./-]\s?(\d{4}|\d{2})(?!\d)")


def data_dal_codice_fiscale(cf: str) -> tuple[int, int, int] | None:
    """Giorno, mese e ultime due cifre dell'anno di nascita codificati nel codice fiscale."""
    cf = cf.replace(" ", "").upper()
    if not _CF_COMPATTO.fullmatch(cf):
        return None
    anno = int(cf[6:8].translate(_OMOCODIA))
    mese = _MESI_CF.index(cf[8]) + 1
    giorno = int(cf[9:11].translate(_OMOCODIA))
    return (giorno - 40 if giorno > 40 else giorno), mese, anno


def trova_date_dal_codice_fiscale(testo: str, gia_trovati: list[Entita]) -> list[Entita]:
    """Ogni data uguale a quella di nascita di un codice fiscale del documento è una data di
    nascita, anche lontana dalla sua etichetta (le buste paga mettono le etichette in una riga
    e i valori in un'altra)."""
    nascite = {
        data
        for e in gia_trovati
        if e.tipo == Tipo.CODICE_FISCALE and (data := data_dal_codice_fiscale(e.valore))
    }
    trovati = []
    for m in _DATA_NUMERICA.finditer(testo):
        giorno, mese, anno = int(m[1]), int(m[2]), int(m[3]) % 100
        if (giorno, mese, anno) in nascite:
            trovati.append(_entita(m, Tipo.DATA_NASCITA, Priorita.REGOLA_VALIDATA))
    return trovati


def _entita(
    m: re.Match[str],
    tipo: Tipo,
    priorita: int,
    azione: Azione = Azione.MASCHERA,
    gruppo: int | str = 0,
) -> Entita:
    return Entita(m.start(gruppo), m.end(gruppo), tipo, m[gruppo], _FONTE, priorita, azione)


def _crea(
    testo: str, inizio: int, fine: int, tipo: Tipo, priorita: int, azione: Azione = Azione.MASCHERA
) -> Entita:
    return Entita(inizio, fine, tipo, testo[inizio:fine], _FONTE, priorita, azione)
