# ADR-004 - Passerelle LLM : LiteLLM Router en processus

## Décision
Alias par tâche, replis configurés, journalisation des coûts dans `llm_calls` par organisation.

## Justification
Substitution de fournisseur par configuration ; mesure des coûts par org intégrée.

## Alternatives écartées
Proxy LiteLLM séparé : un service de plus à opérer sans Docker.
