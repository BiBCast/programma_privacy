"""Test del riconoscimento dei nomi di persona (milestone M3). Solo dati inventati."""

import pytest

from anonimizzatore.rilevamento import nomi
from anonimizzatore.rilevamento.modelli import Tipo


def persone(testo):
    return sorted({e.valore for e in nomi.trova(testo) if e.tipo == Tipo.PERSONA})


def test_copia_per_il_modello_stessa_lunghezza_e_maiuscole_normalizzate():
    testo = "COGNOME E NOME    D'ANGELO MARIO    INPS"
    copia = nomi.testo_per_il_modello(testo)
    assert len(copia) == len(testo)
    assert "D'Angelo Mario" in copia
    assert "INPS" in copia  # le sigle restano maiuscole
    assert "\n" in copia  # le colonne sono separate


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("Il ricorrente Mario Rossi chiede la riforma della sentenza.", ["Mario Rossi"]),
        ("COGNOME E NOME    BIANCHI ANNA    MATRICOLA    004512", ["BIANCHI ANNA"]),
        (
            "Hanno firmato Ermenegildo Colombo e Giulia Ferri.",
            ["Ermenegildo Colombo", "Giulia Ferri"],
        ),
        ("ESPOSITO GENNARO", ["ESPOSITO GENNARO"]),
        ("Gentile Anna Gentile, le scriviamo.", ["Anna Gentile"]),
    ],
)
def test_persone_trovate(testo, atteso):
    assert persone(testo) == atteso


def test_il_nome_si_ferma_alla_colonna_successiva():
    assert persone("Bianchi Anna    Matricola 0045") == ["Bianchi Anna"]


@pytest.mark.parametrize(
    "testo",
    [
        "TRIBUNALE ORDINARIO DI PADOVA",
        "La pratica è passata all'INPS e all'INAIL, con trattenuta IRPEF e TFR.",
        "Alfa S.r.l. e Luigi Pirandello Società Cooperativa hanno firmato.",
        "La Banca Popolare di Vicenza e Poste Italiane comunicano.",
    ],
)
def test_non_sono_persone(testo):
    assert persone(testo) == []


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("In data odierna Ngozi Caruso ha consegnato i documenti.", ["Ngozi Caruso"]),
        ("Elenco presenti: Valle Ofelia; Rossi Mario.", ["Rossi Mario", "Valle Ofelia"]),
        ("Gentile Zeno Valle, le scriviamo.", ["Zeno Valle"]),
    ],
)
def test_coppia_con_un_cognome_noto(testo, atteso):
    assert persone(testo) == atteso


@pytest.mark.parametrize(
    "testo",
    ["Si riunisce la Sala Consiliare.", "Vista sul Monte Bianco.", "Hotel Costa Smeralda"],
)
def test_luoghi_con_un_cognome_non_sono_persone(testo):
    assert persone(testo) == []


def test_possibili_nomi_segnalati_e_non_mascherati():
    testo = "In data odierna Oluwaseun Mokoena e la Sala Consiliare; Via Garibaldi; Regolamento UE."
    trovate = nomi.trova(testo)
    assert trovate == []  # né il modello né gli elenchi conoscono questo nome
    (possibile,) = nomi.possibili(testo, trovate)
    assert possibile.valore == "Oluwaseun Mokoena"
    assert possibile.azione == "segnala" and possibile.nota


@pytest.mark.parametrize(
    "testo",
    [
        "Con Riferimento Alla Vostra Richiesta Del Mese Scorso.",
        "IL DIPENDENTE DICHIARA DI AVER RICEVUTO LA SOMMA INDICATA IN BUSTA.",
        "Alfa Beta S.r.l. comunica.",
    ],
)
def test_possibili_nomi_senza_rumore(testo):
    assert nomi.possibili(testo, nomi.trova(testo)) == []


def test_ogni_valore_corrisponde_al_testo():
    testo = "Il sig. Mario Rossi e la dott.ssa TERESA MARCHETTI hanno firmato."
    trovate = nomi.trova(testo)
    assert trovate and all(testo[e.inizio : e.fine] == e.valore for e in trovate)
