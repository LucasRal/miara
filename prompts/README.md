# Prompts versionnés (ADR-010)

Convention : `prompts/<agent>/v<N>.md` — un fichier par version, jamais
d'écrasement. Un changement de prompt = un nouveau fichier `v<N+1>.md`.

Chargement : `app.core.llm.load_prompt(agent, version=None)` renvoie
`(texte, version)` — dernière version par défaut. La version utilisée est
journalisée dans `llm_calls.prompt_version` à chaque appel (reproductibilité
des expériences, chap. 8 du mémoire).

Agents prévus (cartes [SALES] / [HR]) : `sales_route`, `sales_synthesize`,
`sales_coach`, `hr_extract`, `hr_score`.
