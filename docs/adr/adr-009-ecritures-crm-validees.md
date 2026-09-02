# ADR-009 - Outils d'écriture CRM à validation humaine

## Décision
`create_task` / `update_opportunity` → retour `NeedsConfirmation` à l'interface AVANT exécution.

## Justification
Confiance des équipes commerciales, aucune écriture non consentie.

## Alternatives écartées
Écriture directe : risque inacceptable en production.
