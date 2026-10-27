"""Test delle segnalazioni di dati sensibili e giudiziari (milestone M4)."""

import pytest

from anonimizzatore.rilevamento import sensibili
from anonimizzatore.rilevamento.modelli import Azione, Tipo


def trovati(testo, parole_utente=()):
    return [(e.tipo, e.valore) for e in sensibili.trova(testo, parole_utente)]


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("assenza per malattie varie", (Tipo.DATO_SALUTE, "malattie")),
        ("permessi Legge 104 mensili", (Tipo.DATO_SALUTE, "Legge 104")),
        ("Trattenuta  sindacale mensile", (Tipo.DATO_SINDACALE, "Trattenuta  sindacale")),
        ("iscritto alla CGIL", (Tipo.DATO_SINDACALE, "CGIL")),
        ("procedimento penale n. 12", (Tipo.DATO_GIUDIZIARIO, "procedimento penale")),
        ("hanno contratto unione civile", (Tipo.DATO_SESSUALE, "unione civile")),
    ],
)
def test_parole_sensibili(testo, atteso):
    assert atteso in trovati(testo)


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("affetto da diabete di tipo 2", (Tipo.DATO_SALUTE, "diabete")),
        ("in cura presso il SerD di zona", (Tipo.DATO_SALUTE, "SerD")),
        (
            "percepisce l'indennità di accompagnamento",
            (Tipo.DATO_SALUTE, "indennità di accompagnamento"),
        ),
        ("di religione musulmana", (Tipo.DATO_RELIGIOSO, "musulmana")),
        ("candidato per Fratelli d'Italia", (Tipo.DATO_POLITICO, "Fratelli d'Italia")),
        ("delega sindacale alla FILCAMS", (Tipo.DATO_SINDACALE, "FILCAMS")),
        (
            "condannato per appropriazione indebita",
            (Tipo.DATO_GIUDIZIARIO, "appropriazione indebita"),
        ),
        ("ai sensi dell'art. 640 c.p. e seguenti", (Tipo.DATO_GIUDIZIARIO, "c.p.")),
    ],
)
def test_parole_degli_elenchi_estesi(testo, atteso):
    assert atteso in trovati(testo)


@pytest.mark.parametrize(
    "testo",
    [
        "il sig. Cristian Bianchi",  # nome proprio, non religione
        "trasferito a Roma",  # "rom" solo come parola intera
        "Padova (PD)",  # sigla di provincia, non partito
        "acquistato in farmacia",
        "art. 1218 c.p.c.",  # codice di procedura civile, non penale
        "lega di alluminio",
    ],
)
def test_parole_ambigue_non_segnalate(testo):
    assert trovati(testo) == []


def test_sigle_cercate_solo_maiuscole():
    assert trovati("collegare la chiavetta alla porta usb") == []
    assert trovati("delegato USB") == [(Tipo.DATO_SINDACALE, "USB")]


def test_parole_intere():
    assert trovati("il reatore nucleare") == []


def test_sono_segnalazioni_con_nota():
    (dato,) = sensibili.trova("malattia")
    assert dato.azione == Azione.SEGNALA and "art. 9" in dato.nota


def test_parole_dell_utente():
    assert trovati("visita dal dietologo", ("dietolog*",)) == [(Tipo.DATO_SENSIBILE, "dietologo")]


def test_mascherare_con_il_dettaglio():
    testo = "Assenza per malattia dal 3 al 10 marzo, poi ferie."
    (dato,) = sensibili.trova(testo)
    allargato = sensibili.con_dettaglio(testo, dato)
    assert allargato.valore == "malattia dal 3 al 10 marzo"
    assert allargato.azione == Azione.MASCHERA
