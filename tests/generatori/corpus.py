"""Corpus sintetico: frasi tipiche di atti, lettere e buste paga con nomi inventati.

Nomi e cognomi sono tra i più diffusi in Italia e nel mondo e vengono abbinati a caso: nessuna
frase descrive una persona reale. Per ogni documento si conosce in anticipo dove stanno i nomi
e a quale categoria di difficoltà appartengono.
"""

import random
import re
from dataclasses import dataclass

NOMI = [
    "Mario", "Anna", "Giulia", "Luca", "Francesca", "Giuseppe", "Chiara", "Marco", "Elena",
    "Paolo", "Sara", "Andrea", "Valentina", "Roberto", "Laura", "Stefano", "Federica", "Matteo",
    "Silvia", "Davide", "Alessandra", "Gennaro", "Carmela", "Mohamed", "Ioana", "Lorenzo",
    "Martina", "Antonio", "Rosa", "Pietro",
]  # fmt: skip
# Nomi che non stanno nell'elenco dei nomi propri: li deve riconoscere il modello.
NOMI_RARI = [
    "Ermenegildo", "Brunilde", "Zeno", "Ottone", "Liborio", "Teodolinda", "Ludovica", "Xavier",
    "Anselmo", "Ercole", "Guendalina", "Wilma", "Ezechiele", "Clotilde", "Gaudenzio", "Ofelia",
]  # fmt: skip
COGNOMI = [
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci", "Marino",
    "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Mancini", "Costa", "Giordano", "Rizzo",
    "Lombardi", "Moretti", "Barbieri", "Fontana", "Santoro", "Mariani", "Rinaldi", "Caruso",
    "Ferrara", "Galli", "Martini", "Leone", "Longo", "Martinelli", "Vitale", "Lombardo",
    "Serra", "Coppola", "De Santis", "D'Angelo", "Marchetti", "Pellegrini",
]  # fmt: skip
# Cognomi che sono anche parole comuni.
COGNOMI_PAROLA = ["Gentile", "Guerra", "Pace", "Grande", "Bianco", "Fortuna", "Corte", "Valle"]
# Nomi e cognomi delle comunità straniere più numerose in Italia, abbinati a caso.
STRANIERI_NOMI = [
    "Ngozi", "Chidi", "Fatou", "Moussa", "Arben", "Elira", "Dragos", "Bogdan", "Kateryna",
    "Oksana", "Wei", "Xiaoming", "Rahul", "Priya", "Jomar", "Maricel", "Karim", "Samira",
]  # fmt: skip
STRANIERI_COGNOMI = [
    "Okafor", "Adeyemi", "Diop", "Ndiaye", "Hoxha", "Gashi", "Popescu", "Ionescu", "Kovalenko",
    "Shevchenko", "Zhang", "Chen", "Sharma", "Singh", "Reyes", "Santos", "Benali", "Haddad",
]  # fmt: skip

# Nomi e cognomi stranieri che non stanno in nessun elenco del programma: misurano la rete di
# sicurezza (segnalazione dei possibili nomi) e il modello da solo.
STRANIERI_RARI_NOMI = ["Oluwaseun", "Thandiwe", "Bolat", "Tenzin", "Nalani", "Ayelet", "Kiri"]
STRANIERI_RARI_COGNOMI = ["Adebayo", "Mokoena", "Nurlanov", "Dorje", "Kealoha", "Tane", "Ozturk"]

CATEGORIE = (
    "comune",
    "raro",
    "raro_cognome_parola",
    "straniero",
    "straniero_raro",
    "solo_cognome",
)

# {p} = "Nome Cognome", {c} = "Cognome Nome", {P} = "COGNOME NOME" (come nelle buste paga),
# {s} = solo il cognome dell'ultima persona citata (lo deve trovare la propagazione).
MODELLI = [
    "Il signor {p} ha presentato ricorso. All'udienza {s} non si è presentato.",
    "La dipendente {p} chiede un permesso. La richiesta di {s} è approvata.",
    "Verbale: {p} riferisce che il collega {p} era assente. {s} conferma.",
    "Il ricorrente {p}, rappresentato dall'avv. {p}, chiede la riforma della sentenza.",
    "In data odierna {p} ha consegnato i documenti richiesti all'ufficio.",
    "Si conferma che la sig.ra {p} è stata assunta con la qualifica di impiegata.",
    "Hanno partecipato alla riunione {p}, {p} e {p}.",
    "Testimone: {p}",
    "Con la presente {p} comunica le proprie dimissioni.",
    "Il Giudice dott. {p} ha fissato l'udienza presso il Tribunale di Padova.",
    "Il contratto è stipulato tra {p} e la società Alfa S.r.l. con sede a Venezia.",
    "Il sottoscritto {p}, nato a Padova il 12/03/1975, dichiara quanto segue.",
    "COGNOME E NOME    {P}    MATRICOLA    004512",
    "Dipendente: {c}    Qualifica: Impiegato    Livello: 3",
    "IL SIGNOR {P} DICHIARA DI AVER RICEVUTO LA SOMMA INDICATA.",
    "Gentile {p}, le scriviamo in merito alla sua richiesta di ferie.",
    "La pratica è stata assegnata a {p} dell'ufficio legale.",
    "{p} e {p} sono comparsi davanti al notaio per la firma dell'atto.",
    "Elenco presenti: {c}; {c}; {c}.",
    "La richiesta di {p} è stata accolta dall'INPS e comunicata all'INAIL.",
    "Alfa S.r.l., in persona del legale rappresentante {p}, conviene in giudizio {p}.",
    "Il resistente {p} si è costituito; il testimone {p} conferma i fatti.",
    "Il ricorso proposto da {p} contro {p} è stato respinto.",
]


@dataclass(frozen=True)
class Documento:
    testo: str
    nomi: tuple[tuple[int, int], ...]  # posizioni dei nomi nel testo
    categorie: tuple[str, ...]  # categoria di ogni nome, nello stesso ordine


def _persona(caso: random.Random) -> tuple[str, str, str]:
    sorte = caso.random()
    if sorte < 0.45:
        return caso.choice(NOMI), caso.choice(COGNOMI), "comune"
    if sorte < 0.6:
        return caso.choice(NOMI_RARI), caso.choice(COGNOMI), "raro"
    if sorte < 0.7:
        return caso.choice(NOMI_RARI), caso.choice(COGNOMI_PAROLA), "raro_cognome_parola"
    if sorte < 0.9:
        return caso.choice(STRANIERI_NOMI), caso.choice(STRANIERI_COGNOMI), "straniero"
    return caso.choice(STRANIERI_RARI_NOMI), caso.choice(STRANIERI_RARI_COGNOMI), "straniero_raro"


def genera(quanti: int, seme: int = 0) -> list[Documento]:
    caso = random.Random(seme)
    documenti = []
    for _ in range(quanti):
        modello = caso.choice(MODELLI)
        parti, nomi, categorie, posizione = [], [], [], 0
        nome = cognome = ""
        for pezzo in re.split(r"(\{[pcPs]\})", modello):
            if pezzo in ("{p}", "{c}", "{P}", "{s}"):
                if pezzo == "{s}":
                    categoria = "solo_cognome"
                else:
                    nome, cognome, categoria = _persona(caso)
                testo = {
                    "{p}": f"{nome} {cognome}",
                    "{c}": f"{cognome} {nome}",
                    "{P}": f"{cognome} {nome}".upper(),
                    "{s}": cognome,
                }[pezzo]
                nomi.append((posizione, posizione + len(testo)))
                categorie.append(categoria)
            else:
                testo = pezzo
            parti.append(testo)
            posizione += len(testo)
        documenti.append(Documento("".join(parti), tuple(nomi), tuple(categorie)))
    return documenti
