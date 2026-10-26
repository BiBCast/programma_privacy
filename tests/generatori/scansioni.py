"""Scansioni finte: PDF di testo trasformati in PDF di sole immagini, con i difetti tipici.

Il testo è sempre inventato. Si parte da un PDF disegnato con reportlab, lo si rende come
immagine, poi si aggiungono rotazione, sfocatura e rumore come in una fotocopia.
"""

import random
from pathlib import Path

import pypdfium2
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

_MARGINE = 56
_INTERLINEA = 16


def pdf_di_testo(percorso: Path, righe: list[str], dimensione: int = 11) -> Path:
    """Un PDF di testo con una riga per elemento, su più pagine se serve."""
    foglio = canvas.Canvas(str(percorso), pagesize=A4)
    _, altezza = A4
    y = altezza - _MARGINE
    foglio.setFont("Helvetica", dimensione)
    for riga in righe:
        if y < _MARGINE:
            foglio.showPage()
            foglio.setFont("Helvetica", dimensione)
            y = altezza - _MARGINE
        foglio.drawString(_MARGINE, y, riga)
        y -= _INTERLINEA
    foglio.showPage()
    foglio.save()
    return percorso


def scansiona(
    origine: Path,
    destinazione: Path,
    dpi: int = 300,
    rotazione: float = 0.8,
    sfocatura: float = 0.5,
    rumore: float = 0.003,
    seme: int = 0,
) -> Path:
    """Trasforma ogni pagina in un'immagine "fotocopiata" e salva un PDF di sole immagini."""
    caso = random.Random(seme)
    documento = pypdfium2.PdfDocument(str(origine))
    immagini = []
    try:
        for pagina in documento:
            immagine = pagina.render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
            immagine = immagine.rotate(rotazione, expand=False, fillcolor=255)
            if sfocatura:
                immagine = immagine.filter(ImageFilter.GaussianBlur(sfocatura))
            if rumore:
                pixel = immagine.load()
                larghezza, altezza = immagine.size
                for _ in range(int(larghezza * altezza * rumore)):
                    x, y = caso.randrange(larghezza), caso.randrange(altezza)
                    pixel[x, y] = caso.choice((0, 255))
            immagini.append(immagine)
    finally:
        documento.close()
    prima, *altre = immagini
    prima.save(destinazione, "PDF", resolution=dpi, save_all=True, append_images=altre)
    return destinazione


def busta_paga_scansionata(cartella: Path, dpi: int = 300) -> Path:
    righe = [
        "Alfa S.r.l. - Via Industria 12, 30100 Venezia (VE) - P.IVA 01234567897",
        "Cedolino paga di ottobre 2026 - documento di prova con dati inventati",
        "",
        "Cognome e nome      BIANCHI ANNA          Matricola   004512",
        "Codice fiscale      BNCNNA85M41L736X      Livello     3",
        "Residente in Via dei Mille 8, 30170 Mestre (VE) - Tel. 347 1234567",
        "IBAN IT60X0542811101000000123456",
        "",
        "Retribuzione lorda  1.854,30              Netto in busta  1.402,77",
        "Malattia dal 3 al 10 ottobre",
    ]
    testo = pdf_di_testo(cartella / "busta_testo.pdf", righe)
    return scansiona(testo, cartella / f"busta_scansione_{dpi}.pdf", dpi=dpi)


def immagine_vuota(percorso: Path) -> Path:
    Image.new("L", (1240, 1754), 255).save(percorso, "PDF", resolution=150)
    return percorso
