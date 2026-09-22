"""Campagne de charge (chapitre 8) : débit, latence, coût, mémoire.

Le harnais d'évaluation (`evals/`) répond à « est-ce que ça note juste ». Cette
campagne répond à « est-ce que ça tient la charge », et elle s'appuie sur le
même socle : même organisation d'évaluation d'identifiant fixe, même jeu doré,
mêmes fonctions de percentile. Rien n'est recalculé ici de ce qui existe déjà
dans `evals/metriques.py`.

Une différence de fond avec le harnais, assumée et voulue : **les scénarios RH
passent par de VRAIS workers Celery**, pas par le sémaphore asyncio du
harnais. Le paramètre mesuré par la carte s'appelle `worker_concurrency` ; le
pic mémoire, le journal `task_events` et la preuve que la file `light` n'est
pas affamée n'existent que s'il y a des processus workers et deux files. Le
harnais, lui, mesure la qualité et n'a aucune raison de payer ce montage.

Conséquences à connaître avant de lire un chiffre :

- les tâches Celery passent par `acquire_slot` (limiteur de débit par
  organisation, `HR_LLM_CALLS_PER_MINUTE`), que le harnais court-circuite. Le
  débit mesuré ici est donc celui du produit, limiteur compris ;
- les appels partis d'un worker ne sont pas préfixés `eval.` dans `llm_calls`
  (le worker construit sa propre passerelle). Le coût d'un lot se relit par
  `trace_id`, qui vaut l'identifiant de campagne : c'est la même source de
  vérité que `stats_json`.
"""

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SORTIES = RACINE / "bench" / "reports"
