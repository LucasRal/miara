# ADR-007 - Notation RH par CV indépendant (pas de méga-prompt multi-CV)

## Décision
Chaque CV est noté seul contre la grille issue de l'offre.

## Justification
Parallélisme (500 CV), retries unitaires bon marché, pas de biais de position, grille appliquée identiquement.

## Alternatives écartées
Méga-prompt multi-CV. Option conservée : passe de calibration comparative sur le top-K (ex. 10 finalistes), là où le jugement relatif apporte de la valeur.
