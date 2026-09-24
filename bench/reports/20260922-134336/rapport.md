# Campagne de charge Miara

- Date : 2026-09-22T13:43:36+00:00 · empreinte `d793943-sale`
- Machine : Intel Core Processor (Haswell, no TSX) · 6 vCPU · 11671 Mo
- Graine : 20260922
- Budget : 13.467116 / 18.0 USD (0 point(s) non exécuté(s) faute de budget)
- Durée de la campagne : 3537.1 s

## Ce qui a été exécuté, et ce qui ne l'a pas été

*Section ajoutée au rapport après la campagne, le 22 septembre 2026, parce que
le rapport engendré ne portait pas cette information et qu'un tableau du
chapitre 8 en dépend. Aucun chiffre de mesure n'a été modifié.*

La matrice complète décrite par la carte de charge (5 scénarios, concurrences
2, 4 et 8, trois répétitions par point) représente **39 points pour 91,94 USD
estimés**, chiffre reproductible par `make bench ARGS="--plan-seulement"`. Le
plafond de la campagne a été fixé à 18 USD, et le plan soumis a donc été réduit
AVANT exécution, à 12 points :

| Scénario | Concurrences exécutées | Répétitions | CV notés |
| --- | --- | --- | --- |
| hr-50 | 2, 4 et 8 | 3 par concurrence | 450 |
| hr-100 | 4 | 1 | 100 |
| hr-500 | 8 | 1 | 500 |
| mixed | 8 | 1 | 100 |
| sales-30 | sans objet | 1 | aucun |

Soit **1 150 CV notés, 0 échec**, pour 13,467116 USD sur les 18 autorisés.

La ligne « Budget » de l'en-tête dit « 0 point non exécuté faute de budget » :
elle est exacte pour le plan SOUMIS, et elle ne doit pas se lire comme si la
matrice de la carte avait tourné en entier. Ce qui manque, et qui manque
sciemment : hr-50, hr-100, hr-500 et mixed aux concurrences non exécutées,
les répétitions 2 et 3 de hr-100, hr-500, mixed et sales-30. En conséquence, le
critère de reproductibilité n'est établi que sur hr-50, seul scénario répété
trois fois, et le rapport de famine de la file légère repose sur une seule
exécution de mixed.

## Réserves de lecture

- Clé Anthropic absente : True. Les alias basculent alors sur leurs replis OpenAI ; les coûts et les latences publiés sont ceux des replis, pas des modèles primaires.
- Limiteur de débit actif : 60 appels LLM par minute et par organisation, soit un plafond théorique de 30 CV/min (2 appels par CV).
- Les lots de plus de 180 CV réemploient des documents du jeu doré : voir la colonne `documents_distincts` de `runs.csv`.
- Aucun point aberrant n'a été retiré ; ceux qui sont signalés le sont dans `reproductibilite.csv` (colonne `indices_aberrants` du JSON).

## Lots RH

| Configuration | Rép. | CV | Débit moyen (CV/min) | Coût moyen (USD) | Coût/CV | Échecs | Pic mémoire (Mo) | Statuts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr-100@c4 | 1 | 100 | 19.98 | 1.1557 | 0.0116 | 0 | 1533.6 | termine |
| hr-500@c8 | 1 | 500 | 30.3 | 5.6568 | 0.0113 | 0 | 2926.6 | termine |
| hr-50@c2 | 3 | 50 | 9.83 | 0.5791 | 0.0116 | 0 | 933.0 | termine |
| hr-50@c4 | 3 | 50 | 19.3233 | 0.573 | 0.0115 | 0 | 1487.6 | termine |
| hr-50@c8 | 3 | 50 | 31.6533 | 0.5684 | 0.0114 | 0 | 2604.9 | termine |
| mixed@c8 | 1 | 100 | 32.41 | 1.1536 | 0.0115 | 0 | 2680.9 | termine |

## Latence conversationnelle

| Série | Tours | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| sales-30 à vide | 30/30 | 2.45 | 4.37 | 5.45 |
| mixed à vide | 30/30 | 2.58 | 4.29 | 5.1 |
| mixed sous charge | 30/30 | 2.27 | 3.54 | 4.11 |

## Critères d'acceptation

- `mixed` p95 sous charge / p95 à vide = 0.825 (seuil < 1.5) -> **tenu**
- Reproductibilité debit_cv_par_minute sur hr-50@c2 (3 répétitions) : écart relatif 0.0336 (seuil 0.1) -> **tenu**
- Reproductibilité debit_cv_par_minute sur hr-50@c4 (3 répétitions) : écart relatif 0.0673 (seuil 0.1) -> **tenu**
- Reproductibilité debit_cv_par_minute sur hr-50@c8 (3 répétitions) : écart relatif 0.0423 (seuil 0.1) -> **tenu**

## File `light` (sonde `core.ping`)

| Contexte | Sondes | p50 | p95 | Sans réponse |
| --- | --- | --- | --- | --- |
| a_vide | 5 | 0.01 | 0.07 | 0 |
| sous_charge | 5 | 0.01 | 25.37 | 2 |

Famine de la file `light` : **constatée**. 2 sonde(s) `core.ping` sans réponse dans le délai et p95 à 25.37 s sous charge contre 0.07 s à vide. Un worker unique consomme `heavy` et `light` (`make worker` : `-Q heavy,light`) : les slots occupés par le scoring retardent les tâches légères. Le critère `mixed` de la carte reste tenu parce que l'agent commercial répond dans le processus FastAPI, sans passer par Celery.

## Réparations post-campagne

Aucune tâche n'a été rejouée et aucun appel LLM n'a été refait : les deux
corrections ci-dessous se déduisent des données déjà enregistrées.

- `taches.csv` a été réécrit depuis la table `task_events`. La campagne a
  tourné avec une version de `taches_du_lot` qui retrouvait les tâches par
  `trace_id` seulement ; or `hr.rank_run` reçoit en premier argument la liste
  des retours du `chord`, pas l'identifiant du lot, et restait donc invisible.
  C'était la seule tâche de la file `light` du pipeline : le fichier initial
  ne contenait que les 2300 tâches `heavy`. Il en contient maintenant 2312,
  dont les 12 `hr.rank_run` de la file `light`.
- Le verdict de famine de la file `light` a été ajouté à partir des sondes
  `core.ping` déjà présentes dans `file_light.csv`.
