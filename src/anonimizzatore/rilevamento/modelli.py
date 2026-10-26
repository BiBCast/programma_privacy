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
    CODICE_CLIENTE = "CODICE_CLIENTE"  # codice cliente, conto contrattuale, POD, PDR
    CONTO = "CONTO"  # numero di conto corrente senza IBAN
    # Dai "sempre da mascherare" dell'utente che non sono nomi di persona.
    DATO = "DATO"
    # Categorie particolari (art. 9 GDPR) e dati giudiziari (art. 10): solo segnalati.
    DATO_SALUTE = "DATO_SALUTE"
    DATO_SINDACALE = "DATO_SINDACALE"
    DATO_POLITICO = "DATO_POLITICO"
    DATO_RELIGIOSO = "DATO_RELIGIOSO"
    DATO_SESSUALE = "DATO_SESSUALE"
    DATO_ETNICO = "DATO_ETNICO"
    DATO_BIOMETRICO = "DATO_BIOMETRICO"
    DATO_GIUDIZIARIO = "DATO_GIUDIZIARIO"
    DATO_SENSIBILE = "DATO_SENSIBILE"  # parole sensibili aggiunte dall'utente


class Azione(StrEnum):
    MASCHERA = "maschera"
    SEGNALA = "segnala"
    ESCLUDI = "escludi"


class Priorita(IntEnum):
    """Chi vince quando due entità si sovrappongono (la scelta la fa `risoluzione.risolvi`)."""

    UTENTE = 1000  # una decisione dell'utente vince su tutto
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
