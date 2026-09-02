# ADR-011 - Alias de modèles (jamais de nom de modèle en dur)

## Décision
`sales.route` / `sales.synthesize` / `hr.extract` / `hr.score` définis en config LiteLLM avec replis.

## Justification
Substitution fournisseur = changement de config ; balayages coût/qualité par alias comme expériences du mémoire.

## Alternatives écartées
Noms de modèles en dur dans le code : couplage fournisseur, expériences non reproductibles.
