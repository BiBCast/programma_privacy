"""Test della milestone M1: estrazione del testo. Solo dati inventati."""

import re
import zipfile
from pathlib import Path

import pytest

from anonimizzatore.estrazione import DocumentoNonSupportato, estrai, normalizza, ocr
from generatori.pdf import pdf_busta_paga, pdf_misto, pdf_protetto, pdf_scansionato
from generatori.word import crea_docx, docx_completo, paragrafo, run, tabella

ATTESI = Path(__file__).parent / "attesi"


# --- Word -----------------------------------------------------------------------------------


def test_docx_completo_corrisponde_al_file_atteso(tmp_path):
    risultato = estrai(docx_completo(tmp_path / "completo.docx"))
    atteso = (ATTESI / "docx_completo.txt").read_text(encoding="utf-8").rstrip("\n")
    assert risultato.testo == atteso


def test_docx_esclude_revisioni_nascosti_campi_e_commenti(tmp_path):
    risultato = estrai(docx_completo(tmp_path / "completo.docx"))
    for escluso in ("1.000", "nascosto", "PAGE", "commento con un dato sensibile"):
        assert escluso not in risultato.testo
    assert risultato.testo.count("IT60X0542811101000000123456") == 1
    assert any("commenti" in avviso for avviso in risultato.avvisi)


def test_docx_tabella_annidata_resta_nella_sua_cella(tmp_path):
    interna = tabella(["A1", "A2"])
    corpo = (
        "<w:tbl><w:tr><w:tc>" + paragrafo(run("Esterna")) + "</w:tc>"
        "<w:tc>" + interna + "</w:tc></w:tr></w:tbl>"
    )
    risultato = estrai(crea_docx(tmp_path / "annidata.docx", corpo))
    assert risultato.testo == "Esterna | A1 | A2"


def test_docx_non_valido(tmp_path):
    finto = tmp_path / "finto.docx"
    finto.write_bytes(b"non sono uno zip")
    with pytest.raises(DocumentoNonSupportato, match="danneggiato"):
        estrai(finto)


def test_docx_con_doctype_rifiutato(tmp_path):
    corpo = paragrafo(run("testo"))
    percorso = crea_docx(tmp_path / "doctype.docx", corpo)
    with zipfile.ZipFile(percorso, "a") as archivio:
        archivio.writestr("word/header1.xml", '<!DOCTYPE x [<!ENTITY a "b">]><w:hdr/>')
    with pytest.raises(DocumentoNonSupportato):
        estrai(percorso)


# --- PDF ------------------------------------------------------------------------------------


def test_pdf_conserva_le_colonne(tmp_path):
    risultato = estrai(pdf_busta_paga(tmp_path / "busta.pdf"))
    assert re.search(r"Cognome e nome {2,}ROSSI MARIO", risultato.testo)
    assert re.search(r"Mese di competenza {2,}Ottobre 2026", risultato.testo)
    assert risultato.testo.index("Pagina 1") < risultato.testo.index("Pagina 2")
    assert risultato.avvisi == ()


def test_pdf_scansionato_senza_ocr_rifiutato(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "disponibile", lambda: False)
    with pytest.raises(DocumentoNonSupportato, match="scansione"):
        estrai(pdf_scansionato(tmp_path / "scansione.pdf"))


def test_pdf_con_una_pagina_senza_testo_da_un_avviso(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "disponibile", lambda: False)
    risultato = estrai(pdf_misto(tmp_path / "misto.pdf"))
    assert "Prima pagina" in risultato.testo and "Terza pagina" in risultato.testo
    assert len(risultato.avvisi) == 1 and "leggibile (2)" in risultato.avvisi[0]


def test_pdf_protetto_rifiutato(tmp_path):
    with pytest.raises(DocumentoNonSupportato, match="password"):
        estrai(pdf_protetto(tmp_path / "protetto.pdf"))


def test_pdf_danneggiato(tmp_path):
    finto = tmp_path / "finto.pdf"
    finto.write_bytes(b"%PDF-1.4 non completo")
    with pytest.raises(DocumentoNonSupportato, match="danneggiato"):
        estrai(finto)


# --- TXT ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "codifica",
    ["utf-8", "utf-8-sig", "utf-16", "cp1252"],
)
def test_txt_codifiche(tmp_path, codifica):
    percorso = tmp_path / f"{codifica}.txt"
    percorso.write_bytes("Città: Forlì, perché sì\r\nseconda riga".encode(codifica))
    assert estrai(percorso).testo == "Città: Forlì, perché sì\nseconda riga"


def test_txt_vuoto_rifiutato(tmp_path):
    percorso = tmp_path / "vuoto.txt"
    percorso.write_text("  \n\n ", encoding="utf-8")
    with pytest.raises(DocumentoNonSupportato, match="non contiene testo"):
        estrai(percorso)


# --- Scelta del formato e normalizzazione ---------------------------------------------------


def test_doc_vecchio_formato_rifiutato(tmp_path):
    percorso = tmp_path / "vecchio.doc"
    percorso.write_bytes(b"qualsiasi")
    with pytest.raises(DocumentoNonSupportato, match=r"\.docx"):
        estrai(percorso)


def test_formato_sconosciuto(tmp_path):
    percorso = tmp_path / "foglio.xlsx"
    percorso.write_bytes(b"qualsiasi")
    with pytest.raises(DocumentoNonSupportato, match="Formato non supportato"):
        estrai(percorso)


def test_file_inesistente(tmp_path):
    with pytest.raises(DocumentoNonSupportato, match="non esiste"):
        estrai(tmp_path / "manca.pdf")


def test_estensione_maiuscola(tmp_path):
    percorso = tmp_path / "MAIUSCOLO.TXT"
    percorso.write_text("testo", encoding="utf-8")
    assert estrai(percorso).testo == "testo"


def test_normalizza_spazi_invisibili_e_righe_vuote():
    grezzo = "Ro​ssi Mario   \r\n\r\n\r\n\r\nfine\x07"
    assert normalizza(grezzo) == "Rossi Mario\n\nfine"


def test_normalizza_forma_nfc():
    # "e" + accento combinante diventa il singolo carattere "è".
    assert normalizza("perchè") == "perchè"
