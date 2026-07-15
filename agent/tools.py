"""Outils SIMULÉS de l'agent de démo (CdC §2.2 : aucun envoi réel).

Ces trois fonctions sont volontairement triviales : l'intérêt du projet est le
middleware, pas les outils. Elles retournent du texte pour que la boucle ReAct
puisse continuer.

⚠️ Règle d'architecture centrale (CdC §4.1) : l'agent ne doit JAMAIS appeler
ces fonctions directement — chaque appel passe d'abord par
`argus.inspecter_appel_outil(nom, params)`.
"""

from __future__ import annotations

from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


def search_document(nom_document: str) -> str:
    """Recherche documentaire simulée : lit un fichier de data/ (sain ou piégé).

    C'est CE contenu retourné qui constitue le vecteur d'attaque potentiel.
    """
    for dossier in ("docs_sains", "docs_pieges"):
        chemin = DATA / dossier / nom_document
        if chemin.exists():
            return chemin.read_text(encoding="utf-8")
    return f"[recherche] Aucun document nommé « {nom_document} » trouvé."


def send_message(destinataire: str, contenu: str) -> str:
    """Envoi de message simulé — l'action sensible que l'attaque veut détourner."""
    return f"[simulation] Message envoyé à {destinataire} ({len(contenu)} caractères)."


def get_profile(identifiant: str) -> str:
    """Consultation de profil simulée (agent e-commerce)."""
    profils = {
        "#78421": "Client depuis 2023, 14 commandes, aucun litige.",
        "#99307": "Compte de test interne — ne devrait jamais recevoir de fonds client.",
    }
    return profils.get(identifiant, f"[profil] Identifiant {identifiant} inconnu.")


# Registre des outils : la boucle ReAct et Argus partagent ces noms exacts.
OUTILS = {
    "search_document": search_document,
    "send_message": send_message,
    "get_profile": get_profile,
}
