"""Riga di comando, per sviluppo e test. Dalla milestone M4 anonimizza un file."""

import argparse

from anonimizzatore import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="anonimizzatore",
        description="Toglie i dati personali da un documento prima di darlo a un'AI.",
    )
    parser.add_argument("--versione", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
