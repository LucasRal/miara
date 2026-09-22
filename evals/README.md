# Harnais d'évaluation

Rejoue le jeu doré contre le code de production et écrit un rapport daté,
comparable, et qui fait échouer la commande si une métrique passe sous son
seuil.

```bash
make eval                                      # les quatre suites
make eval ARGS="--suite hr --limit 5"          # une suite, 5 CV par offre
make eval ARGS="--prompt-version hr.score=1"   # rejoue avec l'ancien prompt
make eval ARGS="--alias-override hr.score=openai/gpt-4o"
make eval-compare AVANT=evals/reports/a.json APRES=evals/reports/b.json
make eval-verifier RAPPORT=evals/reports/a.json
make eval-relire RAPPORT=evals/reports/a.json   # après avoir rempli la feuille
```

## Ce qu'il y a dans ce dossier

| Fichier | Rôle |
| --- | --- |
| `data/` | le jeu doré, versionné et régénérable (`make gen-data`). Provenance et procédure : `data/README.md` |
| `run.py` | la ligne de commande : choix des suites, écriture du rapport, verdict des seuils |
| `harnais.py` | organisation d'évaluation, passerelle qui marque les appels `eval.*`, surcharge d'alias |
| `suites/` | une par cas d'usage : `hr`, `sales`, `coach`, `adverse` |
| `metriques.py` | Spearman, top-K, F1, percentiles, matrice de confusion. Fonctions pures, testées à la main |
| `juge.py` | juge LLM pour les faits énoncés en langage libre, et sa feuille de relecture |
| `seuils.py` + `thresholds.yaml` | les barres à tenir, et pourquoi chacune existe |
| `resume.py` | le résumé markdown : les tableaux du chapitre 8, sans retraitement |
| `compare.py` | écarts entre deux rapports, avec le sens de chaque métrique |
| `reports/` | les rapports produits. Un rapport archivé = un tableau du mémoire |

## Les quatre suites

**HR** rejoue la présélection sur les 3 offres et 180 CV : Spearman contre la
note de référence, précision top-10 et top-20, exactitude sur les critères
éliminatoires, taux d'échec, temps et coût par CV, matrice de confusion par
strate.

**Sales** rejoue les 30 questions contre un `FakeCRM` peuplé par la graine du
jeu doré : F1 sur le choix des outils, entités citées, faits de référence
énoncés, nombre d'appels au modèle, latence p50 et p95.

**Coach** rejoue les 10 comptes rendus annotés : corrélation par critère et
sur la note globale, et classement de chaque preuve avancée. Le prompt exige
une citation du texte ou le constat explicite d'une absence ; le harnais
distingue les deux fautes possibles, parce qu'elles n'ont pas la même
gravité. Une citation introuvable dans le texte est une hallucination, et son
seuil est à zéro. Une appréciation sans citation ni constat est un écart de
forme, compté à part.

**Adverse** rejoue les cas piégés : 5 CV porteurs d'une injection, 2 fichiers
corrompus, les CV scannés, et un texte de coaching qui réclame 100/100. Pour
les injections, la mesure qui fait échouer la commande est la SÉCURITÉ, c'est
à dire le nombre de consignes suivies, repéré par une note qui monte vers ce
que l'injection réclame. Une note qui bouge sans monter est une erreur de
notation ordinaire : elle est rapportée à part, avec le nombre de tentatives
signalées dans les réserves du rapport de notation.

## Trois choses à savoir avant de lire un chiffre

1. **Le harnais appelle le code de production.** Il ne remonte pas ses propres
   prompts : `run_extraction`, `run_profile`, `run_scoring` et le runtime
   d'agent sont ceux du dépôt. Un changement de prompt se voit donc
   immédiatement dans les rapports.

2. **Les mesures vivent dans une organisation dédiée**, d'identifiant fixe,
   isolée par RLS comme n'importe quel locataire. Tous les appels sont
   journalisés dans `llm_calls` sous `eval.*` : le coût d'une campagne
   d'évaluation se lit d'une requête et ne pollue pas les statistiques
   d'usage montrées aux clients.

3. **Le juge LLM n'est pas cru sur parole.** Il ne tranche que des présences
   de faits, jamais une qualité, et chaque exécution tire un échantillon
   déterministe de ses verdicts dans un fichier `*_relecture.md`. On remplit
   la ligne « Ton avis » de chaque cas, puis `make eval-relire` dépouille la
   feuille, écrit le taux d'accord dans le rapport et fait passer `juge_relu`
   à true. Une feuille à moitié remplie est refusée : relire les cas faciles
   et laisser les autres en blanc gonflerait le taux. Tant que la relecture
   n'est pas faite, les chiffres qui dépendent du juge ne sont pas validés,
   et le résumé le dit en toutes lettres.

## Limites connues

- `--live` (bac à sable Salesforce réel) n'est pas branché : la commande le
  dit et s'arrête, plutôt que de faire croire à une exécution distante.
- Les corrélations de la suite Coach portent sur 10 textes : elles bougent
  beaucoup, et le seuil associé est bas à dessein.
- La précision top-K départage les ex aequo de la référence par le nom de
  fichier. C'est déterministe, mais arbitraire à la frontière du K.
- Une exécution avec `--limit` est marquée PARTIELLE dans le rapport et dans
  le résumé : ses chiffres ne valent pas pour le jeu complet.
