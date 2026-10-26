"""Test del motore completo (milestone M4). Solo dati inventati."""

import json
import socket

import pytest

from anonimizzatore import cli
from anonimizzatore.motore import NOTA_PER_AI, analizza, analizza_file, applica, legenda, riepilogo
from generatori.corpus import genera
from generatori.word import crea_docx, paragrafo, run

BUSTA_PAGA = """Alfa S.r.l. - Via Industria 12, 30100 Venezia (VE) - P.IVA 01234567897
Cognome: BIANCHI          Nome: ANNA          Matricola: 004512
Codice fiscale      BNCNNA85M41L736X      Livello     3
Residente in Via dei Mille 8, 30170 Mestre (VE) - Tel. 347 1234567 - anna.bianchi@esempio.it
Voci: Retribuzione 1.854,30 - Malattia dal 3 al 10 ottobre - Trattenuta sindacale CGIL 12,50
IBAN IT60X0542811101000000123456
La collega Bianchi Anna conferma."""

DATI_PERSONALI = [
    "BIANCHI",
    "ANNA",
    "004512",
    "BNCNNA85M41L736X",
    "Via dei Mille 8",
    "347 1234567",
    "anna.bianchi@esempio.it",
    "IT60X0542811101000000123456",
    "Bianchi Anna",
]


def test_busta_paga_senza_dati_personali_e_con_dati_utili():
    analisi = analizza(BUSTA_PAGA)
    risultato = applica(analisi, nota_per_ai=False)
    for dato in DATI_PERSONALI:
        assert dato not in risultato
    # Restano i dati che servono all'AI: azienda, importi, voci, livello.
    for utile in ("Alfa S.r.l.", "1.854,30", "Retribuzione", "Livello     3", "Malattia"):
        assert utile in risultato
    # "Cognome: BIANCHI" + "Nome: ANNA" e "Bianchi Anna" sono la stessa persona.
    assert risultato.count("[PERSONA_1]") == 3 and "[PERSONA_2]" not in risultato


def test_segnalazioni_restano_nel_testo():
    analisi = analizza(BUSTA_PAGA)
    segnalati = {d.entita.valore for d in analisi.segnalati}
    assert {"Malattia", "CGIL", "01234567897"} <= segnalati
    assert all(d.segnaposto == "" for d in analisi.segnalati)


def test_nota_per_l_ai_in_testa():
    risultato = applica(analizza("Il sig. Mario Rossi firma."))
    assert risultato.startswith(NOTA_PER_AI)
    assert risultato.endswith("Il sig. [PERSONA_1] firma.")


def test_legenda_solo_per_l_utente():
    analisi = analizza("Il sig. Mario Rossi firma. Rossi conferma.")
    assert legenda(analisi) == [("[PERSONA_1]", "Mario Rossi"), ("[PERSONA_1]", "Rossi")]


def test_riepilogo_senza_valori_originali():
    testo = json.dumps(riepilogo(analizza(BUSTA_PAGA)), ensure_ascii=False)
    for dato in [*DATI_PERSONALI, "Malattia", "01234567897"]:
        assert dato not in testo


def test_analisi_di_un_file_word(tmp_path):
    percorso = crea_docx(tmp_path / "lettera.docx", paragrafo(run("Gentile Mario Rossi, ciao.")))
    risultato = applica(analizza_file(percorso), nota_per_ai=False)
    assert risultato == "Gentile [PERSONA_1], ciao."


# --- Privacy ----------------------------------------------------------------------------------


def test_analisi_senza_rete(monkeypatch):
    def vietata(*args, **kwargs):
        raise AssertionError("L'analisi ha provato ad aprire una connessione di rete.")

    monkeypatch.setattr(socket, "socket", vietata)
    monkeypatch.setattr(socket, "create_connection", vietata)
    applica(analizza(BUSTA_PAGA))


def test_analisi_senza_file_scritti(tmp_path, monkeypatch, elenchi_utente_isolati):
    monkeypatch.chdir(tmp_path)
    prima = set(tmp_path.rglob("*"))
    applica(analizza(BUSTA_PAGA))
    assert set(tmp_path.rglob("*")) == prima
    assert not elenchi_utente_isolati.exists()


# --- Riga di comando --------------------------------------------------------------------------


def test_riga_di_comando(tmp_path, capsys):
    documento = tmp_path / "busta.txt"
    documento.write_text(BUSTA_PAGA, encoding="utf-8")
    uscita, report = tmp_path / "anonimo.txt", tmp_path / "report.json"
    codice = cli.main([str(documento), "--out", str(uscita), "--report", str(report)])
    assert codice == 0
    risultato = uscita.read_text(encoding="utf-8")
    assert risultato.startswith(NOTA_PER_AI) and "BNCNNA85M41L736X" not in risultato
    assert "BNCNNA85M41L736X" not in report.read_text(encoding="utf-8")
    assert "dati mascherati" in capsys.readouterr().err


def test_riga_di_comando_con_documento_non_supportato(tmp_path, capsys):
    documento = tmp_path / "vecchio.doc"
    documento.write_bytes(b"qualsiasi")
    assert cli.main([str(documento)]) == 2
    assert ".docx" in capsys.readouterr().err


# --- Corpus -----------------------------------------------------------------------------------


@pytest.mark.parametrize("seme", [7])
def test_corpus_nessun_nome_resta_nel_testo_finale(seme):
    totale = spariti = 0
    for documento in genera(200, seme):
        risultato = applica(analizza(documento.testo), nota_per_ai=False)
        for inizio, fine in documento.nomi:
            totale += 1
            spariti += documento.testo[inizio:fine] not in risultato
    assert spariti / totale >= 0.95, f"{spariti}/{totale}"
