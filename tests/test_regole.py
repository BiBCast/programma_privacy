"""Test delle regole a formato fisso (milestone M2). Solo dati inventati."""

import pytest

from anonimizzatore.rilevamento import regole
from anonimizzatore.rilevamento.modelli import Azione, Priorita, Tipo


def valori(entita, tipo):
    return [e.valore for e in entita if e.tipo == tipo]


def luhn(cifre: str) -> bool:
    """Controllo di Luhn scritto in modo indipendente dal codice, contando da destra."""
    totale = 0
    for i, c in enumerate(reversed(cifre)):
        n = int(c) * (2 if i % 2 else 1)
        totale += n - 9 if n > 9 else n
    return totale % 10 == 0


def piva_con_controllo(dieci: str) -> str:
    return next(dieci + str(d) for d in range(10) if luhn(dieci + str(d)))


PIVA = piva_con_controllo("0123456789")


# --- Codice fiscale ---------------------------------------------------------------------------


def test_cf_valido_maiuscolo_e_minuscolo():
    trovati = regole.trova_codici_fiscali("C.F. RSSMRA80A01H501U e rssmra80a01h501u")
    assert [e.valore for e in trovati] == ["RSSMRA80A01H501U", "rssmra80a01h501u"]
    assert all(e.priorita == Priorita.REGOLA_VALIDATA for e in trovati)


def test_cf_con_controllo_errato_si_maschera_comunque():
    (trovato,) = regole.trova_codici_fiscali("RSSMRA80A01H501X")
    assert trovato.priorita == Priorita.REGOLA and trovato.azione == Azione.MASCHERA


def test_cf_non_trovato_dentro_parole_o_senza_cifre():
    assert regole.trova_codici_fiscali("XRSSMRA80A01H501U") == []
    assert regole.trova_codici_fiscali("abcdeflmamnzlmnz") == []


# --- IBAN -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("IBAN IT60X0542811101000000123456.", "IT60X0542811101000000123456"),
        ("IBAN: IT60 X054 2811 1010 0000 0123 456 intestato", "IT60 X054 2811 1010 0000 0123 456"),
        ("conto DE89370400440532013000", "DE89370400440532013000"),
        ("conto GB82WEST12345698765432", "GB82WEST12345698765432"),
    ],
)
def test_iban_trovati(testo, atteso):
    assert valori(regole.trova_iban(testo), Tipo.IBAN) == [atteso]


def test_iban_italiano_con_controllo_errato_si_maschera_comunque():
    (trovato,) = regole.trova_iban("IT61X0542811101000000123456")
    assert trovato.priorita == Priorita.REGOLA


def test_iban_estero_non_valido_scartato():
    assert regole.trova_iban("DE89370400440532013001") == []


# --- Partita IVA ------------------------------------------------------------------------------


def test_piva_valida_trovata_come_segnalazione():
    (trovata,) = regole.trova_partite_iva(f"partita IVA IT{PIVA}")
    assert trovata.valore == PIVA
    assert trovata.azione == Azione.SEGNALA and trovata.priorita == Priorita.REGOLA_VALIDATA


def test_piva_non_valida_solo_con_etichetta():
    non_valida = "12345678901"
    assert not luhn(non_valida)
    assert regole.trova_partite_iva(f"numero {non_valida}") == []
    (trovata,) = regole.trova_partite_iva(f"P.IVA: {non_valida}")
    assert trovata.priorita == Priorita.REGOLA


def test_piva_scartate():
    assert regole.trova_partite_iva("00000000000") == []
    assert regole.trova_partite_iva(f"9{PIVA}") == []


# --- Email ------------------------------------------------------------------------------------


def test_email_personale_trovata_e_generica_no():
    testo = "Scrivere a mario.rossi@esempio.it oppure a info@studio-esempio.it"
    assert valori(regole.trova_email(testo), Tipo.EMAIL) == ["mario.rossi@esempio.it"]


# --- Telefono ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "numero",
    [
        "333 1234567",
        "+39 333 123 4567",
        "3331234567",
        "049 8765432",
        "049/8765432",
        "0039 049 8765432",
    ],
)
def test_telefoni_trovati(numero):
    assert valori(regole.trova_telefoni(f"Tel. {numero} grazie"), Tipo.TELEFONO) == [numero]


@pytest.mark.parametrize(
    "testo",
    [
        "il 01.02.2024",
        "importo 1.234,56",
        "CAP 35100",
        "nato il 12/03/1975",
        "anno 2024",
        "Matricola 004512",
        f"P.IVA {PIVA}",
    ],
)
def test_non_sono_telefoni(testo):
    assert regole.trova_telefoni(testo) == []


# --- Indirizzi --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("abita in Via Roma 5 da anni", "Via Roma 5"),
        (
            "residente in via Giuseppe Garibaldi, 12/A, 35100 Padova (PD).",
            "via Giuseppe Garibaldi, 12/A, 35100 Padova (PD)",
        ),
        ("Piazza dei Signori 1", "Piazza dei Signori 1"),
        ("Corso Vittorio Emanuele II 45", "Corso Vittorio Emanuele II 45"),
        ("Via XX Settembre 3", "Via XX Settembre 3"),
        ("Via 4 Novembre 10", "Via 4 Novembre 10"),
        ("Via dell'Industria 7", "Via dell'Industria 7"),
        ("Viale Europa, n. 21", "Viale Europa, n. 21"),
        ("sede a 35100 Padova (PD)", "35100 Padova (PD)"),
        ("30027 San Donà di Piave (VE)", "30027 San Donà di Piave (VE)"),
    ],
)
def test_indirizzi_trovati(testo, atteso):
    trovati = regole.trova_indirizzi(testo)
    assert valori(trovati, Tipo.INDIRIZZO) == [atteso]
    assert trovati[0].azione == Azione.SEGNALA


@pytest.mark.parametrize("testo", ["per via di Mario", "la via più breve", "Via Roma è chiusa"])
def test_non_sono_indirizzi(testo):
    assert regole.trova_indirizzi(testo) == []


# --- Documenti --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("carta d'identità n. CA12345AB rilasciata", "CA12345AB"),
        ("Passaporto YA1234567", "YA1234567"),
        ("documento: AB1234567", "AB1234567"),
    ],
)
def test_documenti(testo, atteso):
    assert valori(regole.trova_documenti(testo), Tipo.DOCUMENTO) == [atteso]


def test_documento_senza_codice():
    assert regole.trova_documenti("il passaporto è valido") == []


# --- Nascita ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo, luogo, data",
    [
        ("nato a Padova il 12/03/1975, residente", "Padova", "12/03/1975"),
        ("nata a San Donà di Piave (VE) il 1 marzo 1980", "San Donà di Piave", "1 marzo 1980"),
        ("NATO A PADOVA IL 12.03.1975", "PADOVA", "12.03.1975"),
        ("nato il 12/03/1975 a Padova", "Padova", "12/03/1975"),
        ("nato/a a Rovigo il 5-6-1990", "Rovigo", "5-6-1990"),
    ],
)
def test_nascita(testo, luogo, data):
    trovati = regole.trova_nascita(testo)
    assert valori(trovati, Tipo.LUOGO_NASCITA) == [luogo]
    assert valori(trovati, Tipo.DATA_NASCITA) == [data]


# --- Insieme ----------------------------------------------------------------------------------


def test_trova_ordina_per_posizione_e_ogni_valore_corrisponde_al_testo():
    testo = (
        "Mario Rossi, nato a Padova il 12/03/1975, C.F. RSSMRA80A01H501U, "
        "residente in Via Roma 5, 35100 Padova (PD), tel. 333 1234567, "
        "email mario.rossi@esempio.it, IBAN IT60X0542811101000000123456"
    )
    trovati = regole.trova(testo)
    assert [e.inizio for e in trovati] == sorted(e.inizio for e in trovati)
    assert all(testo[e.inizio : e.fine] == e.valore for e in trovati)
    tipi = {e.tipo for e in trovati}
    assert {Tipo.CODICE_FISCALE, Tipo.IBAN, Tipo.EMAIL, Tipo.TELEFONO, Tipo.INDIRIZZO} <= tipi
    assert {Tipo.DATA_NASCITA, Tipo.LUOGO_NASCITA} <= tipi
