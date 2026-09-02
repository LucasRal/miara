# ADR-001 - Monolithe modulaire (pas de microservices)

## Décision
Modules internes auth/hr/sales/core à interfaces nettes, un seul déployable.

## Justification
1 dev, 6 mois, simplicité opérationnelle ; la discipline de frontières entre modules est conservée.

## Alternatives écartées
Microservices : taxe opérationnelle injustifiée à cette échelle.
