"""Test della propagazione dei nomi a tutto il testo (milestone M3). Solo dati inventati."""

from anonimizzatore.rilevamento import propagazione, regole
from anonimizzatore.rilevamento.modelli import Entita, Priorita, Tipo


def persona(testo, valore, da=0):
    inizio = testo.index(valore, da)
    return Entita(inizio, inizio + len(valore), Tipo.PERSONA, valore, "ner", Priorita.NER)


def test_cognome_e_nome_ritrovati_ovunque_con_la_stessa_chiave():
    testo = "Mario Rossi ha firmato. Il sig. Rossi conferma. ROSSI MARIO. Mario arriva."
    nuove = propagazione.applica(testo, [persona(testo, "Mario Rossi")])
    assert [e.valore for e in nuove] == ["Rossi", "ROSSI MARIO", "Mario"]
    assert {e.persona for e in nuove} == {"mario rossi"}
    assert all(e.fonte == "propagazione" and e.nota == "" for e in nuove)


def test_solo_occorrenze_con_iniziale_maiuscola():
    testo = "Rosa Bianchi ha scelto la lista rosa e il vino bianchi."
    nuove = propagazione.applica(testo, [persona(testo, "Rosa Bianchi")])
    assert nuove == []


def test_omonimia_segnalata_e_scelta_la_persona_piu_vicina():
    testo = "Mario Rossi e Anna Rossi sono fratelli. Poi Anna Rossi parla. Infine Rossi tace."
    trovate = [persona(testo, "Mario Rossi"), persona(testo, "Anna Rossi")]
    (rossi,) = [e for e in propagazione.applica(testo, trovate) if e.valore == "Rossi"]
    assert rossi.persona == "anna rossi"
    assert "anna rossi" in rossi.nota and "mario rossi" in rossi.nota


def test_forma_breve_della_stessa_persona_non_e_omonimia():
    testo = "Il sig. Rossi, cioè Mario Rossi, firma. Rossi conferma."
    trovate = [persona(testo, "Rossi"), persona(testo, "Mario Rossi")]
    (ultima,) = propagazione.applica(testo, trovate)
    assert ultima.persona == "mario rossi" and ultima.nota == ""


def test_non_tocca_le_altre_entita():
    testo = "Mario Rossi abita in Via Mario Rossi 5."
    trovate = [persona(testo, "Mario Rossi"), *regole.trova_indirizzi(testo)]
    assert propagazione.applica(testo, trovate) == []


def test_cognome_che_e_una_citta_non_si_propaga_dopo_una_preposizione():
    testo = "Mario Ferrara, nato a Ferrara, vive in Ferrara. Ferrara firma."
    nuove = propagazione.applica(testo, [persona(testo, "Mario Ferrara")])
    assert [e.valore for e in nuove] == ["Ferrara"]
    assert nuove[0].inizio == testo.rindex("Ferrara")


def test_cognome_che_e_una_parola_comune_si_propaga():
    testo = "Il collega Zeno Gentile era assente. Gentile conferma."
    nuove = propagazione.applica(testo, [persona(testo, "Zeno Gentile")])
    assert [(e.valore, e.persona) for e in nuove] == [("Gentile", "gentile zeno")]


def test_persone_vicine_diverse_trattate_una_per_una():
    testo = "Mario Rossi e Anna Bianchi. Poi Rossi Bianchi parlano."
    trovate = [persona(testo, "Mario Rossi"), persona(testo, "Anna Bianchi")]
    nuove = propagazione.applica(testo, trovate)
    assert [(e.valore, e.persona) for e in nuove] == [
        ("Rossi", "mario rossi"),
        ("Bianchi", "anna bianchi"),
    ]
