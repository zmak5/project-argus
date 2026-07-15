"""Boucle ReAct custom de l'agent de démo — SQUELETTE (partie coéquipier).

À implémenter (Phase 1 du CdC) : une boucle simple qui
  1. envoie la requête utilisateur + la liste des outils au modèle Groq
     (`ARGUS_MODELE_AGENT`, tool use via l'API chat completions),
  2. pour chaque tool_call renvoyé par le modèle :
       a. si Argus est fourni → decision = argus.inspecter_appel_outil(nom, params)
          - "BLOQUER"   : ne pas exécuter, renvoyer le motif au modèle et à l'UI
          - "CONFIRMER" : demander confirmation (input() ou bouton web)
          - "AUTORISER" : exécuter
       b. exécuter OUTILS[nom](**params) et renvoyer le résultat au modèle,
       c. si l'outil est search_document → argus.analyser_contenu_externe(...)
  3. s'arrête quand le modèle répond sans tool_call (réponse finale).

Le contrat complet avec le middleware est documenté dans README.md — le
middleware est déjà fonctionnel et testé, tu peux développer contre lui dès
maintenant (il marche même sans clé API, couches 0+1).
"""

from __future__ import annotations

from agent.tools import OUTILS  # noqa: F401  (registre partagé avec la boucle)
from middleware.argus import Argus  # noqa: F401


def executer_session(requete_utilisateur: str, argus: Argus | None = None) -> str:
    """Point d'entrée de l'agent. À implémenter (voir docstring du module)."""
    raise NotImplementedError("Boucle ReAct à implémenter — Phase 1 du CdC.")
