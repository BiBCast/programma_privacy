"""Elenchi di parole distribuiti con il programma."""

from functools import cache
from importlib.resources import files


@cache
def elenco(nome: str) -> frozenset[str]:
    """Parole di un file di elenco, in minuscolo. Le righe che iniziano con # sono commenti."""
    testo = files(__name__).joinpath(nome).read_text(encoding="utf-8")
    righe = (riga.strip() for riga in testo.splitlines())
    return frozenset(riga.casefold() for riga in righe if riga and not riga.startswith("#"))
