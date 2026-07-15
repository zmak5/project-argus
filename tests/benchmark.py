"""Benchmark d'efficacité et de performance d'Argus — métriques type AgentDojo.

Mesure sur le jeu de documents de test, entièrement hors ligne (couches 0 + 1) :
  - Taux de détection des documents piégés (rappel / recall)
  - Taux de faux positifs sur les documents sains (le scénario C)
  - Latence par inspection (moyenne / p95), à comparer au seuil 3 s du CdC §7.2

Lancer depuis la racine :  python -m tests.benchmark
"""

from __future__ import annotations

import time
from pathlib import Path

from middleware.rules_engine import SEUIL_ALERTE_DEFAUT, RulesEngine

DATA = Path(__file__).parent.parent / "data"


def _mesurer(moteur: RulesEngine, textes: list[str]) -> tuple[list[int], list[float]]:
    """Retourne (scores, latences_ms) pour une liste de textes."""
    scores, latences = [], []
    for texte in textes:
        depart = time.perf_counter()
        declenchees = moteur.analyser(texte)
        latences.append((time.perf_counter() - depart) * 1000)
        scores.append(moteur.score(declenchees))
    return scores, latences


def executer() -> dict:
    moteur = RulesEngine()
    pieges = [p.read_text(encoding="utf-8") for p in sorted((DATA / "docs_pieges").glob("*.txt"))]
    sains = [p.read_text(encoding="utf-8") for p in sorted((DATA / "docs_sains").glob("*.txt"))]

    scores_pieges, lat_pieges = _mesurer(moteur, pieges)
    scores_sains, lat_sains = _mesurer(moteur, sains)

    seuil = SEUIL_ALERTE_DEFAUT
    detectes = sum(1 for s in scores_pieges if s >= seuil)
    faux_positifs = sum(1 for s in scores_sains if s >= seuil)
    toutes_latences = sorted(lat_pieges + lat_sains)
    p95 = toutes_latences[int(len(toutes_latences) * 0.95) - 1]

    return {
        "documents_pieges": len(pieges),
        "documents_sains": len(sains),
        "seuil_alerte": seuil,
        "detection": f"{detectes}/{len(pieges)}",
        "taux_detection": detectes / len(pieges) if pieges else 0.0,
        "faux_positifs": f"{faux_positifs}/{len(sains)}",
        "taux_faux_positifs": faux_positifs / len(sains) if sains else 0.0,
        "latence_moyenne_ms": round(sum(toutes_latences) / len(toutes_latences), 3),
        "latence_p95_ms": round(p95, 3),
    }


def main() -> None:
    r = executer()
    print("=" * 52)
    print(" BENCHMARK ARGUS - couche 1 (hors ligne)")
    print("=" * 52)
    print(f" Documents pieges       : {r['documents_pieges']}")
    print(f" Documents sains        : {r['documents_sains']}")
    print(f" Seuil d'alerte         : {r['seuil_alerte']}")
    print("-" * 52)
    print(f" Detection (recall)     : {r['detection']}  ({r['taux_detection']:.0%})")
    print(f" Faux positifs          : {r['faux_positifs']}  ({r['taux_faux_positifs']:.0%})")
    print("-" * 52)
    print(f" Latence moyenne        : {r['latence_moyenne_ms']} ms")
    print(f" Latence p95            : {r['latence_p95_ms']} ms  (seuil CdC : 3000 ms)")
    print("=" * 52)


if __name__ == "__main__":
    main()
