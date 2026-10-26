"""Test degli elenchi personali dell'utente (milestone M4)."""

from anonimizzatore import elenchi_utente
from anonimizzatore.motore import analizza, applica


def test_senza_cartella_gli_elenchi_sono_vuoti(elenchi_utente_isolati):
    assert not elenchi_utente_isolati.exists()
    assert elenchi_utente.carica() == elenchi_utente.ElenchiUtente()
    assert not elenchi_utente_isolati.exists()  # leggere non crea niente


def test_prepara_crea_i_file_con_le_istruzioni(elenchi_utente_isolati):
    elenchi_utente.prepara()
    nomi = sorted(p.name for p in elenchi_utente_isolati.iterdir())
    assert nomi == [elenchi_utente.MAI, elenchi_utente.SENSIBILI, elenchi_utente.SEMPRE]
    assert elenchi_utente.carica() == elenchi_utente.ElenchiUtente()  # solo commenti


def test_voci_lette_senza_commenti_ne_doppioni(elenchi_utente_isolati):
    elenchi_utente.prepara()
    (elenchi_utente_isolati / elenchi_utente.SEMPRE).write_text(
        "# clienti\nZeta Gamma\n\nCOD-7781\nZeta Gamma\n", encoding="utf-8"
    )
    assert elenchi_utente.carica().sempre == ("Zeta Gamma", "COD-7781")


def test_sempre_e_mai_nel_motore():
    elenchi = elenchi_utente.ElenchiUtente(
        sempre=("Ottone Brambilla", "COD-7781"), mai=("Studio Mario Rossi",)
    )
    testo = "Pratica COD-7781 di Ottone Brambilla, seguita dallo Studio Mario Rossi."
    risultato = applica(analizza(testo, elenchi=elenchi), nota_per_ai=False)
    assert risultato == "Pratica [DATO_1] di [PERSONA_1], seguita dallo Studio Mario Rossi."
