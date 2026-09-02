# ADR-003 - Auth maison : JWT émis par FastAPI + memberships

## Décision
Tables users / organizations / memberships(user, org, rôle owner-admin-sales-hr) ; un utilisateur peut appartenir à plusieurs organisations.

## Justification
Contrôle total du modèle multi-org, pas de dépendance externe.

## Alternatives écartées
NextAuth, Keycloak : complexité inutile.
