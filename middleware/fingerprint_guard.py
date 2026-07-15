"""Couche 0 — Garde d'empreinte : vérifications DÉTERMINISTES contre l'empreinte
d'intention.

Décision de conception issue de l'étude préalable (docs/ETAT_DE_LART.md §5) :
TrajAD (arXiv 2602.06443) montre qu'un LLM-judge zero-shot est faillible sur les
anomalies de trajectoire. Le signal fort d'Argus doit donc être déterministe :
comparer structurellement chaque appel d'outil aux paramètres verrouillés de
l'empreinte. Pas de LLM ici, pas de réseau, pas d'ambiguïté.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from middleware.intent_capture import REGEX_EMAIL, EmpreinteIntention

# Clés de paramètres considérées comme des "destinations" (où partent les données)
CLES_DESTINATION = {"destinataire", "to", "recipient", "compte", "account", "email"}

# Mots-clés qui doivent apparaître dans l'action attendue pour que l'outil
# correspondant soit considéré "dans l'intention". Table volontairement simple
# et lisible — les cas ambigus sont laissés au juge LLM (couche 2).
MOTS_CLES_PAR_OUTIL = {
    "send_message": ["envoi", "envoy", "send", "transmet", "message", "mail", "partag"],
    "refund": ["rembours", "refund"],
    "delete_file": ["supprim", "delete", "efface"],
}

# Numéros de comptes type "#12345" — utilisés par le scénario e-commerce
REGEX_COMPTE = re.compile(r"#\d{3,}")


@dataclass
class Violation:
    """Un écart déterministe entre l'appel d'outil et l'empreinte verrouillée."""

    code: str
    gravite: int  # contribution directe au score global (0-100)
    detail: str


def _destinations_dans(texte: str) -> set[str]:
    """Extrait emails et numéros de compte d'un texte (en minuscules)."""
    return {e.lower() for e in REGEX_EMAIL.findall(texte)} | set(REGEX_COMPTE.findall(texte))


def verifier(empreinte: EmpreinteIntention, nom_outil: str, params: dict) -> list[Violation]:
    """Compare un appel d'outil à l'empreinte. Retourne les violations trouvées."""
    violations: list[Violation] = []

    # Référentiel des destinations légitimes : celles extraites par la capture
    # d'intention + toutes celles littéralement présentes dans la requête initiale.
    destinations_autorisees = set(d.lower() for d in empreinte.destinataires_autorises)
    destinations_autorisees |= _destinations_dans(empreinte.requete_initiale)

    # 1) Destination inconnue de l'empreinte = signal le plus fort d'Argus.
    #    C'est le cœur des attaques d'exfiltration (scénarios A1 et A2 du CdC).
    for cle, valeur in params.items():
        if cle.lower() not in CLES_DESTINATION:
            continue
        for destination in _destinations_dans(str(valeur)) or {str(valeur).lower()}:
            if destination not in destinations_autorisees:
                violations.append(
                    Violation(
                        code="destination_inconnue",
                        gravite=75,
                        detail=(
                            f"L'outil '{nom_outil}' cible '{destination}', "
                            "jamais mentionné par l'utilisateur."
                        ),
                    )
                )

    # 2) Outil sensible hors intention : l'utilisateur n'a rien demandé qui
    #    corresponde à cette catégorie d'action (ex. demande un résumé, l'agent
    #    tente une suppression → déviation critique, CdC §3.2).
    mots_cles = MOTS_CLES_PAR_OUTIL.get(nom_outil)
    if mots_cles is not None:
        intention = (empreinte.action_attendue + " " + empreinte.requete_initiale).lower()
        if not any(mot in intention for mot in mots_cles):
            violations.append(
                Violation(
                    code="action_hors_intention",
                    gravite=60,
                    detail=(
                        f"L'outil '{nom_outil}' ne correspond à rien dans "
                        f"l'intention déclarée : « {empreinte.action_attendue[:80]} »"
                    ),
                )
            )

    return violations
