---
title: "Miara — agents conversationnels pour les PME malgaches"
subtitle: "Soutenance de mémoire M2"
author: "Lucas Ralambo"
date: "2026"
lang: fr-FR
aspectratio: 169
theme: "default"
colortheme: "dove"
fonttheme: "professionalfonts"
mainfont: "DejaVu Serif"
sansfont: "DejaVu Sans"
monofont: "DejaVu Sans Mono"
---

# Le problème

Deux fonctions d'entreprise, un même goulot : la lecture de données déjà
structurées.

- **Commercial** : préparer un rendez-vous suppose de parcourir quatre écrans
  d'un CRM.
- **Ressources humaines** : présélectionner suppose de lire N CV contre une
  grille.

Contrainte de terrain (chapitre 3) : le prix n'est pas une variable
d'ajustement commerciale, c'est une contrainte de conception.

# Les quatre hypothèses

- **H1** — la présélection produit un classement qui s'accorde avec un
  annotateur humain, en un temps très inférieur à un examen manuel.
- **H2** — l'agent outillé réduit le temps de préparation d'un rendez-vous par
  rapport à une consultation directe du CRM.
- **H3** — une récupération structurée, sans index vectoriel, tient 3 s de
  latence au 95\textsuperscript{e} centile.
- **H4** — le coût unitaire des appels au modèle reste compatible avec le
  budget d'une PME malgache.

Ces énoncés ne sont pas reformulés dans la suite de l'exposé.

# Le système en une diapositive

Next.js → FastAPI (monolithe modulaire : `auth`, `hr`, `sales`, `core`) →
PostgreSQL, RabbitMQ, Redis, travailleurs Celery → passerelle LLM, API CRM.

Cinq contraintes non négociables :

1. isolation des locataires au niveau des lignes de la base ;
2. identité et identifiants issus du contexte de requête, jamais du modèle ;
3. deux files, toute tâche idempotente ;
4. aucun nom de modèle en dur, seulement des alias ;
5. invites versionnées dans le dépôt, version journalisée à chaque appel.

# Évaluer sans entreprise réelle

Pas de client, pas de recruteur, pas de base Salesforce de production.

Trois substituts, et ce qu'ils ne remplacent pas :

- **jeu doré synthétique** : 180 CV annotés, 30 questions, 10 comptes rendus,
  10 cas adverses, régénérable à l'identique, sans donnée personnelle ;
- **harnais automatisé** : rejoue le jeu contre le code de production ;
- **campagne de charge** : débit, latence et coût sous volume.

Le label de présélection est **calculé**, pas jugé : un profil est tiré, le CV
est assemblé à partir des briques de ces niveaux, la référence est produite par
les fonctions de production. Aucune dérive d'annotateur, référence
recalculable, mais **la référence n'est pas humaine** et la double annotation
de 10 % prévue n'a pas été faite.

Aucun des trois substituts ne remplace un utilisateur. Cette limite décide de
deux verdicts.

# Les seuils sont écrits avant la mesure

13 engagements de service, chacun avec sa justification rédigée dans
`evals/thresholds.yaml`.

> « Ces valeurs sont des engagements, pas des constats : la première mesure ne
> doit pas les fixer, sinon le harnais ne peut plus rien détecter. »

Conséquence : le harnais sort en erreur quand une barre est franchie, et il est
impossible d'ajuster la barre après coup.

# Résultat d'ensemble : 8 barres sur 13

Tenues : Spearman présélection, taux d'échec, Spearman coach, citations
inventées, consignes d'injection suivies, tentatives signalées, fichiers
corrompus, limite d'étapes.

**Non tenues** : exactitude des critères éliminatoires (0,7611 / 0,90), rappel
sur les outils (0,650 / 0,80), latence p95 (4,00 s / 3,00 s), faits de
référence énoncés (0,6818 / 0,80), preuves conformes du coach (0,40 / 0,90).

Robustesse, dans le détail : 5 tentatives d'injection sur 5 signalées et 0
suivie, 3 CV scannés sur 3 et 2 fichiers corrompus sur 2 traités proprement, 1
texte de coaching piégé sur 1. Valable pour **ces** cas, écrits pour ce
mémoire : aucune conclusion générale sur l'injection indirecte.

Source : `evals/reports/20260922T132654_e6ebfc6-sale.json`.

# H1 — le classement tient

| Offre | CV | Spearman | s/CV | USD/CV |
| --- | --- | --- | --- | --- |
| assistant-rh | 60 | 0,915 | 11,2 | 0,0121 |
| commercial-b2b | 60 | 0,906 | 11,6 | 0,0125 |
| developpeur-full-stack | 60 | 0,918 | 11,8 | 0,0120 |
| **ensemble** | **180** | **0,910** | **11,5** | **0,0122** |

180 CV en 360,5 s d'horloge, 0 échec.

Source : `evals/reports/20260922T132654_e6ebfc6-sale.md`.

# H1 — et pourtant le produit n'est pas utilisable

| Attendu / obtenu | excellent | bon | limite | hors profil |
| --- | --- | --- | --- | --- |
| excellent | 34 | 11 | 0 | 0 |
| bon | 1 | 43 | 1 | 0 |
| limite | 0 | 0 | **4** | **41** |
| hors profil | 0 | 0 | 2 | 43 |

41 faux négatifs contre 2 faux positifs, tous à la frontière du niveau 2 sur 5.

**Une corrélation de rang de 0,910 ne dit rien de la décision binaire prise en
amont du classement.**

# H2 — l'assistant commercial

| Mesure | Valeur |
| --- | --- |
| Tours aboutis / questions | 30 / 30 |
| Rappel sur les outils | 0,650 |
| Entités du CRM citées | 49 / 56 (87,5 %) |
| Faits de référence énoncés | 30 / 44 (68,2 %) |
| Absence de donnée bien annoncée | 3 / 3 |
| Écritures hors procédure | 0 |

Source : `evals/reports/20260922T132654_e6ebfc6-sale.md`.

# Outil composite contre outils atomiques

| Outil appelé | Questions | Rappel | Latence |
| --- | --- | --- | --- |
| `get_account_context` (composite) | 19 | 0,526 | 2,70 s |
| `find_contact` (atomique) | 6 | 0,917 | 1,96 s |
| `get_opportunity` (atomique) | 4 | 1,000 | 2,50 s |
| aucun outil | 1 | 0,000 | 1,58 s |

9 défauts sur 11 sont une substitution du composite aux atomiques ; 7 ne font
perdre aucune entité. Le défaut réel : le composite ignore les opportunités
closes.

Source : calculé depuis `suites.sales.detail` du rapport JSON.

# H3 — non tenue

| Grandeur | Mesure | Seuil |
| --- | --- | --- |
| médiane | 2,25 s | — |
| **95\textsuperscript{e} centile** | **4,00 s** | **≤ 3,00 s** |
| maximum | 4,5 s | — |

6 questions sur 30 dépassent 3 s. Deux appels au modèle par question, aucune
étape superflue.

Mesuré contre un double de test local : une instance Salesforce réelle
**dégraderait** ce chiffre.

# Où passe le temps d'un tour de conversation ?

| Série | Modèle | Outils | Reste |
| --- | --- | --- | --- |
| `sales-30` à vide | 2 674,5667 ms | 16,9667 ms | 33,5333 ms |
| `mixed` à vide | 2 637,3333 ms | 12,2667 ms | 31,2 ms |
| `mixed` sous charge | 2 367,3667 ms | 13,8667 ms | 34,7667 ms |

**Plus de 98 % du temps est chez le fournisseur de modèles.**

La récupération structurée ne coûte rien : la moitié de H3 est vérifiée, c'est
le seuil qui échoue. Paralléliser les outils ne rapporterait rien.

Source : `bench/reports/20260922-134336/campagne.json`.

# H4 — le coût est bas et surtout prévisible

| Offre | Appels | Jetons | USD | USD/CV |
| --- | --- | --- | --- | --- |
| assistant-rh | 120 | 312 118 | 0,726469 | 0,012108 |
| commercial-b2b | 120 | 314 434 | 0,752165 | 0,012536 |
| developpeur-full-stack | 121 | 312 242 | 0,720698 | 0,012012 |
| **ensemble** | **361** | **938 794** | **2,199332** | **0,012219** |

Moins de 5 % d'écart entre trois grilles différentes : une tarification au lot
est possible.

Source : `evals/reports/20260922T132654_e6ebfc6-sale.json`.

# Le coach : le bon et le mauvais chiffre

Corrélation sur la note globale : **0,985** sur 10 textes.

| Nature de la preuve | Nombre |
| --- | --- |
| Citation retrouvée dans le texte | 10 |
| Constat explicite d'une absence | 10 |
| Appréciation sans citation ni constat | **30** |
| **Citation introuvable dans le texte** | **0** |

Le seuil de sécurité tient parfaitement ; le seuil de forme est manqué de
moitié.

# Tenue en charge : le bon chiffre et le mauvais

| Lot | CV/min | USD/CV | Échecs | Mémoire |
| --- | --- | --- | --- | --- |
| hr-50@c2 | 9,83 | 0,0116 | 0 | 933,0 Mo |
| hr-50@c4 | 19,3233 | 0,0115 | 0 | 1 487,6 Mo |
| hr-50@c8 | 31,6533 | 0,0114 | 0 | 2 604,9 Mo |
| **hr-500@c8** | **30,3** | **0,0113** | **0** | 2 926,6 Mo |

Le débit double de c2 à c4 puis bute sur le limiteur (60 appels/min, 2 par CV).
Campagne **réduite** : 12 lots sur 39 points (plan complet 91,94 USD, plafond
18 USD) ; seuls les lots de 50 CV sont répétés.

| Sonde `core.ping` sur la file `light` | p95 | Sans réponse |
| --- | --- | --- |
| à vide | 0,07 s | 0 / 5 |
| **pendant un lot** | **25,37 s** | **2 / 5** |

Le critère écrit pour cela passe à 0,825, mais il chronomètre l'agent
commercial, qui répond dans FastAPI et **ne traverse jamais Celery** : il
aurait passé file totalement bloquée. Contraire à l'ADR-006, « un lot de 500 CV
ne doit jamais affamer une écriture CRM ».

Défaut de déploiement, pas de conception : les mêmes travailleurs consomment
`heavy` et `light`. Une propriété que rien ne mesure n'est pas une propriété,
c'est une intention.

# Trois métriques qui mentaient

- **Cas adverses** : comptait une imprécision de notation comme une défaillance
  de sécurité. Affichait 1 conforme sur 5 ; réel : 0 consigne suivie sur 5.
- **Preuves du coach** : comptait « inventé » un constat d'absence pourtant
  autorisé. Affichait 56 % ; le vrai défaut était ailleurs.
- **Rappel sur les outils** : pénalise un sur-ensemble d'appels sans perte
  d'information.

Un chiffre faux est bien formé, stable, et faux. Le seul garde-fou : inspecter
les cas derrière l'agrégat.

# Verdicts

- **H1 — non établie.** Référence calculée et non humaine, double annotation
  non faite, aucun examen manuel chronométré. Et 41 faux négatifs interdisent
  la mise en service.
- **H2 — non démontrée** : aucun des deux termes de la comparaison n'a été
  mesuré sur un humain.
- **H3 — infirmée** : 4,00 s au p95 contre 3,00 s. Mais la décomposition
  sépare les deux moitiés de l'énoncé : la récupération structurée tient
  (15 ms), c'est le seuil qui ne tient pas.
- **H4 — partiellement établie** : la mesure est faite et favorable, le
  jugement de compatibilité suppose un prix qui n'est pas fixé.

# Limites assumées

- Annotation calculée, unique, non relue par un humain.
- Données synthétiques et lisibles par construction : borne supérieure.
- Mesures conduites contre un double de test local, pas contre une instance
  Salesforce de production.
- Fournisseur de modèles unique (retombée d'alias, pas de clé pour le second).
- **Aucune mesure d'équité** en présélection : l'absence de mesure n'est pas
  une absence de risque.
- Une seule exécution du harnais, campagne de charge réduite : pas d'estimation
  de variance.

# Ce que le travail laisse

- Un système complet dont chaque décision d'architecture est consignée.
- Un **dispositif d'évaluation exécutable** : jeu doré régénérable, harnais qui
  échoue sous le seuil, barres écrites avant la mesure.
- Un corpus de **résultats négatifs documentés**, avec leur cause identifiée.
- Une feuille de route ordonnée par urgence : décalage de notation à la
  frontière des critères éliminatoires, puis travailleurs dédiés par file.

# Démonstration

Trois minutes, deux parcours :

1. une question au commercial → briefing avec sa trace d'outils → une écriture
   proposée puis **confirmée par l'humain** ;
2. dépôt de 20 CV sur une offre → progression → classement.

Déroulé reproductible : `thesis/soutenance/demo.md`, rejouable par script
Playwright. Répétitions datées et chronométrées : `thesis/soutenance/demo/`.

**Plan B** : parcours complet enregistré le 22 septembre 2026, durée relue sur
le fichier **134,72 s**. Si le réseau ou le fournisseur manque, la vidéo passe.
