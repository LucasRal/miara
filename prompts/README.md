# Prompts versionnés (ADR-010)

Un dossier par agent, un fichier par version : `prompts/<agent>/v<N>.md`.

- Un changement de prompt = un nouveau fichier `v<N+1>.md` — on n'écrase jamais une version.
- La version utilisée est journalisée à chaque appel LLM (`llm_calls.prompt_version`).
- Agents prévus : `sales_route`, `sales_synthesize`, `hr_extract`, `hr_score` (mêmes noms que les alias de modèles, ADR-011).
