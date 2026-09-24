# Campagne de charge Miara

- Date : 2026-09-22T15:57:31+00:00 · empreinte `d793943-sale`
- Machine : Intel Core Processor (Haswell, no TSX) · 6 vCPU · 11671 Mo
- Graine : 20260922
- Budget : 1.3655 / 3.0 USD (0 point(s) non exécuté(s) faute de budget)
- Durée de la campagne : 300.3 s

## Réserves de lecture

- Clé Anthropic absente : True. Les alias basculent alors sur leurs replis OpenAI ; les coûts et les latences publiés sont ceux des replis, pas des modèles primaires.
- Limiteur de débit actif : 60 appels LLM par minute et par organisation, soit un plafond théorique de 30 CV/min (2 appels par CV).
- Les lots de plus de 180 CV réemploient des documents du jeu doré : voir la colonne `documents_distincts` de `runs.csv`.
- Aucun point aberrant n'a été retiré ; ceux qui sont signalés le sont dans `reproductibilite.csv` (colonne `indices_aberrants` du JSON).

## Lots RH

| Configuration | Rép. | CV | Débit moyen (CV/min) | Coût moyen (USD) | Coût/CV | Échecs | Pic mémoire (Mo) | Statuts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed@c8 | 1 | 100 | 32.84 | 1.1463 | 0.0115 | 0 | 3493.1 | termine |

## Latence conversationnelle

| Série | Tours | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| sales-30 à vide | 0/0 | None | None | None |
| mixed à vide | 30/30 | 2.07 | 3.66 | 5.01 |
| mixed sous charge | 30/30 | 2.46 | 5.06 | 8.14 |

## Critères d'acceptation

- `mixed` p95 sous charge / p95 à vide = 1.383 (seuil < 1.5) -> **tenu**

## File `light` (sonde `core.ping`)

| Contexte | Sondes | p50 | p95 | Sans réponse |
| --- | --- | --- | --- | --- |
| a_vide | 5 | 0.01 | 0.09 | 0 |
| sous_charge | 5 | 0.01 | 0.02 | 0 |

Topologie mesurée : **un worker par file** (`heavy` à la concurrence du point, `light` à 2), celle des unités systemd `miara-worker-heavy` et `miara-worker-light` du VPS.

Famine de la file `light` : **non constatée** (p95 sous charge 0.02 s contre 0.09 s à vide, aucune sonde perdue).
