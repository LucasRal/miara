# ADR-006 - Asynchrone : Celery + RabbitMQ (broker) + Redis (résultats/cache)

## Décision
Deux files dès le départ : `heavy` (extraction, scoring LLM) / `light` (sync CRM, notifications) ; tâches idempotentes par `job_id`.

## Justification
Un lot de 500 CV ne doit jamais affamer une écriture CRM.

## Alternatives écartées
File unique : famine des tâches légères. Redis seul comme broker : garanties moindres côté routage/ack.

## Conséquence d'exploitation (ajoutée le 22 septembre 2026)

Deux files ne suffisent pas : il faut **deux consommateurs**. Un worker unique
abonné à `heavy,light` prend ses messages dans les deux files avec les mêmes
slots, et la file `light` attend derrière le scoring exactement comme si elle
n'existait pas. La campagne de charge du 22 septembre 2026 l'a mesuré sur cette
topologie : 3 sondes `core.ping` sur 5 sans réponse en 30 s, p95 à 11,72 s
contre 0,07 s à vide (`bench/reports/20260922-155013/`).

La topologie de référence est donc un worker par file, `heavy` à
`WORKER_HEAVY_CONCURRENCY` et `light` à `WORKER_LIGHT_CONCURRENCY` : c'est ce
que font les unités `miara-worker-heavy` et `miara-worker-light` du VPS, ce que
fait `make worker` en développement, et ce que monte la campagne de charge par
défaut. Augmenter la concurrence d'un worker unique ne remplace pas cette
séparation : cela déplace le seuil de famine sans le supprimer.
