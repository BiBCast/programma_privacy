"""Test della milestone M0: pacchetto installato, versione e dipendenze principali."""

import re

import pytest

from anonimizzatore import __version__
from anonimizzatore.cli import main


def test_versione_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_cli_stampa_la_versione(capsys):
    with pytest.raises(SystemExit) as uscita:
        main(["--versione"])
    assert uscita.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_modello_italiano_caricabile():
    import spacy

    nlp = spacy.load("it_core_news_md")
    assert "ner" in nlp.pipe_names
