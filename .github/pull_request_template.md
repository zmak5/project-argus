# Description

<!-- Qu'est-ce que cette PR change et pourquoi ? Lier l'exigence du CdC si applicable (EF-x). -->

## Check-list

- [ ] `python -m pytest tests/ -q` passe en local
- [ ] `ruff check .` passe en local
- [ ] Aucun secret (clé API, token) dans le diff — vérifié avec `git diff`
- [ ] Si nouvelle règle de détection : ajoutée dans `rules.json` (pas dans le code) + test associé
- [ ] Si changement du contrat middleware (`Argus`, `Decision`) : README mis à jour et coéquipier prévenu

## Scénarios de démo impactés

- [ ] A — attaque baseline (non protégé)
- [ ] B — attaque bloquée (protégé)
- [ ] C — faux positif contrôlé
- [ ] Aucun
