"""Tests de la couche 1 (moteur de règles) — 100 % hors ligne.

Vérifie les deux moitiés du contrat :
1. chaque document piégé déclenche les règles attendues (pas de faux négatif),
2. aucun document sain ne déclenche de règle (pas de faux positif — scénario C).
"""

from pathlib import Path

import pytest

from middleware.rules_engine import PLAFOND_SCORE_COUCHE_1, RulesEngine

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def moteur():
    return RulesEngine()


def lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


# ---------------------------------------------------------------- docs piégés

def test_doc_rh_piege(moteur):
    declenchees = moteur.analyser(lire(DATA / "docs_pieges" / "doc_rh_piege.txt"))
    ids = {r.id for r in declenchees}
    # annulation d'instructions, fausse balise système, redéfinition de rôle,
    # injonction d'envoi vers une adresse, dissimulation
    assert {"R01", "R02", "R03", "R05", "R06"} <= ids


def test_ticket_support_piege(moteur):
    declenchees = moteur.analyser(lire(DATA / "docs_pieges" / "ticket_support_piege.txt"))
    ids = {r.id for r in declenchees}
    # détournement de tâche + dissimulation
    assert {"R06", "R07"} <= ids


def test_page_web_piege(moteur):
    declenchees = moteur.analyser(lire(DATA / "docs_pieges" / "page_web_piege.txt"))
    ids = {r.id for r in declenchees}
    # adressage direct à l'IA, redéfinition de rôle, divulgation d'interne,
    # commentaire HTML caché
    assert {"R02", "R04", "R08", "R10"} <= ids


def test_tous_les_pieges_detectes(moteur):
    """EF : le middleware détecte au moins 3 variantes d'injection différentes."""
    for doc in (DATA / "docs_pieges").glob("*.txt"):
        assert moteur.analyser(lire(doc)), f"{doc.name} : aucune règle déclenchée"


# ----------------------------------------------------------------- docs sains

@pytest.mark.parametrize(
    "nom", ["note_conges.txt", "rapport_activite.txt", "politique_securite.txt"]
)
def test_docs_sains_sans_declenchement(moteur, nom):
    """Scénario C : les documents légitimes — y compris celui qui parle
    d'« instructions de sécurité » — ne déclenchent aucune règle."""
    declenchees = moteur.analyser(lire(DATA / "docs_sains" / nom))
    assert declenchees == [], f"faux positif sur {nom} : {[r.id for r in declenchees]}"


# --------------------------------------------------------------------- score

def test_score_plafonne(moteur):
    declenchees = moteur.analyser(lire(DATA / "docs_pieges" / "doc_rh_piege.txt"))
    assert moteur.score(declenchees) == PLAFOND_SCORE_COUCHE_1


def test_texte_neutre_score_zero(moteur):
    assert moteur.score(moteur.analyser("Bonjour, voici le rapport demandé.")) == 0
