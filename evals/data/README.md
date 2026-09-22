# Jeu doré Miara - provenance, procédure, licence

Jeu de données de référence du chapitre 8 (évaluation). Il est **entièrement
synthétique** : aucune donnée réelle, aucun CV de personne physique, aucune
entreprise existante. Il est versionné dans le dépôt et régénérable à
l'identique par `make gen-data`.

| Bloc | Emplacement | Volume |
| --- | --- | --- |
| Offres et grilles | `hr/<offre>/offre.md`, `hr/<offre>/grille.json` | 3 offres, 6 critères chacune |
| CV annotés | `hr/<offre>/cv/`, `hr/<offre>/labels.csv` | 180 CV (3 x 60), PDF et DOCX |
| Niveaux de construction | `hr/<offre>/niveaux.json` | 180 profils, 6 niveaux chacun |
| Double annotation à faire | `hr/<offre>/double_annotation.csv` | 18 CV (10 %), **vide** |
| Cas adverses | `adverse/` | 5 injections, 3 scannés, 2 corrompus |
| Questions commerciales | `sales/questions.jsonl`, `sales/crm_seed.json` | 30 questions, 45 enregistrements |
| Comptes rendus de coaching | `coach/notes.jsonl`, `coach/injection.txt` | 10 textes annotés (3 bons, 4 moyens, 3 faibles) |

## 1. Provenance

### Ce qui est écrit à la main (source, jamais régénéré)

- `hr/<offre>/offre.md` : les trois offres d'emploi, rédigées en français pour
  une entreprise fictive (Ardentis). Développeur Full Stack, Commercial B2B,
  Assistant RH.
- `hr/<offre>/grille.json` : la grille d'évaluation de l'offre (intitulé,
  poids de 1 à 5, description, caractère éliminatoire). Elle est validée par le
  schéma de production `app.hr.criteria.Criteria` : le jeu doré et le pipeline
  manipulent exactement le même objet.
- `hr/<offre>/briques.json` : pour chaque critère, **six formulations** de CV
  correspondant aux niveaux 0 à 5 de la grille (0 = le CV n'en parle pas,
  3 = pratique régulière et autonome, 5 = expertise chiffrée). Plus les
  éléments d'identité du métier (intitulés de poste, formations, divers).
- `sales/crm_seed.json` : le bac à sable CRM (6 comptes, 10 contacts,
  9 opportunités, 4 cas, 10 activités, 6 étapes).
- `sales/questions.jsonl` : les 30 questions et leur annotation.
- `coach/notes.jsonl` : les 10 comptes rendus et leur annotation par critère.

### Ce qui est généré (`make gen-data`)

`backend/scripts/gen_cvs.py` compose les 180 CV et les 10 cas adverses, puis
écrit `labels.csv`, `niveaux.json`, `double_annotation.csv` et
`adverse/labels.csv`. Graine fixée à 2026. Deux exécutions produisent des
fichiers **identiques octet pour octet** (horodatages des documents figés) :
c'est vérifié par `backend/tests/test_jeu_dore.py`.

## 2. Pourquoi les labels ne sont pas des jugements

La carte interdit des labels produits par le modèle, et un annotateur unique
qui noterait 180 CV à la main produirait une référence lente à établir,
difficile à rejouer et instable dans le temps. La méthode retenue est la
**vérité de construction** :

1. un profil contrôlé est tiré d'abord : un niveau de 0 à 5 par critère de la
   grille, selon la strate visée ;
2. le texte du CV est l'assemblage des briques correspondant à ces niveaux, ce
   qui rend le niveau lisible dans le CV, ligne par ligne ;
3. le score de référence est **calculé** à partir de ces mêmes niveaux et des
   poids de la grille, par `align_with_grid` puis `compute_overall`
   (`app.hr.schemas`) - la fonction exacte qu'exécute le pipeline en
   production : moyenne pondérée ramenée sur 100, et 0 si un critère
   éliminatoire est manqué (note strictement inférieure à 2 sur 5).

Le label n'est donc l'opinion de personne : c'est la règle de la grille
appliquée à un profil connu. Il est recalculable en une ligne depuis
`niveaux.json`, et tout écart entre `labels.csv` et le pipeline est un écart
de lecture du CV par le modèle, pas un désaccord d'appréciation.

**Limite à assumer dans le mémoire** : la construction fixe le niveau *avant*
la rédaction, donc le CV est par nature lisible et cohérent. Un vrai CV est
ambigu, lacunaire, parfois trompeur. Le jeu mesure la capacité du pipeline à
appliquer une grille, pas sa capacité à démêler un CV réellement confus. Les
cas adverses et la validation humaine sur échantillon (section 4) sont là pour
compenser partiellement ce biais.

### Strates

15 CV par strate et par offre, mélangés dans la numérotation des fichiers pour
que ni le numéro ni le format ne trahissent le niveau.

| Strate | Niveaux tirés | Plage de score observée |
| --- | --- | --- |
| `excellent` | éliminatoires à 5, autres 4-5 | 89 à 98 |
| `bon` | éliminatoires 3-4, autres 3-4 | 60 à 78 |
| `limite` | éliminatoires à 2, autres 1-3 | 29 à 51 |
| `hors_profil` | un éliminatoire à 0 ou 1 | 0 (règle éliminatoire) |

Les plages sont disjointes et ordonnées : c'est ce qui permet de mesurer une
corrélation de rang et une précision top-K qui veulent dire quelque chose.

## 3. Colonnes et formats

`hr/<offre>/labels.csv`

| Colonne | Contenu |
| --- | --- |
| `candidate_file` | nom du fichier dans `cv/` |
| `strate` | `excellent`, `bon`, `limite`, `hors_profil` |
| `score_ref_0_100` | score de référence calculé |
| `must_have_ok` | `oui` / `non` (critères éliminatoires satisfaits) |
| `annotateur` | `generateur-v1 (verite de construction)` |
| `date` | date de constitution du jeu (figée) |

`sales/questions.jsonl` - une question par ligne : `question`,
`expected_tools[]` (ensemble minimal d'outils de lecture attendus),
`expected_entities[]` (références du bac à sable que la réponse doit citer),
`gold_facts[]` (`ref`, `field`, `value`, `texte` : le fait doit être vrai dans
le CRM, et `texte` en donne la formulation attendue). Trois questions portent
`attendu_aucune_donnee` : la bonne réponse est de dire qu'il n'y a rien, sans
inventer.

Les références (`@acc_norelec`) et les dates relatives (`today+45`) rendent le
jeu rejouable tel quel sur `FakeCRM` (mode démo) comme sur une organisation
Salesforce de bac à sable : `backend/scripts/crm_seed.py` charge la graine et
renvoie la table référence -> identifiant attribué par le CRM.

`coach/notes.jsonl` - `criteres_0_5` donne le niveau visé sur les cinq critères
de `prompts/sales.coach/v1.md`, et `reference_0_100` en est la moyenne (les
cinq critères pèsent le même poids). Convention : quand le client n'exprime
aucune objection, `gestion_des_objections` vaut 3 (neutre).

## 4. Ce qui reste à faire par l'annotateur humain

Deux points ne peuvent pas être produits par un programme et restent à la
charge du propriétaire du mémoire.

1. **Double annotation de 10 %** (`hr/<offre>/double_annotation.csv`,
   6 CV par offre, 18 au total). Procédure : ouvrir le CV sans consulter
   `labels.csv`, appliquer la grille de l'offre critère par critère, reporter
   le score et `must_have_ok`, signer et dater. La cohérence se mesure ensuite
   entre ces colonnes et `labels.csv`. Les colonnes sont **volontairement
   vides** : aucune valeur d'accord n'a été fabriquée, et le critère
   d'acceptation « auto-cohérence ≥ 0,8 » ne pourra être coché qu'après ce
   passage.
2. **Confirmation des annotations de coaching** (`coach/notes.jsonl`,
   `annotateur: construction-v1 (a confirmer par l'annotateur humain)`). Les
   niveaux par critère ont été posés à partir des ancres 0/3/5 de la grille du
   coach ; ils demandent une relecture humaine avant d'être cités comme
   référence dans le mémoire.

Règle de conduite, reprise de la carte : **ne jamais modifier un label après
avoir vu les scores produits par l'IA**. Toute correction se fait sur la grille
ou sur les niveaux de construction, puis par régénération complète, et se
journalise dans l'historique git.

## 5. Régénération

```bash
make gen-data                                  # tout le jeu, graine 2026
cd backend && uv run python -m scripts.gen_cvs --offre commercial-b2b
cd backend && uv run pytest tests/test_jeu_dore.py   # contrôles du jeu
```

Modifier une offre, une grille ou une brique change les CV : régénérer, puis
relire les écarts de `labels.csv` dans le diff git avant de committer.

## 6. Licence et données personnelles

Jeu produit pour le mémoire M2 Miara, diffusé sous la même licence que le
dépôt. Il ne contient aucune donnée à caractère personnel au sens du RGPD :

- prénoms et noms tirés de listes fictives, associés au hasard ;
- entreprises, écoles et villes citées dans un cadre fictif (les villes
  existent, les employeurs cités n'existent pas) ;
- adresses électroniques sur le domaine réservé `exemple.invalid` (RFC 2606) ;
- numéros de téléphone dans la plage `06 39 98 xx xx`, réservée par l'ARCEP à
  la fiction ;
- aucune donnée sensible au sens de l'article 9 du RGPD.

Les textes de coaching (`coach/notes.jsonl`) décrivent des échanges commerciaux
inventés ; les noms de clients qui y figurent sont fictifs.
