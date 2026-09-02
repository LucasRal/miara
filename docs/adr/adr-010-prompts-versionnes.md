# ADR-010 - Prompts versionnés dans le dépôt

## Décision
`prompts/<agent>/v<N>.md`, `prompt_version` journalisée à chaque appel.

## Justification
Reproductibilité des expériences (chap. 8), diffs lisibles en revue de code.

## Alternatives écartées
Prompts en BDD : hors revue de code.
