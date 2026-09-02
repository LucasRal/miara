# ADR-005 - Salesforce : OAuth par locataire, credentials chiffrés

## Décision
Chaque organisation connecte son Salesforce ; le client est derrière une interface abstraite `CRMPort`.

## Justification
Multi-locataire propre ; le cœur ne dépend pas de Salesforce.

## Alternatives écartées
Couplage direct : verrouillage architectural.
