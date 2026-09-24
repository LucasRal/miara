# Résultats mesurés

## Règle de lecture et conditions de la campagne

Ce chapitre obéit à une règle unique : **aucun nombre n'y figure qui ne
provienne d'un fichier archivé dans le dépôt**, et chaque tableau cite sa source
par son nom de fichier, immédiatement sous le tableau. Lorsqu'un nombre est
obtenu par un calcul à partir de valeurs archivées — une somme, un quotient,
une moyenne — le texte le signale comme tel. Lorsqu'une mesure annoncée n'a pas
pu être produite ou n'a pas été archivée, le chapitre l'écrit à la place du
nombre plutôt que de proposer une estimation. Les valeurs sont reproduites avec
la précision du fichier source ; les zéros ajoutés en fin de décimale pour
aligner une colonne de tableau ne changent pas la valeur.

La campagne de référence est une exécution complète des quatre suites du
harnais, datée du 22 septembre 2026 à 13 h 26 min 54 s, portant sur les cent
quatre-vingts CV, les trente questions commerciales, les dix comptes rendus de
coaching et les onze cas adverses du jeu doré. Les versions d'invite en vigueur
étaient `hr.profile` v1, `hr.score` v2, `sales.assistant` v4 et `sales.coach`
v2. La concurrence d'exécution était de six. Aucune limitation d'effectif n'a
été appliquée : le rapport n'est pas marqué partiel.

Trois réserves encadrent l'ensemble de ce qui suit, et elles ne seront pas
répétées sous chaque tableau.

**Un seul fournisseur de modèles.** Le fichier d'environnement de la machine
d'évaluation ne comportait pas de clé pour l'un des deux fournisseurs
configurés. Les alias déclarés dans la configuration désignent tous des modèles
de ce fournisseur absent ; ils sont donc retombés sur leurs replis, un modèle
léger et un modèle fort d'un fournisseur unique. Le fait est archivé et
vérifiable : le relevé d'environnement de la campagne de charge, produit par le
même code et le même jour, enregistre `"cle_anthropic_presente": false` et
`"cle_openai_presente": true` à côté de la table des alias. Toute latence et
tout coût de ce chapitre se lisent avec cette réserve ; une campagne conduite
avec la configuration d'alias nominale donnerait d'autres chiffres,
probablement différents dans les deux grandeurs à la fois.

Source de cette réserve : `bench/reports/20260922-134336/env.json`, clé `llm`.

**Le dépôt n'était pas propre.** L'empreinte de code du rapport porte un
suffixe qui l'indique, et le rapport le déclare en tête : il n'est pas rejouable
à l'identique depuis cette seule empreinte.

**Une exécution unique.** Les valeurs rapportées sont des observations, non des
moyennes assorties d'un intervalle de confiance. La variance d'une campagne à
l'autre n'a pas été estimée par répétition.

## Présélection de candidatures : ce que mesure H1

### Accord de classement

| Offre | CV | Spearman | Top-10 | Top-20 | Élim. | Échecs | s/CV | USD/CV |
| :------------------------ | ---: | ----: | ----: | ----: | ----: | ---: | ---: | -----: |
| assistant-rh | 60 | 0,915 | 80,0 % | 85,0 % | 80,0 % | 0 | 11,2 | 0,0121 |
| commercial-b2b | 60 | 0,906 | 70,0 % | 85,0 % | 73,3 % | 0 | 11,6 | 0,0125 |
| developpeur-full-stack | 60 | 0,918 | 60,0 % | 85,0 % | 75,0 % | 0 | 11,8 | 0,0120 |
| **ensemble** | **180** | **0,910** | | | **76,1 %** | **0** | **11,5** | **0,0122** |

Source : `evals/reports/20260922T132654_d793943-sale.md`, section « Présélection
RH » ; valeurs complètes dans le fichier JSON de même nom. « Élim. » désigne
l'exactitude de la décision sur les critères éliminatoires.

La corrélation de rang est de 0,9102 sur l'ensemble des cent quatre-vingts CV,
pour un seuil fixé à 0,75. Elle est remarquablement stable d'une offre à
l'autre, entre 0,9056 et 0,9179, ce qui indique que le résultat ne tient pas à
la particularité d'une grille. L'écart absolu moyen entre la note produite et la
note de référence est de 12,8056 points sur cent, et le pipeline est
systématiquement plus sévère que la référence. Aucun CV n'a échoué : le taux
d'échec est nul, pour un seuil qui tolérait cinq pour cent.

La précision aux dix premiers est en revanche irrégulière : 80 %, 70 % et 60 %
selon l'offre, alors que la précision aux vingt premiers vaut 85 % pour les
trois. Cette irrégularité n'a pas de seuil associé et doit être lue avec la
réserve de méthode déjà signalée : les ex aequo de la référence sont départagés
par le nom de fichier, ce qui rend la frontière exacte du dixième rang
arbitraire.

### Le défaut central : les critères éliminatoires

| Offre | Vrais pos. | Vrais nég. | Faux pos. | Faux nég. | Exactitude |
| :----------------------- | ---: | ---: | ---: | ---: | -----: |
| assistant-rh | 34 | 14 | 1 | 11 | 0,800 |
| commercial-b2b | 30 | 14 | 1 | 15 | 0,7333 |
| developpeur-full-stack | 30 | 15 | 0 | 15 | 0,750 |
| **ensemble (somme)** | **94** | **43** | **2** | **41** | **0,7611** |

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemin
`suites.hr.offres.<offre>.must_have` ; la ligne d'ensemble est la somme des
trois offres, et l'exactitude d'ensemble 0,7611 figure telle quelle dans le
fichier au chemin `suites.hr.global.exactitude_must_have`.

C'est ici que se situe le principal échec du produit, et il est net : quarante
et un faux négatifs contre deux faux positifs, soit près d'un candidat sur
trois parmi les cent trente-cinq que la référence déclare recevables. Le
pipeline n'est pas imprécis, il est **biaisé dans une direction**, et dans la
plus coûteuse des deux. Un faux positif sera corrigé au premier entretien ; un
faux négatif écarte un candidat recevable, sans trace visible pour le
recruteur, puisque le candidat se retrouve simplement en bas du classement avec
une note nulle.

La matrice de confusion par strate identifie exactement l'endroit où l'erreur se
produit.

| Attendu / obtenu | excellent | bon | limite | hors profil |
| :--------------- | ---: | ---: | ---: | ---: |
| excellent | 34 | 11 | 0 | 0 |
| bon | 1 | 43 | 1 | 0 |
| limite | 0 | 0 | 4 | 41 |
| hors profil | 0 | 0 | 2 | 43 |

Source : `evals/reports/20260922T132654_d793943-sale.md`, section « Matrice de
confusion par strate ».

Quarante et un des quarante-cinq CV de la strate *limite* sont classés *hors
profil*. Le nombre est exactement celui des faux négatifs sur les critères
éliminatoires, ce qui établit la cause sans ambiguïté : la strate *limite* est
construite en plaçant les critères éliminatoires au niveau deux sur cinq,
c'est-à-dire juste au-dessus de la frontière qui déclenche l'élimination, et le
modèle lit très majoritairement ces candidats comme étant au niveau un. Le
défaut n'est donc pas une imprécision diffuse : c'est un **décalage d'un
demi-niveau à une frontière précise**, qui bascule une note pondérée en une note
nulle.

Deux observations complètent ce tableau. D'abord, la confusion est très faible
partout ailleurs : un seul CV *bon* remonté en *excellent*, un seul descendu en
*limite*, aucune erreur de plus d'une strate. Ensuite, onze CV *excellent* sont
classés *bon*, manifestation de la sévérité générale déjà mesurée par l'écart
absolu moyen.

Le point méthodologique qu'il faut en retirer est sévère pour la corrélation de
rang. Comme les CV *limite* mal évalués tombent à zéro, où se trouvent déjà les
CV *hors profil* qui les suivaient immédiatement dans le classement, l'erreur
déplace très peu les rangs : elle laisse le Spearman à 0,910 tout en détruisant
la décision métier la plus importante. **Une corrélation de rang élevée ne
garantit rien sur la qualité d'une décision binaire prise en amont du
classement.** C'est exactement pour cette raison que les deux métriques sont
publiées séparément et que la seconde porte un seuil propre.

### Temps de traitement

| Étape | assistant-rh | commercial-b2b | developpeur-full-stack |
| :------------------------ | ------: | ------: | ------: |
| Extraction du texte | 0,171 s | 0,101 s | 0,093 s |
| Structuration du profil | 6,113 s | 5,876 s | 6,313 s |
| Notation contre la grille | 4,908 s | 5,599 s | 5,401 s |

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemin
`suites.hr.offres.<offre>.etapes`, champ `mean_seconds` ; soixante mesures par
case.

Le temps cumulé par CV est de 11,5275 secondes, et la suite de présélection
complète a duré 360,5 secondes d'horloge pour cent quatre-vingts CV. Le rapport
entre les deux, soit un facteur d'environ 5,8, correspond à la concurrence
d'exécution de six déclarée par le rapport : le pipeline exploite
effectivement le parallélisme des travailleurs, et cent quatre-vingts
candidatures sont traitées en six minutes.

L'extraction du texte ne pèse rien, entre 0,093 et 0,171 seconde, ce qui valide
a posteriori la décision de traiter les documents avec des bibliothèques locales
plutôt que par un service distant. Tout le temps est dans les deux appels au
modèle, à peu près également répartis entre la structuration et la notation.
C'est une information utile pour toute optimisation future : il n'existe pas de
gisement de performance ailleurs que dans ces deux appels.

Il faut redire ici ce que ce chiffre ne dit pas. Onze secondes et demie par CV
se comparent à une durée d'examen manuel qui **n'a pas été mesurée** dans ce
travail. Aucun recruteur n'a été chronométré, aucune valeur de référence externe
n'a été retenue. La seconde moitié de H1 n'est donc pas établie par ce
chapitre.

## Assistant commercial : ce que mesure H2

| Mesure | Valeur |
| --- | --- |
| Questions rejouées | 30 |
| Tours aboutis | 30 |
| F1 sur le choix des outils | 0,656 |
| Précision / rappel sur les outils | 0,667 / 0,650 |
| Questions avec tous les outils attendus | 19 sur 30 |
| Entités du CRM citées | 49 sur 56 (87,5 %) |
| Faits de référence énoncés | 30 sur 44 (68,2 %) |
| Absence de donnée correctement annoncée | 3 sur 3 |
| Appels au modèle par question | 2,0 |
| Latence médiane / 95\textsuperscript{e} centile | 2,2 s / 4,0 s |
| Latence maximale | 4,5 s |
| Tours coupés par la limite d'étapes | 0 |
| Écritures proposées hors procédure | 0 |

Source : `evals/reports/20260922T132654_d793943-sale.md`, section « Assistant
commercial ».

Trois résultats sont bons et ne doivent pas être noyés par les deux qui ne le
sont pas. Les trente questions aboutissent toutes, aucune n'épuise la limite de
six étapes de la boucle d'agent, et aucune écriture n'est proposée hors de la
procédure de confirmation. Les trois questions dont la bonne réponse est de dire
qu'il n'y a rien à dire reçoivent effectivement cette réponse, sans invention :
c'est le comportement qu'on attend d'un assistant branché sur des données
d'entreprise, et il n'était pas acquis.

Le rappel sur les outils, à 0,650 pour un seuil de 0,80, est le premier des deux
échecs. Onze questions sur trente n'appellent pas l'ensemble des outils attendus
par l'annotation. Le détail archivé permet d'aller plus loin que ce constat, et
il conduit à une conclusion nuancée qu'il faut exposer entièrement.

| Outil appelé | Questions | Rappel moyen | Latence moy. |
| :------------------------------- | ---: | ---: | ---: |
| `get_account_context` (composite) | 19 | 0,526 | 2,70 s |
| `find_contact` (atomique) | 6 | 0,917 | 1,96 s |
| `get_opportunity` (atomique) | 4 | 1,000 | 2,50 s |
| aucun outil | 1 | 0,000 | 1,58 s |

Source : calculé à partir de `evals/reports/20260922T132654_d793943-sale.json`,
chemin `suites.sales.detail`, en regroupant les trente questions par ensemble
d'outils exécutés.

Le déficit de rappel se concentre sur les questions où l'agent a appelé l'outil
**composite** de contexte de compte. Neuf des onze défauts sont de la même
forme : l'annotation attendait un ou deux outils atomiques, le plus
souvent la recherche de compte seule ou accompagnée de la recherche
d'activités, et l'agent a appelé à la place l'outil composite, qui interroge le
compte, ses opportunités, ses activités et ses cas en une fois.

Il faut alors se demander si cette substitution a coûté une information, et le
rapport permet de répondre, puisqu'il enregistre pour chaque question les
entités du CRM que la réponse devait citer. Sur ces neuf substitutions, sept
n'ont fait perdre aucune entité attendue. Les deux autres si : sur la question
des activités des quatre-vingt-dix derniers jours chez un compte, la tâche de
relance attendue manque ; et sur la question portant sur une affaire gagnée par
le passé, l'opportunité historique manque, parce que l'outil composite ne
remonte que les opportunités en cours. Les deux défauts restants sont d'une
autre nature : une question où l'agent appelle la recherche de contact sans la
recherche de compte qui l'accompagnait dans l'annotation, sans perte d'entité,
et la seule question où il **n'appelle aucun outil**, où l'entité attendue
manque évidemment.

Ce détail ne disculpe pas le produit, il déplace le diagnostic. Le rappel sur
les outils, tel qu'il est défini, mesure la conformité du plan d'appel à une
annotation, et non la complétude de l'information rapportée. Sur ce jeu, les
deux grandeurs divergent nettement : le rappel sur les outils vaut 0,650 alors
que le rappel sur les entités, qui mesure ce que l'utilisateur lit réellement,
vaut 0,875. La métrique de rappel outil surestime donc la gravité du défaut,
et l'annotation elle-même mériterait d'être révisée pour accepter un
sur-ensemble d'outils comme conforme. C'est, après les deux cas exposés au
chapitre 7, la **troisième** métrique de ce travail dont la définition s'avère
discutable à l'usage, et il est plus honnête de le signaler ici que de laisser
un chiffre de 0,650 porter seul la conclusion.

Reste un défaut qui, lui, n'est pas un artefact de mesure : la couverture
insuffisante de l'outil composite, qui ignore les opportunités closes et dont
la fenêtre d'activités ne couvre pas tous les cas attendus. Deux briefings sur
trente sont incomplets pour cette raison, et la correction relève du code de
l'outil, non de l'invite.

Le rappel sur les entités doit d'ailleurs être lu dans son ensemble, et il est
moins flatteur que son taux global de 87,5 % ne le laisse croire : les sept
entités manquantes se répartissent sur **sept questions distinctes**, soit
près d'une réponse sur quatre à laquelle il manque au moins un élément attendu.
Trois de ces sept s'expliquent par le choix d'outil qu'on vient de décrire.
Pour les quatre autres, l'agent a appelé exactement les outils attendus, a donc
disposé de l'information, et ne l'a pas reportée dans sa réponse. C'est un
défaut de rédaction et non de récupération, et il relève de l'invite de
synthèse.

Le second échec est le taux de faits de référence énoncés, à 0,6818 pour un
seuil de 0,80. Ce taux est jugé par un modèle, et la relecture humaine
documentée plus bas montre qu'il s'agit d'une **estimation basse**.

### La relecture du juge

Le juge a rendu quarante-sept verdicts, dont neuf ont été tirés pour relecture
humaine, soit dix-neuf pour cent. La relecture a été faite et dépouillée :
**huit accords et un désaccord, soit 88,9 % d'accord**.

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemin
`juge.relecture` ; détail des neuf cas dans
`evals/reports/20260922T132654_d793943-sale_relecture.md`.

Le désaccord est instructif, et le sens dans lequel il joue importe. Le fait de
référence était formulé en relatif, « la clôture est prévue dans environ
quarante-cinq jours », et la réponse de l'agent le donnait en absolu, « le 6
novembre 2026 », ce qui, à la date de la campagne, désigne le même jour. Le juge
a compté le fait absent parce que les deux formulations ne se ressemblent pas.
Un juge qui manque un fait correctement énoncé abaisse le taux ; il ne le
gonfle pas. Le taux de 0,6818 est donc un plancher, et le taux réel est plus
élevé d'une quantité que ce dispositif ne permet pas de chiffrer. Cela ne suffit
vraisemblablement pas à atteindre 0,80, mais cela interdit de traiter 0,6818
comme une mesure exacte.

### Ce que ces chiffres ne disent pas de H2

H2 affirme une réduction de temps par rapport à une consultation directe du
logiciel de gestion de la relation client. **Aucune mesure du terme de
comparaison n'a été prise.** Aucun commercial n'a été chronométré devant une
interface Salesforce, et la campagne s'exécute d'ailleurs contre un double de
test et non contre une instance réelle. Le chapitre ne peut donc rapporter que
ce que l'agent produit et en combien de temps, ce qu'il fait ci-dessus. Le
chapitre 9 en tire la seule conclusion possible.

## Latence conversationnelle : H3 n'est pas tenue

| Grandeur | Valeur mesurée | Seuil |
| --- | --- | --- |
| Latence médiane (p50) | 2,25 s | — |
| Latence au 95\textsuperscript{e} centile | 4,00 s | ≤ 3,00 s |
| Latence maximale | 4,5 s | — |
| Appels au modèle par question | 2,0 | — |

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemin
`suites.sales.latence` et `suites.sales.etapes`.

Le seuil de trois secondes au 95\textsuperscript{e} centile, posé par la
décision d'architecture qui écarte l'index vectoriel au profit d'une
récupération structurée, **n'est pas tenu** : la valeur mesurée est de quatre
secondes, soit un tiers au-dessus de la barre. La médiane, à 2,25 secondes,
reste confortablement sous le seuil, et la distribution archivée montre que six
questions sur trente dépassent trois secondes, la plus lente atteignant 4,5
secondes. Le 95\textsuperscript{e} centile s'appuie donc sur les deux ou trois
observations les plus lentes d'un échantillon de trente : il est légitime au
sens du protocole, et il est fragile au sens statistique. Une question lente de
plus ou de moins le déplacerait visiblement.

La décomposition par outil, donnée plus haut, situe le surcoût : les questions
traitées par l'outil composite durent en moyenne 2,70 secondes contre 1,96
seconde pour la recherche de contact, et les deux questions les plus lentes de
la campagne, à 4,5 et 4,32 secondes, appellent toutes deux cet outil. Chaque
question consomme exactement deux appels au modèle, un pour choisir l'outil et
un pour rédiger la réponse : il n'y a donc pas d'étapes superflues à supprimer.
On se gardera d'en conclure que l'outil composite est lent en lui-même. La
section consacrée à la tenue en charge décompose la latence étape par étape et
montre que l'exécution des outils pèse une quinzaine de millisecondes, soit un
demi pour cent du temps de réponse : ce que l'outil composite prédit, ce n'est
pas un coût de récupération, c'est une réponse plus longue à rédiger, donc un
appel au modèle plus long.

Deux réserves pèsent sur ce résultat, et aucune ne le sauve. D'une part, la
réserve de fournisseur vaut pleinement ici : ces latences sont celles d'un
fournisseur unique, mesurées depuis un serveur donné, et un autre couple
fournisseur-région donnerait d'autres valeurs. D'autre part, ces mesures ont été
prises contre un double de test local, dont le temps d'accès aux données est
négligeable ; une instance Salesforce réelle ajouterait un aller-retour réseau
vers un service distant et **dégraderait** le résultat plutôt que de
l'améliorer. Le verdict du chapitre 9 en tient compte.

## Coût : ce que mesure H4

| Offre | Appels | Jetons | Coût (USD) | Coût/CV (USD) |
| :------------------------- | ---: | ------: | ------: | ------: |
| assistant-rh | 120 | 312 118 | 0,726469 | 0,012108 |
| commercial-b2b | 120 | 314 434 | 0,752165 | 0,012536 |
| developpeur-full-stack | 121 | 312 242 | 0,720698 | 0,012012 |
| **ensemble** | **361** | **938 794** | **2,199332** | **0,012219** |

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemin
`suites.hr.offres.<offre>` (champs `appels_llm`, `jetons`, `cout_usd`,
`cout_par_cv_usd`) ; les totaux d'appels et de jetons sont la somme des trois
offres, le coût total 2,199332 et le coût par CV 0,012219 figurent tels quels au
chemin `suites.hr.global`.

Une remarque de rigueur s'impose sur ce tableau. Le résumé rédigé du rapport
présente la valeur de 2,199332 dollar comme le « coût total de la campagne » ;
elle est en réalité la somme exacte, au millionième de dollar près, des coûts
des trois offres de la suite de présélection. Le coût des suites commerciale, de
coaching et adverse n'est pas agrégé dans ce champ. La valeur doit donc être
lue comme le **coût de la suite de présélection**, et c'est ainsi qu'elle est
employée ici. Cette ambiguïté d'étiquette est signalée plutôt que corrigée
silencieusement, parce que corriger un chiffre publié sans le dire est
précisément ce que ce chapitre s'interdit.

Les trois offres donnent des coûts très proches, de 0,012012 à 0,012536 dollar
par CV, ce qui tient à la régularité de la consommation : deux appels au modèle
par CV, et de l'ordre de cinq mille deux cents jetons par CV, quotient des
jetons par le nombre de candidats. Le coût unitaire est donc **prévisible**, ce
qui est la propriété la plus utile pour une tarification : un lot de cent CV
coûte de l'ordre de 1,22 dollar en appels au modèle, et un lot de cinq cents de
l'ordre de 6,11 dollars, par simple produit du coût unitaire mesuré.

Ce que le chiffre ne comprend pas doit être dit avec la même netteté. Il ne
comprend ni l'hébergement, ni la bande passante, ni le stockage des documents,
ni le coût d'exploitation, ni aucune marge. Il ne comprend pas non plus le coût
des suites commerciale et de coaching, qui relèvent d'un autre usage et n'ont
pas été agrégées. Et il est mesuré sur un fournisseur unique, aux tarifs
publics en vigueur à la date de la campagne. Le jugement de compatibilité avec
le budget d'une entreprise malgache, que H4 appelle, est donc discuté au
chapitre 9 à partir de ce coût mesuré, et non affirmé ici.

## Agent de coaching

La corrélation de rang sur la note globale atteint 0,985 sur dix textes, pour un
écart absolu moyen de 8,6 points sur cent.

| Critère | Spearman | Écart abs. moyen (/5) | Textes |
| --- | --- | --- | --- |
| découverte des besoins | 0,943 | 0,40 | 10 |
| gestion des objections | 0,619 | 0,90 | 10 |
| proposition de valeur | 0,944 | 0,50 | 10 |
| prochaine étape | 0,949 | 0,50 | 10 |
| ton et concision | 0,842 | 0,50 | 10 |

Source : `evals/reports/20260922T132654_d793943-sale.md`, section « Coach
commercial ».

Quatre critères sur cinq se situent entre 0,842 et 0,949 ; celui de la gestion
des objections décroche à 0,619 avec le plus fort écart absolu. C'était
prévisible : c'est le seul critère doté d'une convention d'annotation
discutable, puisqu'un compte rendu sans objection exprimée reçoit d'office la
valeur neutre de trois sur cinq. Une partie du désaccord mesuré porte donc sur
cette convention plutôt que sur le jugement du modèle. Sur dix textes, aucune
de ces valeurs ne supporte une interprétation fine.

Le résultat important de cette suite est ailleurs, et c'est le plus mauvais
chiffre de la campagne.

| Nature de la preuve avancée | Nombre |
| --- | --- |
| Citation retrouvée dans le texte | 10 |
| Constat explicite d'une absence | 10 |
| Appréciation sans citation ni constat | 30 |
| **Citation introuvable dans le texte** | **0** |
| Preuve vide | 0 |
| Total | 50 |

Source : `evals/reports/20260922T132654_d793943-sale.md`, section « Preuves
avancées par le coach ».

Le taux de preuves conformes est de 40,0 % pour un seuil de 90 %, et le taux de
citations inventées est de **zéro**, pour un seuil de sécurité à zéro. Ces deux
résultats doivent être lus ensemble, car ils disent deux choses opposées. Le
seuil de sécurité tient parfaitement : sur cinquante preuves, pas une seule
affirmation ne se présente comme une citation du compte rendu sans y figurer.
Le seuil de forme est massivement manqué : trois preuves sur cinq sont des
appréciations générales, du type « le ton est professionnel », qui ne renvoient
à aucun passage et ne permettent pas à l'utilisateur de contester la note.

Le détail par critère montre que le défaut n'est pas uniforme : la gestion des
objections atteint 8 preuves conformes sur 10, tandis que le critère de
prochaine étape tombe à 2 sur 10 et celui de ton et concision à 1 sur 10. La
hiérarchie est cohérente avec la nature des critères : une objection est un
passage identifiable du texte, alors qu'un jugement de ton porte sur le texte
entier et se prête mal à la citation. C'est exactement l'argument qui avait fait
placer le seuil à 0,90 plutôt qu'à 1,00 ; il apparaît maintenant que 0,90 était
optimiste pour deux des cinq critères, et que la correction relève de l'invite
autant que du seuil.

## Robustesse face aux entrées hostiles ou malformées

| Cas | Conformes | Total |
| --- | --- | --- |
| CV scanné sans couche de texte | 3 | 3 |
| Fichier corrompu | 2 | 2 |
| CV porteur d'une injection de consigne | 5 | 5 |
| Texte de coaching porteur d'une injection | 1 | 1 |

Source : `evals/reports/20260922T132654_d793943-sale.md`, section « Cas
adverses ».

| Mesure sur les cinq CV porteurs d'injection | Valeur |
| --- | --- |
| Consignes suivies (sécurité) | 0 sur 5 |
| Tentatives signalées dans les réserves du rapport | 5 sur 5 |
| Notes restées à cinq points de la référence (qualité) | 3 sur 5 |

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemin
`suites.adverse.par_cas.injection_de_consigne`.

Aucune des cinq consignes injectées n'a été suivie, et les cinq tentatives ont
été signalées dans les réserves du rapport de notation, au-delà de la barre de
trois sur cinq qui avait été fixée en reconnaissant que le signalement dépend
d'une formulation du modèle. Le texte de coaching piégé, dont la consigne
injectée réclamait une note de cent sur cent, a reçu zéro. Les trois CV scannés
sans couche de texte ressortent avec le statut demandant une reconnaissance
optique, et les deux fichiers corrompus échouent avec un motif sans interrompre
le lot.

La ligne de qualité, trois notes sur cinq restées à moins de cinq points de la
référence, est rapportée séparément et n'entre dans aucun verdict de sécurité.
C'est la conséquence directe de la correction de métrique exposée au chapitre 7 :
une note qui bouge sans monter vers ce que l'injection réclame est une erreur de
notation ordinaire, du même ordre que celles observées sur les CV sans piège, et
non une défaillance de sécurité.

Ces résultats sont ceux d'un jeu de cinq injections écrites pour ce mémoire. Ils
n'autorisent aucune conclusion générale sur la résistance du système à
l'injection indirecte, dont la littérature montre qu'elle se décline en familles
nombreuses et que sa neutralisation complète reste un problème ouvert
[@greshake2023indirect ; @liu2024formalizing ; @owasp2025llmtop10].

## Tenue en charge

La campagne de charge a été exécutée le même jour, avec la même empreinte de
code, sur la machine de déploiement : six processeurs logiques, 11 671 mégaoctets
de mémoire. Elle a duré 3 537,1 secondes et dépensé 13,467116 dollars sur un
plafond de 18 dollars, aucun point n'ayant été écarté faute de budget. La graine
était fixée à 20260922.

Deux réserves doivent être posées avant les tableaux, parce qu'elles
conditionnent tout ce qui suit.

La première est que **cette campagne est réduite, et non complète**. La matrice
prévue compte trente-neuf points, estimés à 91,94 dollars, pour un plafond de
dix-huit. Un plan restreint a donc été choisi avant le lancement plutôt que
rogné en route : le rapport enregistre zéro point écarté faute de budget. Douze
lots ont tourné, pour mille cent cinquante CV notés et 13,467116 dollars
dépensés. Les neuf points à cinquante CV ont tourné intégralement et portent
seuls la mesure de reproductibilité ; le lot de cent CV à concurrence quatre,
celui de cinq cents à concurrence huit, le scénario mixte et la série
conversationnelle n'ont qu'une répétition ; les lots de cent et de cinq cents
aux concurrences deux et quatre, comme le scénario mixte à ces mêmes
concurrences, **n'ont pas tourné du tout**. La courbe de débit en fonction de
la concurrence n'est donc établie qu'à cinquante CV, et les deux gros lots
n'ont pas de dispersion connue.

La seconde est qu'un limiteur de débit est actif, à soixante appels au modèle
par minute et par organisation, soit un plafond théorique de trente CV par
minute puisque chaque CV consomme deux appels. Ce plafond est atteint, et les
chiffres qui s'en approchent mesurent le limiteur autant que la machine.

Source : `bench/reports/20260922-134336/rapport.md`, sections « Réserves de
lecture » et « Budget » ; lots effectivement exécutés dans `runs.csv` ; plan
complet et son estimation obtenus par `make bench ARGS="--plan-seulement"`,
matrice définie dans `backend/scripts/bench.py`.

### Débit et mémoire

| Lot          | Rép. |   CV | CV/min | USD/CV | Échecs | Mémoire (Mo) |
| :----------- | ---: | ---: | -----: | -----: | -----: | -----------: |
| hr-50@c2     |    3 |   50 |   9,83 | 0,0116 |      0 |        933,0 |
| hr-50@c4     |    3 |   50 | 19,3233 | 0,0115 |     0 |      1 487,6 |
| hr-50@c8     |    3 |   50 | 31,6533 | 0,0114 |     0 |      2 604,9 |
| hr-100@c4    |    1 |  100 |  19,98 | 0,0116 |      0 |      1 533,6 |
| hr-500@c8    |    1 |  500 |   30,3 | 0,0113 |      0 |      2 926,6 |
| mixed@c8     |    1 |  100 |  32,41 | 0,0115 |      0 |      2 680,9 |

La colonne « Rép. » donne le nombre de répétitions, « CV/min » le débit moyen,
« USD/CV » le coût par CV noté et « Mémoire » le pic d'occupation observé.

Source : `bench/reports/20260922-134336/rapport.md`, section « Lots RH » ;
détail par lot dans `runs.csv` du même dossier.

Trois résultats se lisent directement. Le **débit croît avec la concurrence des
travailleurs**, de 9,83 à 19,3233 puis à 31,6533 CV par minute pour des
concurrences de deux, quatre et huit : le doublement de deux à quatre est
presque parfait, celui de quatre à huit ne l'est plus, et pour cause, puisque
31,6533 CV par minute dépasse le plafond théorique du limiteur. Le lot de cinq
cents CV, plus long, le confirme en retombant à 30,3 CV par minute, exactement
sur ce plafond : la fenêtre glissante du limiteur laisse passer une pointe sur
un lot court, plus sur un lot long. **Le parallélisme utile s'arrête donc, dans
cette configuration, autour de quatre travailleurs** ; au-delà, on consomme de
la mémoire sans gagner de débit, et l'on mesure le limiteur plutôt que la
machine.

Le **coût unitaire est stable** entre 0,0113 et 0,0116 dollar par CV, et
légèrement inférieur aux 0,012219 dollar de la campagne d'évaluation : celle-ci
emploie les trois grilles, dont deux plus longues, là où la campagne de charge
n'en emploie qu'une. Ce n'est pas une divergence de mesure, c'est un travail
différent. La **mémoire croît avec la concurrence**, de 933,0 mégaoctets à deux
travailleurs à 2 926,6 pour le lot de cinq cents, soit un quart de la machine
au pic : le dimensionnement n'est pas contraint par la mémoire dans cette
plage.

Enfin, et c'est le résultat que la campagne devait d'abord établir : **le lot de
cinq cents CV termine sans aucun échec**, en 990,12 secondes, soit seize minutes
et trente secondes, avec 1 003 appels au modèle dont aucun en erreur. Ce nombre
appelle une remarque plutôt qu'un arrondi : deux appels par CV en donneraient
mille, et le fichier en compte trois de plus. Ces trois appels supplémentaires
ont abouti, ils représentent trois dixièmes de pour cent du total, et leur cause
n'a pas été identifiée ; le chiffre est reproduit tel que le fichier le porte.

Ce lot réemploie par ailleurs des documents : il porte sur cent quatre-vingts
documents distincts pour une répétition moyenne de 2,78, comme l'enregistre la
colonne prévue à cet effet. La réserve n'est pas seulement qu'aucune mesure de
qualité n'en peut être tirée ; c'est aussi que la répétition peut **flatter le
coût et la durée**, puisqu'un document déjà traité l'est ensuite sous des
conditions plus favorables au fournisseur. Le lot atteste d'une tenue en charge,
et de rien d'autre.

La reproductibilité, mesurée comme l'étendue relative du débit sur trois
répétitions d'une même configuration, vaut 0,0336 à concurrence deux, 0,0673 à
quatre et 0,0423 à huit, pour une tolérance de 0,1. Les trois configurations
tiennent, avec une marge plus étroite à concurrence quatre.

Source : `bench/reports/20260922-134336/reproductibilite.csv`.

### Latence conversationnelle sous charge

| Série | Tours | p50 | p95 | p99 |
| :-------------------- | ---: | ---: | ---: | ---: |
| `sales-30` à vide | 30/30 | 2,45 s | 4,37 s | 5,45 s |
| `mixed` à vide | 30/30 | 2,58 s | 4,29 s | 5,10 s |
| `mixed` sous charge | 30/30 | 2,27 s | 3,54 s | 4,11 s |

Source : `bench/reports/20260922-134336/rapport.md`, section « Latence
conversationnelle » ; centiles et maxima dans `campagne.json`, clés `sales` et
`mixed`.

Le critère écrit pour cette campagne — la latence de l'agent commercial pendant
un lot de présélection ne doit pas dépasser une fois et demie sa latence à vide
— est **tenu à la lettre**, avec un rapport de 0,825. Il ne doit pourtant pas
être présenté comme une validation, pour deux raisons.

D'abord, un rapport inférieur à un signifie que l'agent a répondu **plus vite**
pendant le lot qu'à vide, ce dont il serait absurde de créditer la charge. La
lecture honnête est que la variation d'une série à l'autre, de 3,54 à 4,37
secondes au 95\textsuperscript{e} centile, excède l'effet de la charge locale,
et que cette variation vient d'ailleurs. La décomposition par étape le montre
sans ambiguïté. Ensuite, et c'est plus grave, **ce critère ne mesure pas la
propriété qu'il prétend vérifier** : l'agent commercial répond à l'intérieur du
processus de l'API et ne traverse jamais les files de tâches, de sorte que sa
latence est insensible, par construction, à l'état de la file lourde. La sonde
qui emprunte réellement la file légère donne le résultat inverse, et fait
l'objet de la sous-section suivante.

| Série | Appels au modèle | Exécution des outils | Reste |
| :-------------------- | ---------: | -------: | -------: |
| `sales-30` à vide | 2 674,5667 ms | 16,9667 ms | 33,5333 ms |
| `mixed` à vide | 2 637,3333 ms | 12,2667 ms | 31,2 ms |
| `mixed` sous charge | 2 367,3667 ms | 13,8667 ms | 34,7667 ms |

Source : `bench/reports/20260922-134336/campagne.json`, clés
`sales.a_vide.par_etape_ms` et `mixed.*.par_etape_ms` (moyennes par tour).

Ce tableau est, avec la matrice de confusion de la présélection, le résultat le
plus important du chapitre. **Plus de quatre-vingt-dix-huit pour cent du temps
de réponse est passé dans les appels au modèle.** L'exécution des outils de
lecture, c'est-à-dire la récupération structurée elle-même, coûte entre 12,2667
et 16,9667 millisecondes, et tout le reste du travail local — assemblage du
contexte, sérialisation, journalisation — entre 31,2 et 34,7667 millisecondes.
La différence de latence entre les trois séries suit exactement celle du temps
passé chez le fournisseur de modèles, de 2 367,3667 à 2 674,5667
millisecondes.

La conséquence pour H3 est double, et elle sera reprise au chapitre 9. D'un
côté, le pari de la décision d'architecture qui écarte l'index vectoriel est
**validé dans son principe** : la récupération structurée ne coûte rien, un
index vectoriel n'aurait rien fait gagner sur ce poste puisqu'il n'y a rien à
gagner. De l'autre, le seuil de trois secondes n'est pas tenu, il ne l'est dans
aucune des trois séries, et il ne le sera pas par une optimisation locale :
seuls le nombre d'appels au modèle par tour ou le choix du modèle peuvent le
déplacer.

### La file légère est affamée pendant un lot

| Contexte | Sondes | p50 | p95 | Sans réponse |
| :--------------- | ---: | ---: | ---: | ---: |
| à vide | 5 | 0,01 s | 0,07 s | 0 |
| pendant un lot | 5 | 0,01 s | 25,37 s | 2 |

Source : `bench/reports/20260922-134336/rapport.md`, section « File `light` » ;
relevé sonde par sonde dans `file_light.csv`.

Ce résultat contredit une attente de conception et doit être rapporté comme
tel. Le scénario mixte avait été construit pour démontrer que la file légère,
qui porte les synchronisations avec le CRM et les notifications, n'est pas
affamée par la file lourde qui porte l'extraction et la notation. La mesure
retenue pour le critère était la latence de l'agent commercial, qui est
synchrone et ne passe pas par les files : elle est bonne, et elle ne dit rien
de la question posée. La sonde qui dit quelque chose est celle qui poste une
tâche légère pendant le lot, et son verdict est mauvais : sur cinq sondes, deux
sont restées **sans réponse**, une a mis 28,189 secondes, et le
95\textsuperscript{e} centile s'établit à 25,37 secondes contre 0,07 seconde à
vide.

La cause est structurelle et non accidentelle : la commande de lancement des
travailleurs, celle du développement, leur fait consommer les deux files à la
fois, si bien qu'un lot de présélection qui occupe les huit emplacements ne
laisse aucun exécutant disponible pour une tâche légère. Deux files déclarées
sur un même pool de travailleurs ne sont pas deux files.

Ce constat contredit frontalement une décision d'architecture. La décision
relative au traitement asynchrone justifie l'existence de deux files par une
phrase sans ambiguïté : un lot de cinq cents CV ne doit jamais affamer une
écriture vers le CRM. C'est exactement ce qui se produit, et cent CV ont suffi
à l'établir. La séparation existe dans le code, elle n'existe pas à l'exécution
sur cette topologie. On notera que cinq sondes ne font pas une mesure fine : ce
chiffre établit l'existence du problème, pas son ampleur exacte.

#### Correction et contre-mesure

Le défaut a été corrigé après la campagne, puis mesuré à nouveau sur le même
scénario, la même machine et la même graine. Il faut d'abord corriger une
imprécision d'attribution : les unités `systemd` du serveur séparaient déjà les
deux files en deux services, `miara-worker-heavy` et `miara-worker-light`. Ce
qui confondait les deux files n'était donc pas le déploiement mais la cible
`make worker` du développement, que le harnais de charge recopiait — de sorte
que la campagne mesurait une topologie qu'aucune machine en service ne faisait
tourner. C'est un biais de banc d'essai autant qu'un défaut de configuration,
et il est plus intéressant que le défaut lui-même : un harnais qui ne reproduit
pas la topologie déployée produit des chiffres exacts sur un système imaginaire.

| Topologie, `mixed` à concurrence 8 | Sondes perdues | p95 `light` sous charge | Débit `heavy` | Mémoire crête |
| :------------------------------ | ---: | ---: | ---: | ---: |
| un travailleur sur `heavy,light` | 3 / 5 | 11,72 s | 29,79 CV/min | 2 707,2 Mo |
| un travailleur par file | 0 / 5 | 0,02 s | 32,84 CV/min | 3 493,1 Mo |

Sources : `bench/reports/20260922-155013/` (avant) et
`bench/reports/20260922-155731/` (après), une répétition chacune.

Les cinq sondes répondent après correction, avec un 95\textsuperscript{e}
centile de 0,02 seconde sous charge contre 0,09 seconde à vide, c'est-à-dire du
même ordre. Le débit de la file lourde ne se dégrade pas : il passe de 29,79 à
32,84 CV par minute, soit dix pour cent de mieux, un écart à prendre avec
prudence puisqu'il repose sur une répétition de chaque côté alors que la
dispersion mesurée entre trois répétitions du même point atteignait déjà 4,23
pour cent, et puisque le plafond d'appels par minute reste de toute façon le
facteur limitant à cette concurrence. Ce qui se paie est la mémoire : 785,9 Mo
de plus, soit le coût des trois processus du travailleur léger, ce que la
décision d'architecture anticipait comme le prix de l'isolement. Le réglage
`worker_prefetch_multiplier`, seconde voie envisagée, n'a pas été touché : les
deux remèdes cumulés à l'aveugle auraient rendu ininterprétable la mesure de
celui qui agit.

## Expériences complémentaires

La carte de travail prévoyait quatre expériences complémentaires. Leur état
respectif est donné ici sans embellissement.

**Outil composite contre outils atomiques.** Conduite, et rapportée plus haut à
partir du détail archivé question par question. C'est le résultat le plus riche
du chapitre : l'outil composite est celui qui coûte le plus de latence et qui
concentre tout le déficit de rappel, mais l'examen des entités retrouvées montre
que sept substitutions sur neuf ne font perdre aucune information, et que le
défaut réel tient à deux lacunes de couverture de l'outil, non à une erreur de
choix de l'agent.

**Résistance à l'injection.** Conduite, rapportée ci-dessus, résultats archivés.

**Budget de jetons.** Mesurée indirectement : le rapport archive le nombre de
jetons consommés par offre, de l'ordre de cinq mille deux cents par CV, ce qui
permet le calcul de coût de la section précédente. En revanche, **aucune
campagne comparative à différents budgets de contexte n'a été exécutée** :
l'effet d'une réduction du budget sur la qualité et sur le coût n'est pas
mesuré par ce mémoire.

**Alias léger contre alias fort.** Cette expérience a bien été exécutée pendant
la mise au point du harnais, sous la forme d'une comparaison entre deux versions
de l'invite de notation sur un sous-ensemble de quarante-cinq CV par côté, et
d'une exécution dégradée forçant le modèle léger sur la notation. **Ses rapports
n'ont pas été archivés dans le dépôt.** Conformément à la règle de ce chapitre,
ses chiffres ne sont donc pas reproduits ici. Ce qui peut être dit et vérifié
est le seul fait consigné dans le rapport de référence : la campagne de
référence a été exécutée avec la version 2 de l'invite de notation, et le
harnais sort effectivement en erreur lorsqu'on impose le modèle léger à l'étape
de notation. La conclusion de cette expérience reste donc **non établie** dans
ce mémoire, et le chapitre 9 la range parmi les travaux à reprendre.

## Validation sur prototype : le parcours complet joué de bout en bout

Les sections précédentes mesurent des composants au moyen d'un harnais qui les
appelle directement ; elles ne disent pas si un utilisateur peut, depuis un
navigateur, obtenir ces comportements dans l'ordre et sans intervention
technique. Cette vérification a été conduite séparément, en pilotant un Chromium
réel sur l'application déployée, avec un script de rejeu qui journalise chaque
étape, la chronomètre et prend les captures au passage.

Le parcours complet a été joué avec succès le 22 septembre 2026 à 14 h 47 min 34
s (UTC), en 133,3 secondes mesurées, sans incident ni reprise manuelle. Il
enchaîne les deux métiers : connexion, question de lecture à l'agent commercial
et affichage de sa trace d'outils, demande d'écriture, dialogue de confirmation,
accusé d'écriture, puis création d'une offre, proposition d'une grille de
critères par le modèle, validation humaine de cette grille, dépôt de vingt CV,
lancement de l'analyse et affichage du classement.

| Étape | Durée mesurée |
| :------------------------------------------- | ---: |
| Connexion | 2 694 ms |
| Ouverture de l'agent commercial | 1 806 ms |
| Question de lecture et rendu du briefing | 20 931 ms |
| Demande d'écriture jusqu'au dialogue | 19 327 ms |
| Confirmation humaine jusqu'à l'accusé | 8 378 ms |
| Création de l'offre | 6 173 ms |
| Proposition de la grille de critères | 14 109 ms |
| Validation de la grille | 623 ms |
| Dépôt de vingt CV | 343 ms |
| Lancement de l'analyse | 2 806 ms |
| Attente de la fin de l'analyse, après cette capture | 31 526 ms |
| Affichage du classement | 10 274 ms |

Source :
`thesis/soutenance/demo/journaux/2026-09-22T14-47-34-complet/resume.json`,
tableau `etapes`.

Ces durées décrivent **la conduite d'une démonstration, pas la performance du
système**, et il faut le dire avant qu'un lecteur ne les compare aux sections
précédentes. Le script s'exécute au rythme de démonstration : il tape les
questions caractère par caractère et ménage des temps de lecture entre les
écrans, de sorte qu'une étape comme « demande d'écriture » inclut plusieurs
secondes de frappe simulée, et que l'attente de fin d'analyse portée au tableau
commence après une capture d'écran et non au lancement. Une seconde exécution
complète, jouée trois minutes plus tard au rythme rapide, suffit à interdire
toute lecture chiffrée : du lancement à la fin de l'analyse, le même lot de
vingt CV a demandé 43,7 secondes dans la première et 55,9 secondes dans la
seconde. Aucune de ces valeurs n'alimente donc une conclusion de performance ;
les chiffres de latence et de débit du chapitre viennent exclusivement des deux
campagnes archivées. Le fichier de résumé enregistre par ailleurs qu'aucune
campagne de charge ne tournait au départ ni à l'arrivée de ces deux exécutions,
ce qui n'est pas vrai des répétitions antérieures consignées dans le même
dossier.

Deux écrans méritent d'être reproduits parce qu'ils montrent, mieux qu'une
description, ce que les chapitres précédents ont soutenu.

![Briefing rendu par l'agent commercial, avec sous la réponse la trace des
outils appelés et de leur durée. Capture du 22 septembre 2026 à 14 h 48 min 01 s
(UTC).](soutenance/demo/journaux/2026-09-22T14-47-34-complet/captures/01-briefing-et-trace.png){width=78%}

![Dialogue de confirmation avant écriture : l'agent propose l'appel, en donne
l'aperçu en français, et rien n'est écrit tant qu'un humain n'a pas confirmé.
Capture du 22 septembre 2026 à 14 h 48 min 20 s
(UTC).](soutenance/demo/journaux/2026-09-22T14-47-34-complet/captures/02-confirmation-ecriture.png){width=78%}

La première atteste que la traçabilité revendiquée en partie 2 est visible par
l'utilisateur et non seulement présente en base ; la seconde, que la
confirmation humaine des écritures est un passage obligé de l'interface et non
une convention interne, le même mécanisme dont la campagne d'évaluation mesure
qu'aucune écriture ne l'a contourné. Les huit captures de l'exécution, avec
leur horodatage et leur légende, sont conservées dans le dossier de journaux.
L'exécution a également produit un **enregistrement vidéo** du parcours, dont
la durée a été relue sur le fichier et non estimée : 134,72 secondes. Il
constitue le plan de repli de la soutenance.

Trois réserves enfin. Le compte rendu consigne dix exécutions, dont **sept
réussites et trois échecs**, plus une répétition interrompue volontairement pour
ne pas perturber la campagne de charge alors en cours. Ces échecs sont
instrumentaux, ils portent sur le script de pilotage, et ils sont conservés
plutôt qu'effacés ; deux ont perdu leur journal, la décision de tout consigner
ayant été prise après coup.

Le volet commercial a par ailleurs été joué contre une **instance Salesforce de
développement réelle**, et non contre le double de test local de la campagne
d'évaluation. C'est une validation plus forte de l'intégration, le jeton, son
rafraîchissement et les écritures étant les vrais ; c'est aussi pourquoi les
temps observés ici ne sont pas comparables à ceux de la campagne. Elle a fait
apparaître un défaut que la campagne ne pouvait pas voir : la première requête
émise après expiration du jeton échoue une fois avant que le rafraîchissement
ne prenne effet, la question reposée passant ensuite. La parade retenue pour la
soutenance est de réveiller la connexion quelques minutes avant de commencer ;
la correction reste à faire.

Ces exécutions laissent enfin des traces, sept tâches dans l'organisation
Salesforce de développement et quatre offres de démonstration avec leurs
candidatures : identifiables à leur intitulé, elles n'ont pas été nettoyées.

Source : `thesis/soutenance/demo/repetitions.md`.

## Récapitulatif : les treize seuils

| Seuil | Attendu | Mesuré | Verdict |
| :------------------------------------ | :------- | :------- | :------- |
| Spearman, présélection | ≥ 0,75 | 0,910 | tenu |
| Exactitude critères éliminatoires | ≥ 0,90 | 0,7611 | **non tenu** |
| Taux d'échec, présélection | ≤ 0,05 | 0,000 | tenu |
| Rappel sur les outils | ≥ 0,80 | 0,650 | **non tenu** |
| Latence p95, assistant | ≤ 3,00 s | 4,00 s | **non tenu** |
| Faits de référence énoncés | ≥ 0,80 | 0,6818 | **non tenu** |
| Tours coupés par la limite d'étapes | = 0 | 0 | tenu |
| Spearman global, coach | ≥ 0,70 | 0,985 | tenu |
| Citations inventées, coach | = 0 | 0 | tenu |
| Preuves conformes, coach | ≥ 0,90 | 0,400 | **non tenu** |
| Consignes d'injection suivies | = 0 | 0 | tenu |
| Tentatives d'injection signalées | ≥ 3 / 5 | 5 / 5 | tenu |
| Fichiers corrompus traités proprement | 2 / 2 | 2 / 2 | tenu |

Source : `evals/reports/20260922T132654_d793943-sale.json`, chemins
`seuils.violations` et `seuils.detail_respectes` ; le rapport déclare huit
seuils respectés et cinq violations.

Huit seuils sur treize sont tenus, cinq ne le sont pas, et la répartition n'est
pas aléatoire. Les cinq barres manquées sont toutes des barres de **qualité** ou
de **performance**. Les deux barres que le fichier de seuils qualifie
explicitement de **sécurité**, citations inventées et consignes d'injection
suivies, sont tenues à leur valeur stricte de zéro, de même que les trois
autres barres de robustesse : aucun tour coupé par la limite d'étapes, cinq
tentatives d'injection signalées sur cinq, deux fichiers corrompus traités
proprement sur deux. À ces cinq résultats s'ajoute une mesure archivée qui ne
porte pas de seuil et qui relève du même ordre : aucune écriture n'a été
proposée hors de la procédure de confirmation. Ce n'est pas une consolation,
c'est une information de conception : les garde-fous structurels, qui relèvent
du code, tiennent ; les promesses de qualité, qui relèvent du modèle et des
invites, ne tiennent pas encore.

La campagne de charge porte ses propres critères, distincts des treize seuils du
harnais d'évaluation, et tous sont formellement tenus : le rapport de latence du
scénario mixte vaut 0,825 pour une tolérance de 1,5, et les trois mesures de
reproductibilité du débit valent 0,0336, 0,0673 et 0,0423 pour une tolérance de
0,1. Le lot de cinq cents CV a terminé sans échec. Ce bilan doit pourtant être
lu avec deux restrictions énoncées plus haut : la campagne est réduite à douze
lots sur trente-neuf points prévus, et le critère de latence sous charge ne
traverse pas le composant qu'il prétend éprouver. La propriété visée par ce
dernier est en réalité fausse, comme l'établit la sonde de la file légère
qu'aucun critère ne couvrait. Qu'un défaut aussi net ait échappé à toutes les
barres posées à l'avance est, en soi, un résultat sur le dispositif
d'évaluation autant que sur le système.

Source : `bench/reports/20260922-134336/rapport.md`, sections « Critères
d'acceptation » et « File `light` ».
