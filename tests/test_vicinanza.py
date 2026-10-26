"""Test della regola di vicinanza per partite IVA e indirizzi (milestone M2)."""

from anonimizzatore.rilevamento import etichette, regole, vicinanza
from anonimizzatore.rilevamento.modelli import Azione, Tipo
from test_regole import PIVA


def azioni(testo, tipo):
    entita = vicinanza.applica(testo, regole.trova(testo) + etichette.trova(testo))
    return [e.azione for e in entita if e.tipo == tipo and e.fonte == "regola"]


def test_piva_vicina_a_una_persona_si_maschera():
    assert azioni(f"Dipendente: Mario Rossi, P.IVA {PIVA}", Tipo.PARTITA_IVA) == [Azione.MASCHERA]


def test_piva_di_societa_resta_segnalata():
    testo = f"Alfa S.r.l., P.IVA {PIVA}\n" + "\n" * 3 + "Dipendente: " + "x" * 90 + " Mario Rossi"
    assert azioni(testo, Tipo.PARTITA_IVA) == [Azione.SEGNALA]


def test_intestazione_di_azienda_con_dipendente_nella_riga_sotto():
    testo = (
        f"Alfa S.r.l. - Via Industria 12, 30100 Venezia (VE) - P.IVA {PIVA}\n"
        "Cognome e nome      BIANCHI ANNA          Matricola   004512"
    )
    assert azioni(testo, Tipo.PARTITA_IVA) == [Azione.SEGNALA]
    assert azioni(testo, Tipo.INDIRIZZO) == [Azione.SEGNALA]


def test_residente_basta_anche_senza_persona():
    assert azioni("residente in Via Verdi 3", Tipo.INDIRIZZO) == [Azione.MASCHERA]


def test_sede_di_azienda_resta_segnalata_anche_vicino_a_una_persona():
    testo = "Sig. Mario Rossi, legale rappresentante di Alfa S.r.l. con sede in Via Roma 5"
    assert azioni(testo, Tipo.INDIRIZZO) == [Azione.SEGNALA]


def test_indirizzo_lontano_dalle_persone_resta_segnalato():
    testo = "Sig. Mario Rossi" + "\n" + "testo " * 30 + "\nconsegna in Via Roma 5"
    assert azioni(testo, Tipo.INDIRIZZO) == [Azione.SEGNALA]


def test_stessa_riga_di_una_busta_paga():
    testo = "ROSSI MARIO" + " " * 100 + "Via Verdi 3"
    persona = etichette.trova("Cognome e nome:  ROSSI MARIO")[0]
    # La persona della riga arriverà dal riconoscimento dei nomi (M3): qui la si simula.
    persona = type(persona)(0, 11, Tipo.PERSONA, "ROSSI MARIO", "ner", 50)
    entita = vicinanza.applica(testo, [persona, *regole.trova_indirizzi(testo)])
    assert [e.azione for e in entita if e.tipo == Tipo.INDIRIZZO] == [Azione.MASCHERA]
