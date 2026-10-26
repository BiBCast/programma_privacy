"""Sceglie, tra entità che si sovrappongono, quelle da tenere.

L'ordine conta:
1. le esclusioni ("non è un dato personale", decise dall'utente) bloccano tutto ciò che toccano;
2. poi i dati da mascherare, dal più affidabile: priorità più alta, poi intervallo più lungo,
   poi posizione;
3. infine le segnalazioni che non toccano nessun dato già scelto: una segnalazione non deve
   mai impedire di mascherare un dato.
"""

from anonimizzatore.rilevamento.modelli import Azione, Entita


def risolvi(entita: list[Entita]) -> list[Entita]:
    """Entità da mascherare o da segnalare, senza sovrapposizioni, in ordine di posizione."""
    occupate: list[Entita] = []
    scelte: list[Entita] = []
    for azione in (Azione.ESCLUDI, Azione.MASCHERA, Azione.SEGNALA):
        candidate = sorted(
            (e for e in entita if e.azione == azione),
            key=lambda e: (-e.priorita, -(e.fine - e.inizio), e.inizio),
        )
        for e in candidate:
            if not any(e.inizio < o.fine and o.inizio < e.fine for o in occupate):
                occupate.append(e)
                if azione != Azione.ESCLUDI:
                    scelte.append(e)
    return sorted(scelte, key=lambda e: e.inizio)
