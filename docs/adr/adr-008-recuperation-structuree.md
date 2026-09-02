# ADR-008 - Récupération contextuelle structurée (pas d'embeddings)

## Décision
Requêtes typées et déterministes vers Salesforce choisies par le modèle + ContextBuilder en code (classement, budget de tokens).

## Justification
Données CRM déjà structurées : résultats exacts et frais, latence < 3 s, explicabilité.

## Alternatives écartées
RAG vectoriel : approximatif, latence d'indexation, inutile pour du structuré. À réévaluer si données non structurées (transcriptions d'appels).
