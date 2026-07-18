"""Boucle ReAct custom de l'agent de démo."""

from __future__ import annotations

import json
import os

from groq import Groq

from agent.tools import OUTILS
from middleware.argus import Argus

MODELE = os.getenv("ARGUS_MODELE_AGENT", "llama-3.1-8b-instant")

# Description des outils au format attendu par l'API Groq (tool use)
OUTILS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_document",
            "description": "Recherche un document par son nom dans data/",
            "parameters": {
                "type": "object",
                "properties": {"nom_document": {"type": "string"}},
                "required": ["nom_document"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Envoie un message à un destinataire",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinataire": {"type": "string"},
                    "contenu": {"type": "string"},
                },
                "required": ["destinataire", "contenu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "Consulte le profil d'un client via son identifiant",
            "parameters": {
                "type": "object",
                "properties": {"identifiant": {"type": ["string", "integer"]}},
                "required": ["identifiant"],
            },
        },
    },
]


MAX_ITERATIONS = 8


def executer_session(requete_utilisateur: str, argus: Argus | None = None) -> str:
    """Point d'entrée de l'agent : boucle ReAct avec vérification Argus."""
    client = Groq()
    messages = [{"role": "user", "content": requete_utilisateur}]

    if argus is not None:
        argus.demarrer_session(requete_utilisateur)

    iterations = 0
    while True:
        iterations += 1
        if iterations > MAX_ITERATIONS:
            return "[ARGUS] Session arrêtée : trop de tentatives d'action suspectes détectées."

        try:
            reponse = client.chat.completions.create(
                model=MODELE,
                messages=messages,
                tools=OUTILS_SCHEMA,
            )
        except Exception as erreur:
            print(f"[AGENT] Erreur API Groq (tentative {iterations}) : {erreur}")
            messages.append(
                {
                    "role": "user",
                    "content": "Ton précédent appel d'outil était invalide. Réponds avec un appel correctement formaté, ou donne ta réponse finale.",
                }
            )
            continue

        message_ia = reponse.choices[0].message

        # Pas de tool_call → le modèle a fini, c'est la réponse finale
        if not message_ia.tool_calls:
            return message_ia.content or ""

        messages.append(message_ia)

        for appel in message_ia.tool_calls:
            nom = appel.function.name
            params = json.loads(appel.function.arguments)
            params = {k: (str(v) if isinstance(v, (int, float)) else v) for k, v in params.items()}

            print(f"\n[AGENT] Appel outil : {nom}({params})")

            resultat_texte: str

            if argus is not None:
                decision = argus.inspecter_appel_outil(nom, params)
                print(f"[ARGUS] Décision : {decision.niveau} (score {decision.score_global}/100)")
                for motif in decision.motifs:
                    print(f"         {motif}")

                if decision.niveau == "BLOQUER":
                    resultat_texte = (
                        "[ARGUS] Action bloquée et refusée définitivement. "
                        "N'essaie pas d'autres destinataires ou reformulations : "
                        f"cette action reste interdite. Motifs : {decision.motifs}"
                    )
                elif decision.niveau == "CONFIRMER":
                    reponse_utilisateur = input(
                        f"⚠️ Argus demande confirmation pour {nom}({params}). "
                        f"Motifs : {decision.motifs}. Confirmer ? (o/n) "
                    )
                    if reponse_utilisateur.strip().lower() == "o":
                        resultat_texte = OUTILS[nom](**params)
                    else:
                        resultat_texte = "[Utilisateur a refusé l'action]"
                else:  # AUTORISER
                    resultat_texte = OUTILS[nom](**params)
            else:
                resultat_texte = OUTILS[nom](**params)

            if nom == "search_document" and argus is not None:
                verdict_contenu = argus.analyser_contenu_externe(
                    resultat_texte, source=params.get("nom_document", "")
                )
                if verdict_contenu.motifs and verdict_contenu.motifs != ["aucun motif suspect dans le contenu"]:
                    print(f"[ARGUS] Contenu externe suspect détecté : {verdict_contenu.motifs}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": appel.id,
                    "content": resultat_texte,
                }
            )