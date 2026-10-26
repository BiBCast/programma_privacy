"""Test dei dati dopo un'etichetta (milestone M2). Solo dati inventati."""

import pytest

from anonimizzatore.rilevamento import etichette
from anonimizzatore.rilevamento.modelli import Azione, Tipo


def valori(testo, tipo):
    return [e.valore for e in etichette.trova(testo) if e.tipo == tipo]


def test_busta_paga_a_colonne():
    testo = "Cognome e nome      ROSSI MARIO      Matricola   000123\nQualifica   Impiegato"
    assert valori(testo, Tipo.PERSONA) == ["ROSSI MARIO"]
    assert valori(testo, Tipo.MATRICOLA) == ["000123"]


def test_cognome_e_nome_separati():
    assert valori("Cognome: Rossi | Nome: Mario", Tipo.PERSONA) == ["Rossi", "Mario"]


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("Dipendente: Mario Rossi, nato a Padova", "Mario Rossi"),
        ("Il Sig. Mario Rossi ha firmato", "Mario Rossi"),
        ("Gent.mo Sig. Mario Rossi,", "Mario Rossi"),
        ("assistito dall'Avv. Anna De Luca del foro", "Anna De Luca"),
        ("Il sottoscritto Mario Rossi, nato a Padova", "Mario Rossi"),
        ("la sottoscritta Dott.ssa Anna Bianchi dichiara", "Anna Bianchi"),
        ("Il sottoscritto Mario Rossi.", "Mario Rossi"),
        ("Nominativo: M. Rossi", "M. Rossi"),
    ],
)
def test_persone(testo, atteso):
    assert valori(testo, Tipo.PERSONA) == [atteso]


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("Il ricorrente Bolat Tane chiede", "Bolat Tane"),
        ("assistito dall'avv. Kiri Kealoha, conviene", "Kiri Kealoha"),
        ("Alfa S.r.l., in persona del legale rappresentante Nalani Dorje,", "Nalani Dorje"),
        ("conviene in giudizio Ayelet Ozturk", "Ayelet Ozturk"),
        ("Testimone: Oluwaseun Adebayo", "Oluwaseun Adebayo"),
        ("il resistente Mario Rossi si è costituito", "Mario Rossi"),
        ("IL SIGNOR OLUWASEUN MOKOENA DICHIARA DI AVER RICEVUTO", "OLUWASEUN MOKOENA"),
    ],
)
def test_ruoli_degli_atti(testo, atteso):
    assert valori(testo, Tipo.PERSONA) == [atteso]


@pytest.mark.parametrize(
    "testo",
    [
        "Il ricorrente, nato a Padova, chiede",
        "ricorso contro Beta S.p.A.",
        "denuncia contro Ignoti",
    ],
)
def test_ruoli_degli_atti_senza_nome(testo):
    assert valori(testo, Tipo.PERSONA) == []


def test_piu_titoli_nella_stessa_frase():
    testo = "La signora Marchetti e il dott. Fabbri hanno firmato; il sig. Mario Ferrara no."
    assert valori(testo, Tipo.PERSONA) == ["Marchetti", "Fabbri", "Mario Ferrara"]


@pytest.mark.parametrize(
    "testo",
    [
        "Nome del file: prova.txt",
        "Cognome e nome   Qualifica   Livello",
        "Dipendente: Alfa S.r.l.",
        "il dipendente si impegna a rispettare",
        "Sig. Il presente atto",
    ],
)
def test_non_sono_persone(testo):
    assert valori(testo, Tipo.PERSONA) == []


def test_dati_di_nascita():
    testo = "Data di nascita: 12/03/1975   Luogo di nascita: Padova (PD)"
    assert valori(testo, Tipo.DATA_NASCITA) == ["12/03/1975"]
    assert valori(testo, Tipo.LUOGO_NASCITA) == ["Padova"]


def test_residenza_mascherata_e_telefono():
    testo = "Residente in Via Roma 5, Padova; tel. 333 1234567"
    (indirizzo,) = [e for e in etichette.trova(testo) if e.tipo == Tipo.INDIRIZZO]
    assert indirizzo.valore == "Via Roma 5, Padova" and indirizzo.azione == Azione.MASCHERA
    assert valori(testo, Tipo.TELEFONO) == ["333 1234567"]


def test_indirizzo_generico_resta_da_valutare():
    (indirizzo,) = [
        e for e in etichette.trova("Indirizzo: Via Verdi 3") if e.tipo == Tipo.INDIRIZZO
    ]
    assert indirizzo.valore == "Via Verdi 3" and indirizzo.azione == Azione.SEGNALA


def test_ogni_valore_corrisponde_al_testo():
    testo = "Cognome e nome:  BIANCHI ANNA   Matr. 4567   Tel.: 049 8765432"
    trovate = etichette.trova(testo)
    assert trovate and all(testo[e.inizio : e.fine] == e.valore for e in trovate)
