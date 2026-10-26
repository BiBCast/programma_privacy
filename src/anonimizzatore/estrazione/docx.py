"""Testo dai file Word .docx, letto direttamente dall'XML.

Si legge solo il testo visibile: corpo, tabelle, caselle di testo, intestazioni, piè di pagina e
note. Restano fuori revisioni cancellate, testo nascosto, codici di campo, commenti e metadati.
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from anonimizzatore.estrazione import DocumentoNonSupportato, TestoEstratto

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

_P, _TBL, _TR, _TC = f"{_W}p", f"{_W}tbl", f"{_W}tr", f"{_W}tc"
_R, _T, _TAB = f"{_W}r", f"{_W}t", f"{_W}tab"
_TXBX = f"{_W}txbxContent"
_A_CAPO = {f"{_W}br", f"{_W}cr"}
# Elementi il cui contenuto non è testo visibile: revisioni cancellate, codici di campo,
# proprietà, e il doppione delle caselle di testo per le vecchie versioni di Word.
_DA_SALTARE = {
    f"{_W}del",
    f"{_W}moveFrom",
    f"{_W}delText",
    f"{_W}instrText",
    f"{_W}pPr",
    f"{_W}rPr",
    f"{_W}sectPr",
    f"{_MC}Fallback",
}

# Limite al testo XML letto, contro i file costruiti per esaurire la memoria.
_MAX_BYTE = 200 * 1024 * 1024

_DANNEGGIATO = "Il file Word è danneggiato o non è un vero file .docx."


def estrai_docx(percorso: Path) -> TestoEstratto:
    try:
        with zipfile.ZipFile(percorso) as archivio:
            nomi = set(archivio.namelist())
            if "word/document.xml" not in nomi:
                raise DocumentoNonSupportato(_DANNEGGIATO)
            if sum(info.file_size for info in archivio.infolist()) > _MAX_BYTE:
                raise DocumentoNonSupportato("Il file Word è troppo grande per essere letto.")

            def leggi(nome: str) -> ElementTree.Element:
                dati = archivio.read(nome)
                if b"<!DOCTYPE" in dati:
                    raise DocumentoNonSupportato(_DANNEGGIATO)
                return ElementTree.fromstring(dati)

            sezioni = [("", _righe(leggi("word/document.xml")))]
            sezioni.append(("[Intestazione]", _parti(leggi, nomi, "header")))
            sezioni.append(("[Piè di pagina]", _parti(leggi, nomi, "footer")))
            note = [n for n in ("word/footnotes.xml", "word/endnotes.xml") if n in nomi]
            sezioni.append(("[Note]", [r for n in note for r in _righe(leggi(n))]))

            avvisi = []
            if "word/comments.xml" in nomi and any(_righe(leggi("word/comments.xml"))):
                avvisi.append("Il documento contiene commenti: non sono stati inclusi nel testo.")
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as errore:
        raise DocumentoNonSupportato(_DANNEGGIATO) from errore

    blocchi = []
    for titolo, righe in sezioni:
        righe = [r for r in righe if r.strip()]
        if righe:
            blocchi.append("\n".join([titolo, *righe] if titolo else righe))
    return TestoEstratto("\n\n".join(blocchi), tuple(avvisi))


def _parti(leggi, nomi: set[str], tipo: str) -> list[str]:
    """Righe di intestazioni o piè di pagina, senza ripetere quelle identiche."""

    def numero(nome: str) -> int:
        cifre = re.search(r"(\d+)\.xml$", nome)
        return int(cifre.group(1)) if cifre else 0

    righe: list[str] = []
    viste: set[tuple[str, ...]] = set()
    parti = sorted((n for n in nomi if re.fullmatch(rf"word/{tipo}\d*\.xml", n)), key=numero)
    for nome in parti:
        testo = tuple(r for r in _righe(leggi(nome)) if r.strip())
        if testo and testo not in viste:
            viste.add(testo)
            righe.extend(testo)
    return righe


def _righe(radice: ElementTree.Element) -> list[str]:
    righe: list[str] = []
    _blocchi(radice, righe)
    return righe


def _blocchi(elemento: ElementTree.Element, righe: list[str]) -> None:
    for figlio in elemento:
        if figlio.tag == _P:
            _paragrafo(figlio, righe)
        elif figlio.tag == _TBL:
            _tabella(figlio, righe)
        elif figlio.tag not in _DA_SALTARE:
            _blocchi(figlio, righe)


def _paragrafo(paragrafo: ElementTree.Element, righe: list[str]) -> None:
    parti: list[str] = []
    caselle: list[ElementTree.Element] = []
    _testo(paragrafo, parti, caselle)
    righe.extend("".join(parti).split("\n"))
    # Le caselle di testo vanno subito dopo il paragrafo a cui sono ancorate.
    for casella in caselle:
        _blocchi(casella, righe)


def _testo(elemento: ElementTree.Element, parti: list[str], caselle: list) -> None:
    for figlio in elemento:
        tag = figlio.tag
        if tag == _T:
            parti.append(figlio.text or "")
        elif tag == _TAB:
            parti.append("\t")
        elif tag in _A_CAPO:
            parti.append("\n")
        elif tag == _TXBX:
            caselle.append(figlio)
        elif tag in _DA_SALTARE or (tag == _R and _nascosto(figlio)):
            continue
        else:
            _testo(figlio, parti, caselle)


def _nascosto(run: ElementTree.Element) -> bool:
    vanish = run.find(f"{_W}rPr/{_W}vanish")
    return vanish is not None and vanish.get(f"{_W}val", "true") not in ("false", "0", "off")


def _tabella(tabella: ElementTree.Element, righe: list[str]) -> None:
    for riga in tabella.findall(_TR):
        celle = []
        for cella in riga.findall(_TC):
            contenuto: list[str] = []
            _blocchi(cella, contenuto)
            celle.append(" ".join(r.strip() for r in contenuto if r.strip()))
        righe.append(" | ".join(celle))
