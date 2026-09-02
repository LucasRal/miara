# ADR-006 - Asynchrone : Celery + RabbitMQ (broker) + Redis (résultats/cache)

## Décision
Deux files dès le départ : `heavy` (extraction, scoring LLM) / `light` (sync CRM, notifications) ; tâches idempotentes par `job_id`.

## Justification
Un lot de 500 CV ne doit jamais affamer une écriture CRM.

## Alternatives écartées
File unique : famine des tâches légères. Redis seul comme broker : garanties moindres côté routage/ack.
