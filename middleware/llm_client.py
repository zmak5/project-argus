"""Client Groq minimal partagé par les composants d'Argus.

Tous les appels LLM du middleware passent par ici : température 0 (exigence de
reproductibilité du CdC §7.2) et sortie JSON contrainte. La clé API vient de
l'environnement (.env via python-dotenv — jamais codée en dur).
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

load_dotenv()

# Modèle léger et rapide pour les tâches de classification du middleware
# (extraction d'intention, juge de cohérence). Distinct du modèle de l'agent.
# NB : Mixtral-8x7B cité au CdC n'existe plus sur Groq — cf. docs/ETAT_DE_LART.md §4.
MODELE_JUGE = os.getenv("ARGUS_MODELE_JUGE", "llama-3.1-8b-instant")


def groq_disponible() -> bool:
    """Vrai si une clé API Groq est configurée (sinon Argus tourne en mode
    dégradé : couches 0 et 1 uniquement, entièrement hors ligne)."""
    return bool(os.getenv("GROQ_API_KEY"))


def appel_json(prompt_systeme: str, prompt_utilisateur: str, modele: str = MODELE_JUGE) -> dict:
    """Appel Groq déterministe avec réponse JSON garantie par l'API."""
    from groq import Groq  # import local : le package n'est requis qu'en ligne

    client = Groq()  # lit GROQ_API_KEY dans l'environnement
    reponse = client.chat.completions.create(
        model=modele,
        messages=[
            {"role": "system", "content": prompt_systeme},
            {"role": "user", "content": prompt_utilisateur},
        ],
        temperature=0,  # reproductibilité de la démo (CdC §7.2)
        response_format={"type": "json_object"},
    )
    return json.loads(reponse.choices[0].message.content)
