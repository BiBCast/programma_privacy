"""Test dell'OCR dei PDF scansionati (milestone M1b). Solo dati inventati."""

import socket

import pytest

from anonimizzatore import diagnosi
from anonimizzatore.estrazione import DocumentoNonSupportato, estrai, ocr
from anonimizzatore.estrazione.ocr import Parola, impagina
from anonimizzatore.motore import analizza_file, applica
from anonimizzatore.rilevamento import regole
from anonimizzatore.rilevamento.modelli import Tipo
from generatori.pdf import pdf_busta_paga
from generatori.scansioni import busta_paga_scansionata, immagine_vuota, pdf_di_testo, scansiona

serve_ocr = pytest.mark.skipif(
    not ocr.disponibile(), reason="Tesseract non è installato (vendor/tesseract o PATH)"
)

DATI_DELLA_BUSTA = [
    "BIANCHI ANNA",
    "004512",
    "BNCNNA85M41L736X",
    "Via dei Mille 8",
    "347 1234567",
    "IT60X0542811101000000123456",
]


# --- Impaginazione, senza Tesseract ---------------------------------------------------------


def parola(testo, sinistra, alto, linea, confidenza=95.0):
    return Parola(testo, sinistra, alto, len(testo) * 20, 40, confidenza, linea)


def test_colonne_di_blocchi_diversi_sulla_stessa_riga():
    parole = [
        parola("Cognome", 100, 100, (1, 1, 1)),
        parola("e", 270, 101, (1, 1, 1)),
        parola("nome", 300, 100, (1, 1, 1)),
        parola("ROSSI", 900, 108, (2, 1, 1)),  # altro blocco, appena più in basso
        parola("MARIO", 1020, 108, (2, 1, 1)),
        parola("Livello", 100, 160, (1, 1, 2)),
    ]
    pagina = impagina(parole)
    assert pagina.testo.split("\n")[0].startswith("Cognome e nome  ")
    assert pagina.testo.split("\n")[0].endswith("ROSSI MARIO")
    assert pagina.testo.split("\n")[1] == "Livello"


def test_parole_incerte_con_la_loro_posizione():
    pagina = impagina([parola("Mario", 0, 0, (1, 1, 1)), parola("Ro55i", 120, 0, (1, 1, 1), 40)])
    ((inizio, fine),) = pagina.incerti
    assert pagina.testo[inizio:fine] == "Ro55i"


def test_pagina_senza_parole():
    assert impagina([]).testo == ""


# --- Codici letti male, senza Tesseract ------------------------------------------------------


@pytest.mark.parametrize(
    "testo, tipo, valore",
    [
        ("C.F. RSSMRA8OAO1H5O1U fine", Tipo.CODICE_FISCALE, "RSSMRA8OAO1H5O1U"),
        ("CF RSS MRA 80A01 H501U.", Tipo.CODICE_FISCALE, "RSS MRA 80A01 H501U"),
        ("IBAN IT6OXO542811101000000123456", Tipo.IBAN, "IT6OXO542811101000000123456"),
        ("IBAN lT60 X054 2811 1O10 0000 0123 456", Tipo.IBAN, "lT60 X054 2811 1O10 0000 0123 456"),
        ("P.IVA O1234567897", Tipo.PARTITA_IVA, "O1234567897"),
    ],
)
def test_codici_letti_male_ritrovati(testo, tipo, valore):
    assert valore in [e.valore for e in regole.trova(testo) if e.tipo == tipo]


def test_iniziale_letta_male_accanto_a_un_nome_solo_nelle_scansioni():
    from anonimizzatore.motore import analizza

    testo = "Il sig. Mario Rossi lonescu firma."
    scansione = analizza(testo, letto_con_ocr=True)
    assert [(d.entita.valore, d.entita.fonte) for d in scansione.segnalati] == [("lonescu", "ocr")]
    assert "lonescu" not in [d.entita.valore for d in analizza(testo).segnalati]


def test_senza_controllo_valido_nessun_codice():
    assert [e for e in regole.trova("RSSMRA8OAO1H5O1X") if e.tipo == Tipo.CODICE_FISCALE] == []
    assert regole.trova("testo normale con parole qualsiasi e niente codici") == []


# --- Con Tesseract --------------------------------------------------------------------------


@serve_ocr
@pytest.mark.parametrize("dpi", [300, 200])
def test_busta_paga_scansionata(tmp_path, dpi):
    analisi = analizza_file(busta_paga_scansionata(tmp_path, dpi))
    risultato = applica(analisi, nota_per_ai=False)
    for dato in DATI_DELLA_BUSTA:
        assert dato not in risultato
    assert "Retribuzione" in risultato and "1.854,30" in risultato
    assert "Cognome e nome    [PERSONA_1]" in risultato  # le colonne restano sulla stessa riga
    assert any("riconoscimento dei caratteri" in avviso for avviso in analisi.avvisi)


@serve_ocr
def test_pdf_misto_testo_e_scansione(tmp_path):
    import pypdfium2

    testo = pdf_di_testo(tmp_path / "testo.pdf", ["Il sottoscritto Mario Rossi dichiara."] * 3)
    scansione = busta_paga_scansionata(tmp_path)
    misto = pypdfium2.PdfDocument.new()
    for origine in (testo, scansione):
        documento = pypdfium2.PdfDocument(str(origine))
        misto.import_pages(documento)
        documento.close()
    misto.save(str(tmp_path / "misto.pdf"))
    misto.close()

    estratto = estrai(tmp_path / "misto.pdf")
    assert estratto.testo.lstrip().startswith("Il sottoscritto Mario Rossi dichiara.")
    assert "Retribuzione" in estratto.testo
    assert any("(2)" in avviso for avviso in estratto.avvisi)  # solo la pagina 2 è una scansione
    # Gli intervalli incerti puntano a parole vere del testo finale.
    assert all(
        estratto.testo[a:b].strip() == estratto.testo[a:b] != "" for a, b in estratto.incerti
    )


@serve_ocr
def test_pagina_bianca_non_leggibile(tmp_path):
    with pytest.raises(DocumentoNonSupportato, match="neanche con il riconoscimento"):
        estrai(immagine_vuota(tmp_path / "bianca.pdf"))


@serve_ocr
def test_pdf_di_testo_non_passa_dall_ocr(tmp_path):
    from anonimizzatore.estrazione.pdf import leggi_pagine

    pagine = leggi_pagine(pdf_busta_paga(tmp_path / "busta.pdf"))
    assert {p.metodo for p in pagine} == {"testo"}


@serve_ocr
def test_ocr_senza_file_temporanei_ne_rete(tmp_path, monkeypatch):
    temporanea = tmp_path / "temp"
    temporanea.mkdir()
    for variabile in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(variabile, str(temporanea))
    documento = busta_paga_scansionata(tmp_path)
    prima = set(tmp_path.rglob("*"))

    def vietata(*args, **kwargs):
        raise AssertionError("L'OCR ha provato ad aprire una connessione di rete.")

    monkeypatch.setattr(socket, "socket", vietata)
    estrai(documento)
    assert set(tmp_path.rglob("*")) == prima
    assert list(temporanea.iterdir()) == []


@serve_ocr
def test_diagnosi_senza_contenuto(tmp_path, capsys):
    documento = busta_paga_scansionata(tmp_path)
    assert diagnosi.main([str(documento)]) == 0
    uscita = capsys.readouterr().out
    assert "ocr" in uscita
    for dato in [*DATI_DELLA_BUSTA, "Retribuzione", "Alfa"]:
        assert dato not in uscita


def test_ocr_non_disponibile(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "disponibile", lambda: False)
    documento = scansiona(
        pdf_di_testo(tmp_path / "t.pdf", ["Testo abbastanza lungo per una pagina di prova"]),
        tmp_path / "s.pdf",
    )
    with pytest.raises(DocumentoNonSupportato, match="OCR non è disponibile"):
        estrai(documento)
