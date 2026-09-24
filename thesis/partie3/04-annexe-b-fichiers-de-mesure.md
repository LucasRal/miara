# Annexe B — Fichiers de mesure archivés {-}

Le chapitre 8 s'interdit tout chiffre qui ne provienne d'un fichier versionné
dans le dépôt. Cette annexe rassemble ces fichiers, indique ce que chacun
contient et rappelle les réserves qui s'y attachent, afin qu'un lecteur puisse
retrouver n'importe quelle valeur sans parcourir le chapitre.

## Campagne d'évaluation de référence {-}

Les trois fichiers portent le même horodatage, `20260922T132654`, et la même
empreinte de code, `d793943-sale`, dont le suffixe indique que le dépôt
comportait des modifications non validées au moment de l'exécution : le rapport
n'est pas rejouable à l'identique depuis cette seule empreinte.

L'historique du dépôt a été réécrit le 24 septembre 2026 pour corriger
l'identité d'auteur des commits. Les empreintes citées dans cette annexe et
dans le chapitre 8 sont celles de l'historique actuel : celle de la campagne de
référence, `e6ebfc6` jusque-là, est devenue `d793943`. La réécriture n'a touché
que l'identité d'auteur ; l'arbre de fichiers désigné est le même, et les
fichiers de mesure ont été renommés pour que leur nom continue de désigner un
commit existant.

`evals/reports/20260922T132654_d793943-sale.json`
: Rapport complet, structuré, versionné par un numéro de format. Contient le
  détail CV par CV et question par question, les agrégats de chaque suite, le
  résultat du dépouillement de la relecture du juge et le verdict de chacun des
  treize seuils. C'est le fichier de référence de tous les tableaux du
  chapitre 8, y compris ceux qui sont présentés comme calculés à partir de son
  détail.

`evals/reports/20260922T132654_d793943-sale.md`
: Résumé rédigé, produit par la même exécution. Il contient, sans
  retraitement, les tableaux de classement par offre, la matrice de confusion
  par strate, les mesures de l'assistant commercial, les corrélations du coach
  par critère, la nature des preuves avancées et les cas adverses.

`evals/reports/20260922T132654_d793943-sale_relecture.md`
: Feuille de relecture humaine des verdicts du modèle juge. Neuf cas tirés sur
  quarante-sept, chacun avec le fait attendu, la réponse complète de l'agent,
  le verdict du juge et l'avis du relecteur. Le seul désaccord y est motivé.

## Seuils et jeu de données {-}

`evals/thresholds.yaml`
: Les treize engagements de niveau de service, chacun assorti de sa
  justification rédigée. Le fichier énonce en tête la règle qui interdit de
  fixer une barre sur une mesure déjà obtenue.

`evals/data/README.md`
: Provenance du jeu de données de référence, procédure de régénération,
  définition des strates, colonnes des fichiers d'annotation, situation au
  regard des données personnelles, et liste explicite de ce qui reste à la
  charge d'un annotateur humain.

`evals/data/hr/<offre>/labels.csv`, `niveaux.json`, `double_annotation.csv`
: Annotations de présélection. Les colonnes de `double_annotation.csv` sont
  vides : la double annotation humaine de dix pour cent du jeu n'a pas été
  réalisée, et aucune valeur d'accord n'a été fabriquée pour la remplacer.

`evals/data/sales/questions.jsonl`, `evals/data/coach/notes.jsonl`
: Annotations des trente questions commerciales et des dix comptes rendus de
  coaching. Les annotations de coaching portent la mention qu'elles restent à
  confirmer par un annotateur humain.

## Campagne de charge {-}

`bench/reports/20260922-134336/env.json`
: Relevé d'environnement de la campagne : machine, versions logicielles, table
  des alias de modèles et présence ou absence des clés de chaque fournisseur.
  C'est ce fichier qui atteste, pour l'ensemble du chapitre 8, que les alias
  sont retombés sur leurs replis faute de clé pour le fournisseur primaire.

`bench/reports/20260922-134336/rapport.md` et `campagne.json`
: Résultats de la campagne de charge, agrégés et détaillés.

`bench/reports/20260922-134336/runs.csv`, `questions.csv`, `file_light.csv`,
`taches.csv`, `reproductibilite.csv`
: Mesures brutes, une ligne par lot, par question, par sonde et par tâche.

`bench/reports/20260922-134336/figures/`
: Figures produites automatiquement à partir des mesures brutes.

`bench/reports/20260922-155013/` et `bench/reports/20260922-155731/`
: Contre-mesure de la famine de la file `light`, scénario `mixed` à concurrence
  8, une répétition chacune : d'abord la topologie fautive (un travailleur sur
  `heavy,light`), puis la topologie corrigée (un travailleur par file). La clé
  `campagne.topologie_workers` de `campagne.json` dit laquelle a été mesurée.

## Démonstration {-}

`thesis/soutenance/demo.md`
: Déroulé reproductible de la démonstration de soutenance.

`thesis/soutenance/demo/`
: Script de rejeu, journaux datés des répétitions, captures d'écran et, le cas
  échéant, enregistrement vidéo. Le compte rendu factuel des répétitions, avec
  leurs temps mesurés et leurs incidents, se trouve dans `repetitions.md`.
