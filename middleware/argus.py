"""ARGUS — point d'entrée du middleware : analyse de trajectoire + décision.

Usage (contrat d'intégration pour l'agent, cf. README) :

    from middleware.argus import Argus

    argus = Argus(protege=True)
    argus.demarrer_session("Résume le doc RH et envoie-le à manager@company.com")

    # Avant CHAQUE appel d'outil (règle d'architecture centrale du CdC §4.1) :
    decision = argus.inspecter_appel_outil("send_message",
                                           {"destinataire": "...", "contenu": "..."})
    if decision.niveau == "BLOQUER":   # ne pas exécuter l'outil
    if decision.niveau == "CONFIRMER": # demander confirmation humaine
    if decision.niveau == "AUTORISER": # exécuter

    # Optionnel : signaler le contenu externe entrant (sortie de search_document)
    argus.analyser_contenu_externe(contenu, source="doc_rh.txt")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from middleware import coherence_checker, fingerprint_guard
from middleware.intent_capture import EmpreinteIntention, capturer_intention
from middleware.rules_engine import RulesEngine

# Seuils de décision du CdC §4.2 (calibrables en Phase 3)
SEUIL_CONFIRMATION = 30  # score >= 30 : confirmation humaine requise
SEUIL_BLOCAGE = 70       # score >  70 : blocage automatique

# Poids maximal de la couche 2 (juge LLM) dans le score global : signal
# d'appoint, jamais suffisant seul pour bloquer (cf. docs/ETAT_DE_LART.md §5).
POIDS_JUGE = 40

CHEMIN_JOURNAL_DEFAUT = Path(__file__).parent.parent / "logs" / "decisions.jsonl"


@dataclass
class Decision:
    """Résultat d'une inspection Argus — tout ce qu'il faut pour décider et expliquer."""

    niveau: str                    # "AUTORISER" | "CONFIRMER" | "BLOQUER"
    score_global: int              # 0-100
    score_couche0: int             # violations déterministes de l'empreinte
    score_couche1: int             # règles statiques
    score_couche2: int | None      # juge LLM (None = indisponible/hors ligne)
    motifs: list[str] = field(default_factory=list)
    horodatage: str = ""

    @property
    def autorise(self) -> bool:
        return self.niveau == "AUTORISER"


class Argus:
    """Middleware de surveillance comportementale — une instance par session."""

    def __init__(
        self,
        protege: bool = True,
        chemin_journal: str | Path = CHEMIN_JOURNAL_DEFAUT,
        moteur_regles: RulesEngine | None = None,
    ):
        self.protege = protege  # bascule protégé / non protégé (EF-7)
        self.chemin_journal = Path(chemin_journal)
        self.moteur_regles = moteur_regles or RulesEngine()
        self.empreinte: EmpreinteIntention | None = None

    # ------------------------------------------------------------------ session

    def demarrer_session(self, requete_utilisateur: str) -> EmpreinteIntention:
        """Capture et verrouille l'empreinte d'intention (EF-2)."""
        self.empreinte = capturer_intention(requete_utilisateur)
        self._journaliser("session", {"empreinte": self.empreinte.to_dict()})
        return self.empreinte

    # -------------------------------------------------------------- inspections

    def inspecter_appel_outil(self, nom_outil: str, params: dict) -> Decision:
        """Point de contrôle obligatoire avant chaque appel d'outil (EF-3)."""
        if self.empreinte is None:
            raise RuntimeError("Appeler demarrer_session() avant toute inspection.")

        motifs: list[str] = []

        # Couche 0 — comparaison déterministe à l'empreinte (signal fort)
        violations = fingerprint_guard.verifier(self.empreinte, nom_outil, params)
        score_c0 = max((v.gravite for v in violations), default=0)
        motifs += [f"[couche0:{v.code}] {v.detail}" for v in violations]

        # Couche 1 — règles statiques sur le contenu des paramètres
        texte_params = json.dumps(params, ensure_ascii=False, default=str)
        declenchees = self.moteur_regles.analyser(texte_params)
        score_c1 = self.moteur_regles.score(declenchees)
        motifs += [f"[couche1:{r.id}:{r.nom}] « {r.extrait} »" for r in declenchees]

        # Couche 2 — juge LLM, seulement si un doute existe déjà OU si l'outil
        # est inconnu de la couche 0 (économie d'appels + latence < 3 s, CdC §7.2)
        score_c2: int | None = None
        if score_c0 or score_c1 or nom_outil not in fingerprint_guard.MOTS_CLES_PAR_OUTIL:
            verdict = coherence_checker.evaluer_coherence(self.empreinte, nom_outil, params)
            if verdict is not None:
                score_brut, explication = verdict
                score_c2 = round(score_brut * POIDS_JUGE)
                if explication:
                    motifs.append(f"[couche2:juge] {explication} (score {score_brut:.2f})")

        # Combinaison : la violation d'empreinte domine ; règles + juge s'additionnent.
        score_global = min(100, max(score_c0, score_c1 + (score_c2 or 0)))

        if not self.protege:
            # Mode démo "non protégé" : on observe et journalise, on ne bloque rien.
            niveau = "AUTORISER"
            motifs.insert(0, "[mode non protégé] analyse journalisée, aucune action bloquée")
        elif score_global > SEUIL_BLOCAGE:
            niveau = "BLOQUER"
        elif score_global >= SEUIL_CONFIRMATION:
            niveau = "CONFIRMER"
        else:
            niveau = "AUTORISER"

        decision = Decision(
            niveau=niveau,
            score_global=score_global,
            score_couche0=score_c0,
            score_couche1=score_c1,
            score_couche2=score_c2,
            motifs=motifs,
            horodatage=datetime.now(UTC).isoformat(),
        )
        self._journaliser(
            "appel_outil",
            {"outil": nom_outil, "params": params, "decision": decision.__dict__},
        )
        return decision

    def analyser_contenu_externe(self, contenu: str, source: str) -> Decision:
        """Analyse un contenu externe entrant (sortie d'outil de recherche).

        N'est pas bloquant en soi — Argus bloque les ACTIONS, pas les lectures —
        mais alimente le journal et permet d'afficher l'alerte au plus tôt dans
        l'interface de démo.
        """
        declenchees = self.moteur_regles.analyser(contenu)
        score_c1 = self.moteur_regles.score(declenchees)
        motifs = [f"[couche1:{r.id}:{r.nom}] « {r.extrait} »" for r in declenchees]

        decision = Decision(
            niveau="AUTORISER" if score_c1 < SEUIL_CONFIRMATION or not self.protege
            else "CONFIRMER",
            score_global=score_c1,
            score_couche0=0,
            score_couche1=score_c1,
            score_couche2=None,
            motifs=motifs or ["aucun motif suspect dans le contenu"],
            horodatage=datetime.now(UTC).isoformat(),
        )
        self._journaliser("contenu_externe", {"source": source, "decision": decision.__dict__})
        return decision

    # ------------------------------------------------------------------- journal

    def _journaliser(self, type_evenement: str, donnees: dict) -> None:
        """Journal JSONL append-only : horodatage, type, données (EF-6)."""
        self.chemin_journal.parent.mkdir(parents=True, exist_ok=True)
        entree = {
            "horodatage": datetime.now(UTC).isoformat(),
            "type": type_evenement,
            "protege": self.protege,
            **donnees,
        }
        with self.chemin_journal.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(entree, ensure_ascii=False, default=str) + "\n")
