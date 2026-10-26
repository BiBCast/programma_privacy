"""Copertura dei nomi sul corpus sintetico, per categoria (criterio di chiusura di M3)."""

from misura_nomi import misura

# Nomi mascherati, in totale e per categoria.
COPERTURA_MINIMA = 0.95
COPERTURA_MINIMA_PER_CATEGORIA = 0.85
# Nomi mascherati o almeno segnalati in revisione: la rete di sicurezza.
VISTI_MINIMI = 0.99


def test_copertura_dei_nomi_per_categoria():
    totali, mascherati, visti, falsi_mascherati, falsi_segnalati, _ = misura(300, seme=7)
    n = sum(totali.values())
    riepilogo = {c: f"{mascherati[c]}/{totali[c]}" for c in totali}
    assert sum(mascherati.values()) / n >= COPERTURA_MINIMA, riepilogo
    assert sum(visti.values()) / n >= VISTI_MINIMI, riepilogo
    for categoria, quanti in totali.items():
        assert mascherati[categoria] / quanti >= COPERTURA_MINIMA_PER_CATEGORIA, riepilogo
    assert falsi_mascherati <= n * 0.01
    assert falsi_segnalati <= n * 0.05
