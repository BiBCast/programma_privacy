"""Crea PDF di prova con reportlab."""

from pathlib import Path

from reportlab.pdfgen import canvas


def pdf_busta_paga(percorso: Path) -> Path:
    """Due pagine a colonne, come una busta paga: etichetta a sinistra, valore a destra."""
    foglio = canvas.Canvas(str(percorso))
    for numero, (etichetta, valore) in enumerate(
        [("Cognome e nome", "ROSSI MARIO"), ("Mese di competenza", "Ottobre 2026")], 1
    ):
        foglio.drawString(50, 780, "Cedolino paga di prova - dati inventati")
        foglio.drawString(50, 750, etichetta)
        foglio.drawString(320, 750, valore)
        foglio.drawString(50, 730, f"Pagina {numero}")
        foglio.showPage()
    foglio.save()
    return percorso


def pdf_scansionato(percorso: Path) -> Path:
    """Solo grafica, nessun testo: come una scansione."""
    foglio = canvas.Canvas(str(percorso))
    foglio.rect(50, 50, 400, 600, fill=1)
    foglio.showPage()
    foglio.save()
    return percorso


def pdf_misto(percorso: Path) -> Path:
    """Tre pagine, la seconda senza testo."""
    foglio = canvas.Canvas(str(percorso))
    foglio.drawString(50, 750, "Prima pagina con testo sufficiente per la prova")
    foglio.showPage()
    foglio.rect(50, 50, 400, 600, fill=1)
    foglio.showPage()
    foglio.drawString(50, 750, "Terza pagina con testo sufficiente per la prova")
    foglio.showPage()
    foglio.save()
    return percorso


def pdf_protetto(percorso: Path) -> Path:
    foglio = canvas.Canvas(str(percorso), encrypt="segreta")
    foglio.drawString(50, 750, "Documento protetto da password")
    foglio.showPage()
    foglio.save()
    return percorso
