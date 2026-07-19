"""Génère un rapport de synthèse lisible à partir de logs/decisions.jsonl."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

CHEMIN_JOURNAL = Path(__file__).parent.parent / "logs" / "decisions.jsonl"
CHEMIN_RAPPORT = Path(__file__).parent.parent / "logs" / "rapport_session.html"


def charger_evenements() -> list[dict]:
    if not CHEMIN_JOURNAL.exists():
        return []
    evenements = []
    with CHEMIN_JOURNAL.open(encoding="utf-8") as f:
        for ligne in f:
            if ligne.strip():
                evenements.append(json.loads(ligne))
    return evenements


def generer_rapport() -> Path:
    evenements = charger_evenements()
    appels = [e for e in evenements if e.get("type") == "appel_outil"]
    niveaux = Counter(e["decision"]["niveau"] for e in appels)

    lignes_tableau = ""
    for e in appels:
        d = e["decision"]
        couleur = {"AUTORISER": "#2ecc71", "CONFIRMER": "#f39c12", "BLOQUER": "#e74c3c"}.get(d["niveau"], "#333")
        motifs = "<br>".join(d.get("motifs", [])) or "—"
        lignes_tableau += f"""
        <tr>
            <td>{e.get('horodatage', '')}</td>
            <td>{e.get('outil', '')}</td>
            <td style="color:{couleur}; font-weight:bold;">{d['niveau']}</td>
            <td>{d['score_global']}/100</td>
            <td style="font-size:12px;">{motifs}</td>
        </tr>"""

    html = f"""
    <html><head><meta charset="utf-8"><title>Rapport de session Argus</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 30px; color: #222; }}
        h1 {{ color: #16213e; }}
        .resume {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .carte {{ background: #f5f6fa; border-radius: 8px; padding: 15px 25px; text-align: center; }}
        .carte b {{ font-size: 24px; display: block; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background: #16213e; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
    </style></head><body>
        <h1>Rapport de session — ARGUS</h1>
        <p>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
        <div class="resume">
            <div class="carte" style="color:#2ecc71;"><b>{niveaux.get('AUTORISER', 0)}</b>Autorisées</div>
            <div class="carte" style="color:#f39c12;"><b>{niveaux.get('CONFIRMER', 0)}</b>Confirmations</div>
            <div class="carte" style="color:#e74c3c;"><b>{niveaux.get('BLOQUER', 0)}</b>Bloquées</div>
        </div>
        <table>
            <tr><th>Horodatage</th><th>Outil</th><th>Décision</th><th>Score</th><th>Motifs</th></tr>
            {lignes_tableau}
        </table>
    </body></html>
    """
    CHEMIN_RAPPORT.write_text(html, encoding="utf-8")
    return CHEMIN_RAPPORT


if __name__ == "__main__":
    chemin = generer_rapport()
    print(f"Rapport généré : {chemin}")