"""Test dei segnaposto coerenti (milestone M4). Solo dati inventati."""

from anonimizzatore import pseudonimi
from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo


def entita(testo, valore, tipo=Tipo.PERSONA, da=0, persona="", azione=Azione.MASCHERA):
    inizio = testo.index(valore, da)
    return Entita(
        inizio, inizio + len(valore), tipo, valore, "prova", Priorita.NER, azione, persona
    )


def test_stessa_persona_scritta_in_modi_diversi():
    testo = "Mario Rossi. ROSSI MARIO. Il sig. Rossi. Anna Bianchi."
    trovate = [
        entita(testo, "Mario Rossi"),
        entita(testo, "ROSSI MARIO"),
        entita(testo, "Rossi", da=testo.index("sig.")),
        entita(testo, "Anna Bianchi"),
    ]
    assert pseudonimi.assegna(trovate) == ["[PERSONA_1]"] * 3 + ["[PERSONA_2]"]


def test_omonimia_risolta_con_la_persona_piu_vicina():
    testo = "Mario Rossi parla. Poi Anna Rossi risponde e Rossi annuisce."
    trovate = [
        entita(testo, "Mario Rossi"),
        entita(testo, "Anna Rossi"),
        entita(testo, "Rossi", da=testo.index("e Rossi")),
    ]
    assert pseudonimi.assegna(trovate) == ["[PERSONA_1]", "[PERSONA_2]", "[PERSONA_2]"]


def test_chiave_indicata_dalla_propagazione_o_da_cognome_e_nome():
    testo = "Cognome: Bianchi Nome: Anna. Anna Bianchi firma."
    trovate = [
        entita(testo, "Bianchi", persona="anna bianchi"),
        entita(testo, "Anna", persona="anna bianchi"),
        entita(testo, "Anna Bianchi"),
    ]
    assert set(pseudonimi.assegna(trovate)) == {"[PERSONA_1]"}


def test_codici_normalizzati_e_numerati_per_tipo():
    testo = (
        "IBAN IT60X0542811101000000123456, poi IT60 X054 2811 1010 0000 0123 456; "
        "tel. +39 347 1234567 e 3471234567; CF RSSMRA80A01H501U"
    )
    trovate = [
        entita(testo, "IT60X0542811101000000123456", Tipo.IBAN),
        entita(testo, "IT60 X054 2811 1010 0000 0123 456", Tipo.IBAN),
        entita(testo, "+39 347 1234567", Tipo.TELEFONO),
        entita(testo, "3471234567", Tipo.TELEFONO),
        entita(testo, "RSSMRA80A01H501U", Tipo.CODICE_FISCALE),
    ]
    assert pseudonimi.assegna(trovate) == [
        "[IBAN_1]",
        "[IBAN_1]",
        "[TELEFONO_1]",
        "[TELEFONO_1]",
        "[CODICE_FISCALE_1]",
    ]


def test_segnalazioni_senza_segnaposto():
    testo = "Malattia di Mario Rossi"
    trovate = [
        entita(testo, "Malattia", Tipo.DATO_SALUTE, azione=Azione.SEGNALA),
        entita(testo, "Mario Rossi"),
    ]
    assert pseudonimi.assegna(trovate) == ["", "[PERSONA_1]"]


def test_numeri_nell_ordine_di_prima_comparsa():
    testo = "Anna Bianchi, poi Mario Rossi, poi di nuovo Anna Bianchi."
    trovate = [
        entita(testo, "Mario Rossi"),
        entita(testo, "Anna Bianchi", da=20),
        entita(testo, "Anna Bianchi"),
    ]
    assert pseudonimi.assegna(trovate) == ["[PERSONA_2]", "[PERSONA_1]", "[PERSONA_1]"]
