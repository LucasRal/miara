# Campagne de charge Miara

- Date : 2026-09-22T15:50:13+00:00 · empreinte `e6ebfc6-sale`
- Machine : Intel Core Processor (Haswell, no TSX) · 6 vCPU · 11671 Mo
- Graine : 20260922
- Budget : 1.426531 / 3.0 USD (0 point(s) non exécuté(s) faute de budget)
- Durée de la campagne : 307.8 s

## Réserves de lecture

- Clé Anthropic absente : True. Les alias basculent alors sur leurs replis OpenAI ; les coûts et les latences publiés sont ceux des replis, pas des modèles primaires.
- Limiteur de débit actif : 60 appels LLM par minute et par organisation, soit un plafond théorique de 30 CV/min (2 appels par CV).
- Les lots de plus de 180 CV réemploient des documents du jeu doré : voir la colonne `documents_distincts` de `runs.csv`.
- Aucun point aberrant n'a été retiré ; ceux qui sont signalés le sont dans `reproductibilite.csv` (colonne `indices_aberrants` du JSON).

## Lots RH

| Configuration | Rép. | CV | Débit moyen (CV/min) | Coût moyen (USD) | Coût/CV | Échecs | Pic mémoire (Mo) | Statuts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed@c8 | 1 | 100 | 29.79 | 1.1466 | 0.0115 | 0 | 2707.2 | termine |

## Latence conversationnelle

| Série | Tours | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| sales-30 à vide | 0/0 | None | None | None |
| mixed à vide | 30/30 | 2.42 | 3.69 | 4.87 |
| mixed sous charge | 30/30 | 2.43 | 3.6 | 4.41 |

## Critères d'acceptation

- `mixed` p95 sous charge / p95 à vide = 0.976 (seuil < 1.5) -> **tenu**

## File `light` (sonde `core.ping`)

| Contexte | Sondes | p50 | p95 | Sans réponse |
| --- | --- | --- | --- | --- |
| a_vide | 5 | 0.01 | 0.07 | 0 |
| sous_charge | 5 | 6.17 | 11.72 | 3 |

Famine de la file `light` : **constatée**. 3 sonde(s) `core.ping` sans réponse dans le délai et p95 à 11.72 s sous charge contre 0.07 s à vide. Un worker unique consomme `heavy` et `light` (`make worker` : `-Q heavy,light`) : les slots occupés par le scoring retardent les tâches légères. Le critère `mixed` de la carte reste tenu parce que l'agent commercial répond dans le processus FastAPI, sans passer par Celery.
