"""Crea file .docx minimi scrivendo direttamente l'XML, per controllare ogni caso."""

import zipfile
from pathlib import Path

_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def paragrafo(*runs: str) -> str:
    return f"<w:p>{''.join(runs)}</w:p>"


def run(testo: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{testo}</w:t></w:r>'


def tabella(*righe: list[str]) -> str:
    xml_righe = "".join(
        "<w:tr>" + "".join(f"<w:tc>{paragrafo(run(c))}</w:tc>" for c in celle) + "</w:tr>"
        for celle in righe
    )
    return f"<w:tbl><w:tblPr/>{xml_righe}</w:tbl>"


def crea_docx(
    percorso: Path,
    corpo: str,
    intestazioni: list[str] = (),
    piedi: list[str] = (),
    note: str | None = None,
    commenti: str | None = None,
) -> Path:
    parti = {
        "word/document.xml": f"<w:document {_NS}><w:body>{corpo}<w:sectPr/></w:body></w:document>"
    }
    for n, contenuto in enumerate(intestazioni, 1):
        parti[f"word/header{n}.xml"] = f"<w:hdr {_NS}>{contenuto}</w:hdr>"
    for n, contenuto in enumerate(piedi, 1):
        parti[f"word/footer{n}.xml"] = f"<w:ftr {_NS}>{contenuto}</w:ftr>"
    if note is not None:
        parti["word/footnotes.xml"] = f"<w:footnotes {_NS}>{note}</w:footnotes>"
    if commenti is not None:
        parti["word/comments.xml"] = f"<w:comments {_NS}>{commenti}</w:comments>"

    with zipfile.ZipFile(percorso, "w", zipfile.ZIP_DEFLATED) as archivio:
        archivio.writestr("[Content_Types].xml", "<Types/>")
        for nome, xml in parti.items():
            archivio.writestr(nome, '<?xml version="1.0" encoding="UTF-8"?>' + xml)
    return percorso


def docx_completo(percorso: Path) -> Path:
    """Un .docx con tutti i casi difficili: revisioni, testo nascosto, campi, caselle."""
    corpo = "".join(
        [
            paragrafo(run("Contratto di prova")),
            paragrafo(
                run("Il sottoscritto "),
                run("Mario Rossi"),
                "<w:r><w:tab/></w:r>",
                run("nato a Padova"),
            ),
            paragrafo(
                run("Importo: "),
                "<w:del><w:r><w:delText>1.000</w:delText></w:r></w:del>",
                "<w:ins><w:r><w:t>2.000</w:t></w:r></w:ins>",
                run(" euro"),
            ),
            paragrafo(run("Visibile"), "<w:r><w:rPr><w:vanish/></w:rPr><w:t> nascosto</w:t></w:r>"),
            paragrafo(run("Riga uno"), "<w:r><w:br/></w:r>", run("Riga due")),
            tabella(["Cognome", "ROSSI"], ["Nome", "MARIO"]),
            paragrafo(
                run("Testo prima della casella"),
                "<w:r><mc:AlternateContent>"
                '<mc:Choice Requires="wps"><w:drawing><wps:txbx><w:txbxContent>'
                + paragrafo(run("Casella: IBAN IT60X0542811101000000123456"))
                + "</w:txbxContent></wps:txbx></w:drawing></mc:Choice>"
                "<mc:Fallback><w:pict><v:textbox><w:txbxContent>"
                + paragrafo(run("Casella: IBAN IT60X0542811101000000123456"))
                + "</w:txbxContent></v:textbox></w:pict></mc:Fallback>"
                "</mc:AlternateContent></w:r>",
            ),
            paragrafo(
                run("Pagina "),
                '<w:r><w:fldChar w:fldCharType="begin"/></w:r>',
                "<w:r><w:instrText> PAGE </w:instrText></w:r>",
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>',
                "<w:r><w:t>1</w:t></w:r>",
                '<w:r><w:fldChar w:fldCharType="end"/></w:r>',
            ),
        ]
    )
    intestazione = paragrafo(run("Studio Esempio - riservato"))
    note = (
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
        f'<w:footnote w:id="1">{paragrafo(run("Nota: dato inventato"))}</w:footnote>'
    )
    commenti = f'<w:comment w:id="0">{paragrafo(run("commento con un dato sensibile"))}</w:comment>'
    return crea_docx(
        percorso,
        corpo,
        intestazioni=[intestazione, intestazione],
        piedi=[paragrafo(run("Pagina di prova"))],
        note=note,
        commenti=commenti,
    )
