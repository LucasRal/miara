# ADR-002 - Multi-location : base partagée + Row-Level Security PostgreSQL

## Décision
`organization_id` sur toute table métier, politiques RLS, `SET LOCAL app.current_org` par requête.

## Justification
Isolation garantie au niveau BDD, testable.

## Alternatives écartées
Schéma-par-locataire : migrations pénibles. Base-par-locataire : surdimensionné.
