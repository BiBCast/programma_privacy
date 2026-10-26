from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Tipo(StrEnum):
    PERSONA = "PERSONA"
    CODICE_FISCALE = "CODICE_FISCALE"
    PARTITA_IVA = "PARTITA_IVA"
    IBAN = "IBAN"
    EMAIL = "EMAIL"
    TELEFONO = "TELEFONO"
    INDIRIZZO = "INDIRIZZO"
    DATA_NASCITA = "DATA_NASCITA"
    LUOGO_NASCITA = "LUOGO_NASCITA"
    DOCUMENTO = "DOCUMENTO"
    MATRICOLA = "MATRICOLA"


class Azione(StrEnum):
    MASCHERA = "maschera"
    SEGNALA = "segnala"
    ESCLUDI = "escludi"


class Priorita(IntEnum):
    """Chi vince quando due entità si sovrappongono (la scelta la fa la risoluzione, in M4)."""

    REGOLA_VALIDATA = 100
    REGOLA = 90
    ETICHETTA = 80
    ELENCO_NOMI = 60
    NER = 50
    PROPAGAZIONE = 40
    SEGNALAZIONE = 10


@dataclass(frozen=True)
class Entita:
    inizio: int  # offset nel testo estratto e normalizzato
    fine: int
    tipo: Tipo
    valore: str  # testo originale, uguale a testo[inizio:fine]
    fonte: str  # "regola", "etichetta", "ner", …
    priorita: int
    azione: Azione = Azione.MASCHERA
    # Solo per la propagazione: la persona a cui si riferisce ("mario rossi"), così riceve
    # lo stesso pseudonimo anche se qui compare solo "Rossi".
    persona: str = ""
    nota: str = ""  # da mostrare in revisione, per esempio un'omonimia
