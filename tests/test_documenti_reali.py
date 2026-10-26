"""Casi emersi dalla prova su documenti reali (26/10/2026), riscritti con dati inventati.

Nessun valore viene dai documenti veri: nomi, codici, date e indirizzi sono di fantasia e
riproducono solo la forma del caso.
"""

import pytest

from anonimizzatore.estrazione import estrai, ocr
from anonimizzatore.motore import analizza, applica
from anonimizzatore.rilevamento import nomi, regole
from anonimizzatore.rilevamento.modelli import Azione, Tipo
from generatori.scansioni import pdf_di_testo, scansiona


def mascherato(testo):
    return applica(analizza(testo), nota_per_ai=False)


def test_data_di_nascita_ricavata_dal_codice_fiscale():
    # RSSMRA80A01H501U: nato il 1 gennaio 1980. La data è lontana dalla sua etichetta.
    testo = "Data di nascita   Data assunzione\n\n\nRSSMRA80A01H501U\n01-01-1980   15-04-2021"
    risultato = mascherato(testo)
    assert "01-01-1980" not in risultato and "15-04-2021" in risultato


def test_data_di_nascita_dal_codice_fiscale_di_una_donna():
    # Giorno + 40 per le donne: 41 → 1.
    assert regole.data_dal_codice_fiscale("BNCNNA85M41L736X") == (1, 8, 85)


def test_codice_fiscale_con_un_carattere_in_piu_dopo_l_etichetta():
    testo = "residente in Asti codice fiscale RSSMRA80SA01H501U , e"
    (cf,) = [e for e in regole.trova(testo) if e.tipo == Tipo.CODICE_FISCALE]
    assert cf.valore == "RSSMRA80SA01H501U"


@pytest.mark.parametrize("testo", ["nata ad Asti (AT) il 21/05/1961", "nato ad Asti il 1/2/1970"])
def test_nata_ad(testo):
    risultato = mascherato(testo)
    assert "[LUOGO_NASCITA_1]" in risultato and "[DATA_NASCITA_1]" in risultato


def test_residente_con_indirizzo_a_capo():
    risultato = mascherato("la sig.ra Anna Bianchi residente in\nVia dei Tigli, Asti (AT)")
    assert "Tigli" not in risultato


@pytest.mark.parametrize(
    "testo, tipo",
    [
        ("Codice Cliente: 5550001234", "[CODICE_CLIENTE_1]"),
        ("Conto contrattuale 900011112222", "[CODICE_CLIENTE_1]"),
        ("C/C 000000123456 B 21", "[CONTO_1]"),
    ],
)
def test_codici_cliente_e_conto(testo, tipo):
    assert tipo in mascherato(testo)


def test_data_con_ora_non_e_un_telefono():
    assert regole.trova_telefoni("ASTI   03-05-2026 09:41") == []


@pytest.mark.parametrize("testo", ["Ferie -12,50000 ORE TOTALE", "ABI 01234  CAB 56789"])
def test_numeri_che_non_sono_cap(testo):
    assert regole.trova_indirizzi(testo) == []


@pytest.mark.parametrize(
    "testo", ["INPS   MINIMALE   LAVORATO", "Click & Pay, Bancomat Pay", "PIEMONTE Residuo  76,59"]
)
def test_parola_singola_maiuscola_non_mascherata(testo):
    assert all(e.azione != Azione.MASCHERA for e in nomi.trova(testo))


@pytest.mark.parametrize(
    "testo",
    ["Gamma spa, Autorizzazione Inail", "Eseguito ASTI AT 14100", "registrato ad Alba (CN)"],
)
def test_aziende_e_luoghi_non_sono_persone(testo):
    assert [e for e in nomi.trova(testo) if e.azione == Azione.MASCHERA] == []


def test_gentile_cliente_e_citta_restano():
    risultato = mascherato("Gentile Cliente, CITTÀ DI ALBA. Poiché l'iscrizione in Alba è valida.")
    assert "Cliente" in risultato and "Alba" in risultato


def test_matricola_sulla_riga_del_nome_e_del_codice_fiscale():
    testo = (
        "    0004321   ROSSI MARIO                RSSMRA80A01H501U 007788\n    Livello 4  1.257,46"
    )
    risultato = mascherato(testo)
    assert "0004321" not in risultato and "007788" not in risultato
    assert "1.257,46" in risultato and "Livello 4" in risultato


@pytest.mark.skipif(not ocr.disponibile(), reason="Tesseract non è installato")
def test_pagina_scansionata_di_traverso(tmp_path):
    righe = [
        "Modalita di pagamento della bolletta di prova",
        "Il sottoscritto Mario Rossi chiede la domiciliazione bancaria",
    ] * 6
    testo = pdf_di_testo(tmp_path / "t.pdf", righe)
    girata = tmp_path / "girata.pdf"
    scansiona(testo, girata, rotazione=90, rumore=0, sfocatura=0)
    estratto = estrai(girata)
    assert "Modalita di pagamento della bolletta di prova" in estratto.testo
