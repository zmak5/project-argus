"""Capture de l'empreinte d'intention (CdC §3).

Au démarrage de la session, avant toute action de l'agent, on extrait et on
verrouille les trois paramètres fondamentaux de la requête utilisateur :
action attendue, destinataires autorisés, périmètre de données. Toute la
surveillance de trajectoire se fait ensuite par comparaison à cette empreinte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from middleware.llm_client import appel_json, groq_disponible

REGEX_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


@dataclass
class EmpreinteIntention:
    """Les 3 paramètres verrouillés en début de session + la requête brute."""

    requete_initiale: str
    action_attendue: str
    destinataires_autorises: list[str] = field(default_factory=list)
    perimetre_donnees: str = ""

    def to_dict(self) -> dict:
        return {
            "requete_initiale": self.requete_initiale,
            "action_attendue": self.action_attendue,
            "destinataires_autorises": self.destinataires_autorises,
            "perimetre_donnees": self.perimetre_donnees,
        }


PROMPT_EXTRACTION = """Tu es un module d'analyse de requêtes pour un middleware \
de sécurité d'agents IA. On te donne la requête initiale d'un utilisateur. \
Extrais-en trois paramètres, sans rien inventer :
- action_attendue : ce que l'agent doit faire, en une phrase courte.
- destinataires_autorises : liste des destinataires (emails, comptes, personnes) \
explicitement mentionnés par l'utilisateur. Liste vide si aucun.
- perimetre_donnees : quelles données l'agent est autorisé à consulter.
Réponds UNIQUEMENT en JSON avec exactement ces trois clés."""


def capturer_intention(requete_utilisateur: str) -> EmpreinteIntention:
    """Construit l'empreinte d'intention, via Groq si disponible.

    Mode dégradé hors ligne (pas de clé API) : extraction heuristique — les
    emails cités dans la requête deviennent les destinataires autorisés et la
    requête entière sert d'action attendue. Suffisant pour les tests unitaires
    et pour garder la couche 0 fonctionnelle sans réseau.
    """
    if groq_disponible():
        try:
            reponse = appel_json(PROMPT_EXTRACTION, requete_utilisateur)
            return EmpreinteIntention(
                requete_initiale=requete_utilisateur,
                action_attendue=str(reponse.get("action_attendue", requete_utilisateur)),
                destinataires_autorises=[
                    str(d).lower() for d in reponse.get("destinataires_autorises", [])
                ],
                perimetre_donnees=str(reponse.get("perimetre_donnees", "")),
            )
        except Exception:
            # Si l'appel LLM échoue, on retombe sur l'extraction heuristique :
            # la protection ne doit jamais dépendre du réseau pour exister.
            pass

    return EmpreinteIntention(
        requete_initiale=requete_utilisateur,
        action_attendue=requete_utilisateur,
        destinataires_autorises=[e.lower() for e in REGEX_EMAIL.findall(requete_utilisateur)],
        perimetre_donnees="",
    )
