"""Test della risoluzione delle sovrapposizioni (milestone M4)."""

from anonimizzatore.rilevamento.modelli import Azione, Entita, Priorita, Tipo
from anonimizzatore.rilevamento.risoluzione import risolvi


def entita(inizio, fine, tipo=Tipo.PERSONA, priorita=Priorita.NER, azione=Azione.MASCHERA):
    return Entita(inizio, fine, tipo, "x" * (fine - inizio), "prova", priorita, azione)


def test_vince_la_priorita_piu_alta():
    cf = entita(0, 16, Tipo.CODICE_FISCALE, Priorita.REGOLA_VALIDATA)
    persona = entita(0, 20, Tipo.PERSONA, Priorita.ETICHETTA)
    assert risolvi([persona, cf]) == [cf]


def test_a_parita_di_priorita_vince_la_piu_lunga():
    corta, lunga = entita(0, 5), entita(0, 11)
    assert risolvi([corta, lunga]) == [lunga]


def test_una_segnalazione_non_blocca_un_dato_da_mascherare():
    indirizzo = entita(0, 20, Tipo.INDIRIZZO, Priorita.REGOLA, Azione.SEGNALA)
    residenza = entita(0, 18, Tipo.INDIRIZZO, Priorita.ETICHETTA, Azione.MASCHERA)
    assert risolvi([indirizzo, residenza]) == [residenza]


def test_segnalazioni_che_non_toccano_nulla_restano():
    nome = entita(0, 10)
    sensibile = entita(20, 28, Tipo.DATO_SALUTE, Priorita.SEGNALAZIONE, Azione.SEGNALA)
    assert risolvi([sensibile, nome]) == [nome, sensibile]


def test_esclusione_dell_utente_blocca_tutto_cio_che_tocca():
    escluso = entita(0, 12, Tipo.DATO, Priorita.UTENTE, Azione.ESCLUDI)
    nome = entita(7, 12, Tipo.PERSONA, Priorita.REGOLA_VALIDATA)
    altro = entita(15, 20)
    assert risolvi([escluso, nome, altro]) == [altro]
