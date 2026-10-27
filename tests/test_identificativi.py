"""Test degli identificativi aggiunti in M4b. Solo dati inventati: le carte usano i numeri di
prova pubblicati dai circuiti, le targhe e i codici sono di fantasia."""

from datetime import date

import pytest

from anonimizzatore.motore import _minori, analizza, applica
from anonimizzatore.rilevamento import identificativi as ident
from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo


def valori(entita, tipo=None):
    return [e.valore for e in entita if tipo is None or e.tipo == tipo]


def mascherato(testo):
    return applica(analizza(testo), nota_per_ai=False)


# --- Carte ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("pagato con 4111 1111 1111 1111 il 3 marzo", "4111 1111 1111 1111"),  # Visa di prova
        ("carta di credito n. 5555555555554444", "5555555555554444"),  # Mastercard di prova
        ("Amex: 378282246310005", "378282246310005"),  # American Express di prova
    ],
)
def test_carte_trovate(testo, atteso):
    assert valori(ident.trova_carte(testo)) == [atteso]


@pytest.mark.parametrize(
    "testo",
    [
        "Codice bolletta: 420268543007796577",  # 18 cifre che iniziano per 4: non è una Visa
        "numero 4111111111111111 senza etichetta e senza gruppi",
        "4111 1111 1111 1112",  # controllo di Luhn errato
        "IBAN IT60 X054 2811 1010 0000 0123 456",
    ],
)
def test_non_sono_carte(testo):
    assert ident.trova_carte(testo) == []


# --- Tessera sanitaria e targhe ---------------------------------------------------------------


def test_tessera_sanitaria():
    # 20 cifre: 80380 + 15.
    assert valori(ident.trova_tessere_sanitarie("TEAM 80380 00001 23456 78901")) == [
        "80380 00001 23456 78901"
    ]
    assert valori(ident.trova_tessere_sanitarie("Tessera sanitaria n. 1234567890")) == [
        "1234567890"
    ]


def test_targa_con_etichetta_mascherata_senza_segnalata():
    (con,) = ident.trova_targhe("veicolo targato AB 123 CD")
    (senza,) = ident.trova_targhe("codice articolo FG456HJ")
    assert con.azione == Azione.MASCHERA and con.valore == "AB 123 CD"
    assert senza.azione == Azione.SEGNALA


def test_non_sono_targhe():
    assert ident.trova_targhe("modello IO123QU") == []  # I, O, Q, U non si usano


# --- Procedimenti, polizze, telefoni esteri ---------------------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("causa iscritta al R.G. n. 1234/2025", "1234/2025"),
        ("proc. pen. R.G.N.R. 5678/24", "5678/24"),
        ("procedimento n. 42/2026 davanti al giudice", "42/2026"),
        ("n. 1234/2025 R.G. del Tribunale", "1234/2025"),
        ("ruolo generale n. 999/2023", "999/2023"),
    ],
)
def test_procedimenti(testo, atteso):
    assert valori(ident.trova_procedimenti(testo)) == [atteso]


def test_citazioni_di_giurisprudenza_restano():
    assert ident.trova_procedimenti("come affermato da Cass. n. 1234/2020") == []


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("Polizza n. RCA-2025-00123", "RCA-2025-00123"),
        ("numero sinistro 2026/778899", "2026/778899"),
        ("pratica n. 45/7788", "45/7788"),
    ],
)
def test_polizze_e_pratiche(testo, atteso):
    assert valori(ident.trova_polizze(testo)) == [atteso]


@pytest.mark.parametrize(
    "numero", ["+44 20 7946 0958", "+49 30 1234 5678", "0033 1 23 45 67 89", "+1 (555) 123-4567"]
)
def test_telefoni_esteri(numero):
    assert valori(ident.trova_telefoni_esteri(f"chiamare il {numero} grazie")) == [numero]


def test_telefono_italiano_non_e_estero():
    assert ident.trova_telefoni_esteri("+39 333 1234567") == []


# --- Identificativi online --------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("accesso dall'IP 192.168.1.20 alle 10", "192.168.1.20"),
        ("indirizzo 2001:db8:85a3::8a2e:370:7334", "2001:db8:85a3::8a2e:370:7334"),
        (
            "profilo https://www.linkedin.com/in/mario-rossi-123 aggiornato",
            "https://www.linkedin.com/in/mario-rossi-123",
        ),
        ("scrivere a @mario_rossi85 su Instagram", "@mario_rossi85"),
    ],
)
def test_identificativi_online(testo, atteso):
    assert valori(ident.trova_identificativi_online(testo)) == [atteso]


def test_non_sono_identificativi_online():
    for testo in ("versione 1.2.3", "ore 14:27", "mario.rossi@esempio.it", "importo 1.234.567"):
        assert ident.trova_identificativi_online(testo) == []


def test_url_con_il_nome_di_una_persona():
    risultato = mascherato(
        "Il sig. Mario Rossi pubblica su www.esempio.it/blog/mario-rossi ogni mese."
    )
    assert "mario-rossi" not in risultato and "[ID_ONLINE_1]" in risultato


# --- Età, data di morte, codice fiscale numerico, minori --------------------------------------


@pytest.mark.parametrize(
    "testo, atteso",
    [("Mario Rossi, di anni 45, residente", "45"), ("un 32enne di Asti", "32"), ("età: 71", "71")],
)
def test_eta_segnalata(testo, atteso):
    (eta,) = ident.trova_eta(testo)
    assert eta.valore == atteso and eta.azione == Azione.SEGNALA


def test_durate_non_sono_eta():
    assert ident.trova_eta("il contratto dura da 5 anni") == []


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("deceduto il 12/03/2021", "12/03/2021"),
        ("deceduta a Asti il 1 marzo 2020", "1 marzo 2020"),
        ("data di morte: 05.06.2019", "05.06.2019"),
    ],
)
def test_data_di_morte(testo, atteso):
    assert valori(ident.trova_date_di_morte(testo)) == [atteso]


def test_codice_fiscale_numerico_di_persona_mascherato_di_societa_segnalato():
    persona = analizza("Il sig. Mario Rossi, codice fiscale 12345678901, dichiara")
    societa = analizza("Alfa S.r.l., codice fiscale 12345678901")
    (cf_persona,) = [d for d in persona.dati if d.entita.tipo == Tipo.CODICE_FISCALE]
    (cf_societa,) = [d for d in societa.dati if d.entita.tipo == Tipo.CODICE_FISCALE]
    assert cf_persona.entita.azione == Azione.MASCHERA
    assert cf_societa.entita.azione == Azione.SEGNALA


def test_minore_riconosciuto_dal_codice_fiscale():
    # RSSMRA12A01H501?: nato il 1 gennaio 2012 (il carattere di controllo qui non conta).
    minore = Entita(0, 16, Tipo.CODICE_FISCALE, "RSSMRA12A01H501X", "regola", Priorita.REGOLA)
    adulto = Entita(0, 16, Tipo.CODICE_FISCALE, "RSSMRA80A01H501U", "regola", Priorita.REGOLA)
    (con_nota,), avviso = _minori([minore], oggi=date(2026, 10, 27))
    (senza_nota,), nessun_avviso = _minori([adulto], oggi=date(2026, 10, 27))
    assert "art. 8" in con_nota.nota and "minore" in avviso
    assert senza_nota.nota == "" and nessun_avviso == ""


def test_segnaposto_dei_nuovi_tipi():
    risultato = mascherato(
        "Carta 4111 1111 1111 1111, targa AB 123 CD del veicolo targato AB123CD, R.G. n. 1/2025"
    )
    assert risultato.count("[CARTA_1]") == 1 and "[PROCEDIMENTO_1]" in risultato
