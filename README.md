# programma_privacy

Anonimizzatore: un programma Windows che toglie i dati personali da PDF, Word e file di testo e restituisce un testo con pseudonimi (`[PERSONA_1]`, `[CODICE_FISCALE_1]`…), da dare poi a un'AI. Tutto avviene sul PC: il documento non viene mai inviato in rete.

> **Mai documenti reali in questo repository**, nemmeno come esempio o allegato a una segnalazione. I test usano solo dati inventati.

## Sviluppo

Serve Python 3.12.

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Controlli, gli stessi della CI:

```bash
ruff check .
ruff format --check .
pytest
```

Il numero di versione si cambia solo in `src/anonimizzatore/__init__.py`.
