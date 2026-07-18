"""Interface de démonstration interactive (Phase 4 du CdC).

Lancer depuis la racine : python -m interface.demo
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from agent.agent import executer_session
from middleware.argus import Argus


def afficher_banniere() -> None:
    print("=" * 60)
    print("  ARGUS — Démo middleware anti-injection de prompt")
    print("=" * 60)


def choisir_mode() -> bool:
    reponse = input("Mode protégé activé ? (o/n) [o par défaut] : ").strip().lower()
    return reponse != "n"


def main() -> None:
    afficher_banniere()
    protege = choisir_mode()
    print(f"\n>> Mode : {'PROTÉGÉ' if protege else 'NON PROTÉGÉ'}\n")

    argus = Argus(protege=protege)

    while True:
        requete = input("\nVotre requête (ou 'quit' pour sortir) : ").strip()
        if requete.lower() in ("quit", "exit"):
            print("Fin de la démo.")
            break
        if not requete:
            continue

        print("\n--- Traitement en cours ---")
        reponse = executer_session(requete, argus=argus)
        print(f"\n>> Réponse finale de l'agent : {reponse}")

    print("\nJournal complet : logs/decisions.jsonl")


if __name__ == "__main__":
    main()