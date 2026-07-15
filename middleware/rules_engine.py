"""Couche 1 — Moteur de règles statiques (détection déterministe par patterns).

Fonctionne entièrement hors ligne : c'est la couche qui doit rester opérationnelle
même sans réseau ni clé API (exigence issue de l'étude préalable, cf.
docs/ETAT_DE_LART.md §5). Les patterns vivent dans rules.json et sont éditables
sans toucher au code (EF-10).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from middleware.text_normalizer import normaliser

# Plafond de la contribution de la couche 1 au score global (0-100) :
# plusieurs règles déclenchées ne doivent pas à elles seules dépasser ce plafond,
# la décision finale revient au moteur de décision (argus.py).
PLAFOND_SCORE_COUCHE_1 = 50

# Poids d'un signal d'obfuscation : cacher du texte à un humain est en soi
# suspect (cf. text_normalizer). Volontairement modéré pour ne pas bloquer seul.
POIDS_OBFUSCATION = 20

# Seuil de score couche 1 au-delà duquel un contenu est considéré "signalé"
# (utilisé par le benchmark ; aligné sur SEUIL_CONFIRMATION du moteur de décision).
SEUIL_ALERTE_DEFAUT = 30

CHEMIN_RULES_DEFAUT = Path(__file__).parent / "rules.json"


@dataclass
class RegleDeclenchee:
    """Une règle qui a matché dans le texte analysé."""

    id: str
    nom: str
    description: str
    poids: int
    extrait: str  # le passage exact du texte qui a déclenché la règle


class RulesEngine:
    """Charge rules.json et analyse un texte contre tous les patterns."""

    def __init__(self, chemin_rules: str | Path = CHEMIN_RULES_DEFAUT):
        donnees = json.loads(Path(chemin_rules).read_text(encoding="utf-8"))
        self.regles = []
        for regle in donnees["regles"]:
            self.regles.append(
                {
                    **regle,
                    # DOTALL : les injections s'étalent souvent sur plusieurs lignes
                    "compilee": re.compile(regle["pattern"], re.IGNORECASE | re.DOTALL),
                }
            )

    def analyser(self, texte: str) -> list[RegleDeclenchee]:
        """Retourne la liste des règles déclenchées par le texte.

        Le texte est d'abord dé-obfusqué (caractères invisibles, homoglyphes,
        tags Unicode, espacement) pour empêcher un contournement trivial de la
        couche 1. L'obfuscation détectée devient elle-même une règle synthétique.
        """
        resultat = normaliser(texte)
        texte_propre = resultat.texte

        declenchees = []

        # Signaux d'obfuscation = règles synthétiques (id OBF-*)
        for signal in resultat.signaux:
            declenchees.append(
                RegleDeclenchee(
                    id=f"OBF-{signal}",
                    nom=f"obfuscation:{signal}",
                    description="Contenu masqué détecté et neutralisé avant analyse",
                    poids=POIDS_OBFUSCATION,
                    extrait=signal,
                )
            )

        for regle in self.regles:
            match = regle["compilee"].search(texte_propre)
            if match:
                # extrait tronqué : suffisant pour expliquer la décision (EF-9)
                extrait = match.group(0)[:120].replace("\n", " ")
                declenchees.append(
                    RegleDeclenchee(
                        id=regle["id"],
                        nom=regle["nom"],
                        description=regle["description"],
                        poids=regle["poids"],
                        extrait=extrait,
                    )
                )
        return declenchees

    @staticmethod
    def score(declenchees: list[RegleDeclenchee]) -> int:
        """Somme des poids des règles déclenchées, plafonnée."""
        return min(PLAFOND_SCORE_COUCHE_1, sum(r.poids for r in declenchees))
