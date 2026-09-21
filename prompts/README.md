# Prompts versionnés (ADR-010)

Convention : `prompts/<agent>/v<N>.md` — un fichier par version, jamais
d'écrasement. Un changement de prompt = un nouveau fichier `v<N+1>.md`.

Chargement : `app.core.llm.load_prompt(agent, version=None)` renvoie
`(texte, version)` — dernière version par défaut. La version utilisée est
journalisée dans `llm_calls.prompt_version` à chaque appel (reproductibilité
des expériences, chap. 8 du mémoire).

Le nom du dossier est le `prompt_name` de l'`AgentDefinition`, donc le nom de
l'agent lui-même — un agent peut enchaîner plusieurs alias de modèles (routage
puis synthèse) avec UN seul prompt système.

Agents : `echo` (test du runtime), `sales.assistant` (assistant commercial) ;
à venir : `sales.coach`, `hr.extract`, `hr.score`.
