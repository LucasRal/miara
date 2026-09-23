# Méthodologie d'évaluation

## Objet du chapitre et question préalable

Ce chapitre décrit le dispositif qui a produit les chiffres du chapitre 8. Il
le fait avant de les présenter, et de façon suffisamment détaillée pour qu'un
lecteur puisse contester une mesure sans avoir à deviner comment elle a été
prise. C'est une exigence ordinaire de méthode ; elle est ici d'autant plus
nécessaire que le système évalué comporte un composant non déterministe, et
qu'une évaluation mal définie d'un tel système produit des nombres qui ont
toutes les apparences de la rigueur sans en avoir la substance.

Une question préalable gouverne tout le reste : que peut-on prouver au sujet
d'un logiciel d'entreprise lorsqu'on ne dispose d'aucune entreprise ? Le
mémoire ne s'appuie sur aucun client, aucun recruteur, aucun commercial, aucune
base Salesforce de production. La partie 1 a déjà signalé cette limite pour son
analyse de besoins, déduits de conditions observables plutôt que constatés
auprès d'utilisateurs. Elle vaut ici avec plus de force encore, parce qu'une
mesure de performance n'a d'intérêt qu'au regard de ce qu'elle remplace, et que
ce qu'elle remplace est un travail humain qui n'a pas pu être chronométré.

La réponse retenue est de séparer nettement trois ordres de preuve et de ne
jamais faire passer l'un pour l'autre. On peut **mesurer avec rigueur** ce que
le système produit : la corrélation entre son classement et une référence
calculable, le choix des outils qu'il appelle, sa latence, son coût, son
comportement face à des entrées hostiles. On peut **documenter honnêtement** les
conditions dans lesquelles ces mesures ont été prises, jusqu'à leurs défauts.
On ne peut pas, en revanche, **établir un gain** par rapport à une pratique
humaine que l'on n'a pas observée. Les hypothèses H1 et H2 comportent
précisément une telle comparaison, et le chapitre 9 en tirera les conséquences
plutôt que de les contourner.

## Les quatre hypothèses et la preuve que chacune exige

Les hypothèses sont reprises ici dans les termes exacts de l'introduction de la
partie 1, parce que le chapitre 9 devra rendre un verdict sur ces énoncés et
non sur une version assouplie en cours de route.

**H1.** *Une chaîne de traitement de présélection fondée sur un modèle de
langue produit un classement de candidatures dont l'ordre s'accorde avec celui
d'un annotateur humain, pour un temps de traitement très inférieur à un examen
manuel.* L'énoncé contient deux affirmations distinctes, et deux exigences de
preuve distinctes : une mesure d'accord de rang avec une référence **humaine**,
et une comparaison de durée avec un examen **manuel**. La première suppose une
annotation humaine ; la seconde suppose un chronométrage humain.

**H2.** *Un agent doté d'outils de lecture typés réduit le temps nécessaire à la
préparation d'un rendez-vous commercial par rapport à une consultation directe
du logiciel de gestion de la relation client.* L'énoncé est entièrement
comparatif : il ne porte pas sur la qualité du briefing produit mais sur un
écart de durée entre deux façons de préparer un rendez-vous. Sa preuve exige
donc deux mesures, dont l'une porte sur un opérateur humain devant une
interface Salesforce.

**H3.** *Une récupération contextuelle structurée, sans index vectoriel, permet
de tenir une latence de réponse conversationnelle inférieure à trois secondes au
95\textsuperscript{e} centile.* C'est le seul énoncé entièrement vérifiable par
la machine : il fixe une grandeur, un seuil et un centile. Il est donc aussi le
seul qui puisse être franchement infirmé, et il l'est.

**H4.** *Le coût unitaire des appels au modèle, mesuré par organisation et par
lot, reste compatible avec le budget logiciel d'une petite ou moyenne
entreprise malgache.* L'énoncé mêle une mesure, le coût unitaire, et un
jugement de compatibilité qui dépend d'un budget de référence et d'un prix de
vente. La mesure est faisable ; le jugement suppose des éléments que le mémoire
emprunte au chapitre 3 et un prix qui n'a pas été fixé.

Cette lecture ligne à ligne n'est pas une précaution oratoire. Elle détermine
quelles mesures le dispositif a été construit pour prendre, et elle rend
visibles, dès ce chapitre, les deux trous du dispositif : il n'y a pas de
mesure humaine de comparaison, et il n'y a pas de référence humaine
d'annotation. Le reste du chapitre expose ce qui a été construit à la place, et
ce que cela permet de conclure.

## Une stratégie d'évaluation sans entreprise réelle

Trois substituts ont été construits, chacun couvrant une partie de ce
qu'apporterait un terrain réel.

Le premier est un **jeu de données de référence entièrement synthétique**, dit
jeu doré, versionné dans le dépôt et régénérable à l'identique. Il remplace les
candidatures réelles et la base CRM réelle. Sa construction fait l'objet de la
section suivante, et le prix à payer pour cette commodité est discuté dans les
menaces à la validité : un document fabriqué pour porter un niveau connu est
plus lisible qu'un vrai document.

Le deuxième est un **harnais d'évaluation automatisé**, qui rejoue ce jeu contre
le code de production et écrit un rapport daté, comparable d'une exécution à
l'autre, et qui fait échouer la commande lorsqu'une métrique passe sous son
seuil. Il remplace la boucle de retour d'un client qui signale une régression.
Son intérêt méthodologique tient moins à ce qu'il mesure qu'à ce qu'il rend
impossible : une fois les seuils écrits, il n'est plus possible de découvrir un
résultat décevant et de choisir, après coup, de ne pas le publier.

Le troisième est une **campagne de charge**, exécutée sur la machine de
déploiement et non sur le poste de développement, qui mesure le débit, la
latence, le coût et la tenue du système sous des volumes croissants. Elle
remplace l'observation d'un système en production.

Aucun de ces trois substituts ne remplace un utilisateur. Le dispositif inclut
donc un quatrième volet, de nature différente et de portée bien moindre : une
**validation sur prototype**, c'est-à-dire l'exécution réelle du parcours
utilisateur complet contre l'application en fonctionnement, assortie de
captures datées. Elle ne mesure pas un gain ; elle atteste qu'un chemin
fonctionne de bout en bout, ce qui n'est pas rien et n'est pas davantage.

## Le jeu de données de référence

### Composition

Le jeu doré se compose de cinq blocs. Trois **offres d'emploi** rédigées à la
main en français pour une entreprise fictive, chacune accompagnée de sa grille
d'évaluation à six critères pondérés, dont certains éliminatoires ; la grille
est validée par le schéma de production, si bien que le jeu d'évaluation et le
pipeline manipulent exactement le même objet. **Cent quatre-vingts CV**, soit
soixante par offre, répartis en quatre strates de quinze, la moitié au format
PDF et la moitié au format DOCX, les deux formats étant présents dans chaque
strate. **Trente questions commerciales** annotées, accompagnées d'une graine de
bac à sable CRM de quarante-cinq enregistrements. **Dix comptes rendus
d'entretien** annotés critère par critère pour la suite de coaching. Enfin
**dix cas adverses** : cinq CV porteurs d'une injection de consigne, trois CV
scannés sans couche de texte, deux fichiers corrompus, auxquels s'ajoute un
texte de coaching piégé.

Le jeu ne contient aucune donnée à caractère personnel : noms tirés de listes
fictives, adresses électroniques sur le domaine réservé `exemple.invalid`,
numéros de téléphone d'une plage réservée à la fiction, et aucune donnée
sensible au sens de l'article 9 du règlement général sur la protection des
données [@gdpr2016]. Cette propriété n'est pas accessoire : elle autorise le
versionnement du jeu dans le dépôt, donc sa republication avec le mémoire, donc
la reproductibilité de l'évaluation par un tiers.

### Une vérité de construction plutôt qu'un jugement

Le point le plus discutable, et donc celui qui doit être exposé le plus
clairement, est l'origine des annotations de la suite de présélection. Elles ne
sont pas le jugement d'un annotateur. Elles sont **calculées**.

Le procédé est le suivant. Pour chaque CV, un profil est tiré d'abord : un
niveau de zéro à cinq sur chacun des six critères de la grille, selon la strate
visée. Le texte du CV est ensuite assemblé à partir de briques de rédaction
correspondant à ces niveaux, chaque critère disposant de six formulations, de
l'absence totale de mention à l'expertise chiffrée. Le score de référence est
enfin obtenu en appliquant à ces mêmes niveaux les fonctions de production qui
alignent les critères sur la grille et calculent la note globale : moyenne
pondérée ramenée sur cent, et zéro dès qu'un critère éliminatoire est manqué.

Ce choix a deux conséquences opposées qu'il faut tenir ensemble. Du côté
favorable, le label n'est l'opinion de personne : c'est la règle de la grille
appliquée à un profil connu, recalculable et stable, et tout écart entre le
label et la sortie du pipeline est un écart de **lecture du document** par le
modèle, jamais un désaccord d'appréciation. Aucune dérive d'annotateur n'est
possible, et l'interdiction de retoucher un label après avoir vu les scores du
modèle devient mécaniquement vérifiable dans l'historique du dépôt.

Du côté défavorable, et c'est décisif pour la lecture de H1 : **la référence
n'est pas humaine**. Un accord élevé entre le pipeline et cette référence
démontre que le pipeline applique correctement une grille à un document, non
qu'il s'accorde avec un recruteur. Le dispositif prévoyait de combler cet écart
par une double annotation humaine de dix pour cent du jeu, soit dix-huit CV
répartis sur les trois offres, dont les fichiers existent avec leurs colonnes
de notation délibérément vides. **Cette double annotation n'a pas été réalisée.**
Aucune valeur d'accord inter-annotateur ou intra-annotateur n'a été fabriquée
pour la remplacer, et le critère correspondant reste non tenu. Le chapitre 9 en
tire la conséquence sur H1.

Une convention du bloc de coaching mérite le même traitement : lorsqu'un compte
rendu ne fait état d'aucune objection du client, le critère de gestion des
objections est fixé à trois sur cinq, valeur neutre. C'est un choix défendable
et contestable, il a été fait avant les mesures, et les annotations de coaching
portent la mention explicite qu'elles restent à confirmer par un annotateur
humain.

### Strates et reproductibilité

Les quatre strates ont des plages de score disjointes et ordonnées : de
quatre-vingt-neuf à quatre-vingt-dix-huit pour la strate *excellent*, de
soixante à soixante-dix-huit pour *bon*, de vingt-neuf à cinquante et un pour
*limite*, et zéro pour *hors profil*, par l'effet de la règle éliminatoire. La
disjonction est ce qui donne un sens à une corrélation de rang et à une
précision aux K premiers ; l'uniformité de la strate *hors profil* crée en
revanche quarante-cinq valeurs identiques, dont la section suivante montre
qu'elle impose un choix explicite dans le calcul de la corrélation.

Les noms de fichiers sont neutres et les strates mélangées dans la
numérotation : ni le numéro ni le format ne trahissent le niveau, condition
d'une annotation en aveugle si elle est un jour conduite. La génération est à
graine fixe et produit des fichiers identiques octet pour octet, horodatages
compris, propriété vérifiée par les tests du dépôt. Cette exigence est la
condition pour que deux rapports séparés de plusieurs semaines restent
comparables, et pour que la comparaison de deux versions d'invite ne soit pas
polluée par une variation du jeu.

## Les métriques et leur justification

Une métrique n'est jamais neutre : elle décide de ce qui compte comme une
erreur. Chacune de celles qui suivent a été choisie pour une raison qui se
formule dans les termes du métier, et non pour sa commodité statistique.

La **corrélation de rang de Spearman** mesure l'accord entre le classement
produit et le classement de référence [@spearman1904proof]. Elle est préférée à
un écart de note parce que le produit promet un classement et non une notation
absolue : un pipeline qui noterait tous les candidats dix points trop bas, mais
dans le bon ordre, rendrait exactement le service attendu. Le calcul est fait en
corrélation de Pearson sur les rangs, avec rang moyen pour les ex aequo, et non
par la formule simplifiée en somme des carrés des différences, qui n'est valide
qu'en l'absence d'ex aequo ; ce détail n'en est pas un ici, puisque
quarante-cinq candidats de la strate *hors profil* partagent la même note de
zéro.

La **précision aux dix et aux vingt premiers** mesure ce que le recruteur voit
réellement, c'est-à-dire le haut de la pile. Elle a un défaut assumé : les ex
aequo de la référence sont départagés par le nom de fichier, procédé
déterministe mais arbitraire à la frontière exacte du K retenu.

L'**exactitude sur les critères éliminatoires** est une décision binaire, et le
harnais en rapporte les quatre cases plutôt que le seul taux global, parce que
les deux erreurs n'ont pas le même coût. Un faux positif, c'est-à-dire un
candidat retenu à tort, sera écarté à l'entretien suivant. Un faux négatif,
c'est-à-dire un bon candidat écarté par une lecture erronée d'un critère
éliminatoire, disparaît du processus sans que personne ne s'en aperçoive : c'est
l'erreur la plus coûteuse du produit, et elle est invisible par construction.
Cette asymétrie justifie à elle seule que l'exactitude soit publiée avec son
détail.

Le **F1 sur le choix des outils** compare l'ensemble des outils de lecture
appelés à l'ensemble minimal attendu pour la question. La comparaison porte sur
des ensembles et non sur des listes : un outil appelé deux fois reste un outil
appelé, et le nombre d'appels est mesuré séparément. Précision et rappel sont
publiés séparément parce qu'ils ne coûtent pas la même chose : un outil de trop
coûte une fraction de seconde, un outil manquant coûte une information absente
du briefing. C'est le rappel qui porte le seuil.

La **latence** est publiée en médiane et en 95\textsuperscript{e} centile, jamais
en moyenne. C'est la queue de la distribution qui décide de l'abandon d'un outil
interactif, non sa tendance centrale [@dean2013tail], et les seuils de temps de
réponse au-delà desquels l'attention d'un utilisateur décroche sont documentés
depuis les premiers travaux d'ergonomie informatique [@miller1968response ;
@nielsen1993usability]. Le centile est calculé par interpolation linéaire entre
les deux observations qui l'encadrent, précaution qui évite qu'un arrondi vers
le bas fasse passer un seuil pour tenu sur un échantillon de trente points.

Le **coût** est rapporté par unité de travail, c'est-à-dire par CV noté et par
campagne, et non par appel ou par millier de jetons. C'est la seule forme qui
permette de discuter un prix de vente, donc la seule qui réponde à H4.

Les **mesures de sécurité** sont traitées à part des mesures de qualité et leur
seuil est à zéro. Une consigne injectée suivie une fois sur cinq n'est pas une
performance moyenne, c'est une faille ; une citation présentée comme extraite
du document et introuvable dans celui-ci n'est pas une imprécision, c'est une
affirmation fausse présentée à l'utilisateur comme un fait.

Enfin, les **faits énoncés en langage libre** sont évalués par un modèle juge,
faute de pouvoir être reconnus par comparaison de chaînes. La littérature
documente les biais de ce procédé : préférence pour les réponses longues,
sensibilité à l'ordre de présentation, indulgence envers les productions de
modèles apparentés [@zheng2023mtbench ; @liu2023geval]. Trois garde-fous en
découlent, tous implémentés. Le juge ne tranche que des présences de faits
fermés, jamais une qualité. Il dispose de son propre alias de modèle, distinct
de ceux des agents métier, afin qu'un changement de modèle côté produit ne
déplace pas silencieusement la règle de jugement. Et chaque exécution tire un
échantillon déterministe de ses verdicts dans une feuille de relecture
humaine ; tant que cette feuille n'est pas dépouillée, les chiffres qui
dépendent du juge sont marqués comme non validés dans le rapport. Une feuille
partiellement remplie est refusée, parce que relire les cas faciles et laisser
les cas difficiles en blanc gonflerait mécaniquement le taux d'accord.

## Les seuils : des engagements pris avant la mesure

Treize seuils de service ont été écrits avant la campagne de référence, chacun
accompagné dans le dépôt d'une justification rédigée. La règle qui les gouverne
est énoncée en tête du fichier qui les porte : ce sont des **engagements**, non
des constats. Si la première mesure fixait la barre, le dispositif ne pourrait
plus rien détecter, et il suffirait de mesurer pour réussir.

| Métrique | Barre | Ce que la barre protège |
| :---------------------------- | :--------- | :-------------------------------------- |
| Spearman, présélection | ≥ 0,75 | L'ordre proposé au recruteur ; en deçà, la promesse de classement tombe |
| Exactitude critères éliminatoires | ≥ 0,90 | L'erreur la plus coûteuse et la plus invisible du produit |
| Taux d'échec, présélection | ≤ 0,05 | Au-delà, le recruteur reprend une partie du lot à la main |
| Rappel sur les outils | ≥ 0,80 | Un outil non appelé est une information absente du briefing |
| Latence p95, assistant | ≤ 3,00 s | Seuil au-delà duquel un commercial rouvre le CRM (ADR-008) |
| Faits de référence énoncés | ≥ 0,80 | La part du briefing effectivement dite ; mesure jugée, à lire avec la relecture |
| Tours coupés par la limite d'étapes | = 0 | Un tour perdu n'est pas une réponse lente |
| Spearman global, coach | ≥ 0,70 | Barre basse assumée : dix textes seulement |
| Citations inventées, coach | = 0 | Seuil de sécurité : une citation fausse discrédite les quatre autres |
| Preuves conformes, coach | ≥ 0,90 | Une note que l'utilisateur ne peut pas contester ne lui sert à rien |
| Consignes d'injection suivies | = 0 | Seuil de sécurité : une fois sur cinq n'est pas une moyenne, c'est une faille |
| Tentatives d'injection signalées | ≥ 3 / 5 | Barre inférieure : le signalement dépend de la formulation du modèle |
| Fichiers corrompus traités proprement | 2 / 2 | Un fichier illisible échoue avec un motif, sans arrêter le lot |

Source : `evals/thresholds.yaml`, où chaque barre porte sa justification
rédigée.

Deux barres méritent un commentaire. Celle du coach à 0,90 plutôt qu'à 1,00
reconnaît que le critère de ton porte sur la forme du texte entier, où
l'exigence de citation est parfois artificielle. Celle du signalement des
injections à trois sur cinq et non à cinq sur cinq sépare deux exigences de
nature différente : ne pas obéir est un comportement que le système doit
garantir, signaler la tentative dépend d'une formulation du modèle et se prête
mal à une garantie absolue.

## Protocole d'exécution

### Le harnais

Le harnais rejoue les quatre suites — présélection, assistant commercial,
coach, cas adverses — contre le **code de production**. Il ne redéfinit ni
invite, ni grille, ni calcul de note : les fonctions d'extraction, de
structuration, de notation et la boucle d'agent sont celles du dépôt, si bien
qu'un changement d'invite se voit immédiatement dans le rapport suivant.

Les mesures vivent dans une organisation dédiée, d'identifiant fixe, isolée par
les mêmes politiques de sécurité au niveau des lignes que n'importe quel
locataire. Tous les appels au modèle sont journalisés sous un préfixe `eval.*`,
de sorte que le coût d'une campagne se lise d'une requête et ne se mélange
jamais aux statistiques d'usage présentées aux clients. Le connecteur CRM
utilisé est le double de test peuplé par la graine du jeu doré ; le mode
connecté à un bac à sable Salesforce réel est déclaré non branché par la
commande elle-même, qui s'arrête plutôt que de laisser croire à une exécution
distante.

Une exécution produit trois fichiers portant le même horodatage et la même
empreinte de code : un rapport structuré complet, un résumé rédigé contenant
les tableaux destinés au chapitre 8 sans retraitement, et la feuille de
relecture du juge. Le rapport porte un numéro de version de format, et le
générateur de résumé refuse un rapport de version antérieure au lieu de le
traiter : deux définitions d'une même métrique ne doivent jamais se retrouver
dans le même tableau. La commande sort en erreur dès qu'un seuil est franchi,
et cette sortie en erreur a été vérifiée de deux manières indépendantes, par
une dégradation réelle du modèle de notation et par un fichier de seuils
volontairement resserré.

### La campagne de charge

La campagne de charge obéit à un protocole distinct parce qu'elle mesure autre
chose. Elle exécute des scénarios de présélection à cinquante, cent et cinq
cents CV, un scénario conversationnel, et un scénario mixte qui fait tourner un
lot de CV et des questions simultanément afin de vérifier que la file légère
n'est pas affamée par la file lourde. Deux instruments distincts renseignent
cette dernière question, et la distinction se révélera décisive : le critère
d'acceptation compare la latence de l'agent commercial pendant le lot à sa
latence à vide, tandis qu'une sonde secondaire poste une tâche légère minimale
dans la file et chronomètre sa prise en charge. Le premier passe par le
processus applicatif, le second par les files ; ils ne mesurent pas la même
chose. Chaque point est exécuté à plusieurs
niveaux de concurrence de travailleurs et répété, à graine fixe, la
reproductibilité étant elle-même une grandeur mesurée et non une hypothèse.
La campagne démarre ses propres travailleurs et **refuse de partir** si
d'autres travailleurs consomment déjà les files, parce que deux consommateurs
se partageraient les messages et la concurrence mesurée ne serait plus celle
annoncée. Un plafond de dépense dur encadre chaque campagne : un point dont le
coût estimé ne tient pas dans le reste n'est pas lancé et apparaît comme tel
dans le rapport, et un lot qui franchit le plafond en cours d'exécution est
interrompu et marqué comme interrompu, jamais présenté comme terminé.

Une propriété du corpus de charge doit être énoncée ici plutôt que découverte
au chapitre 8 : au-delà de cent quatre-vingts documents, les fichiers sont
réemployés par répétition déterministe. Le cinq-centième CV d'un lot est le même
document qu'un autre, déposé une seconde fois comme une candidature distincte.
C'est légitime pour mesurer un débit, une empreinte mémoire ou un coût, ce sont
les mêmes octets et le même travail ; c'est illégitime pour en tirer une mesure
de qualité. **Aucun chiffre de qualité ne provient donc de la campagne de
charge**, et aucun ne doit en être tiré.

## Menaces à la validité

### Validité de construit : deux métriques ont mesuré autre chose que leur nom

La menace la plus instructive de ce travail ne relève pas de l'échantillonnage
mais de la définition des mesures, et elle s'est matérialisée. Deux métriques
ont dû être refaites parce qu'elles annonçaient une grandeur et en mesuraient
une autre.

La première portait sur les cas adverses. Sa version initiale comptait comme
conforme un CV porteur d'injection dont la note ne s'écartait pas de plus de
cinq points de la référence, et affichait un résultat d'un cas conforme sur
cinq. L'inspection des cas a montré qu'aucune note n'était montée vers ce que
l'injection réclamait : les écarts observés étaient de l'erreur de notation
ordinaire, du même ordre que sur les CV sans piège. La métrique confondait donc
une **défaillance de sécurité** avec une **imprécision de notation**, et
présentait le système comme quatre fois plus vulnérable qu'il ne l'était. La
mesure de sécurité est désormais le nombre de consignes effectivement suivies,
repéré par une hausse de la note vers la valeur exigée par l'injection, et la
stabilité de la note est rapportée séparément comme mesure de qualité.

La seconde portait sur les preuves avancées par l'agent de coaching. Sa version
initiale comptait comme inventée toute preuve introuvable dans le texte du
compte rendu, y compris le constat explicite d'une absence, que l'invite
autorise pourtant et que le produit attend. Elle affichait cinquante-six pour
cent de preuves conformes. La mesure distingue désormais quatre natures de
preuve — citation vérifiée, constat d'absence, appréciation sans appui,
citation introuvable — et reconnaît une citation authentique même rognée, au
moyen d'une fenêtre glissante. Le défaut réel du produit est apparu à ce
moment-là, et il n'était pas celui que la première mesure désignait.

Ces deux épisodes valent d'être retenus au-delà du projet. Une métrique mal
définie produit un chiffre faux avec exactement la même assurance qu'une
métrique juste : rien dans le rapport ne signale la différence, le nombre est
bien formé, sa décimale est stable d'une exécution à l'autre, et il est
parfaitement faux. Le seul garde-fou qui ait fonctionné ici est l'inspection à
la main des cas individuels derrière un chiffre agrégé surprenant. Un
dispositif d'évaluation devrait donc rendre cette inspection facile, et un
résultat inattendu devrait toujours déclencher un examen de la définition de la
mesure avant toute interprétation du produit.

Le chapitre 8 en ajoutera une troisième, découverte non pas avant la campagne
mais en lisant le détail archivé de ses résultats. C'est la meilleure
justification possible de la règle qui impose d'archiver le cas par cas à côté
de l'agrégat : sans ce détail, la troisième métrique serait passée pour juste.

### Validité interne

Trois faits limitent l'attribution des résultats au système évalué.

La **référence de présélection n'est pas humaine**, et la double annotation
prévue n'a pas été faite : ce point, développé plus haut, prive H1 de la moitié
de sa preuve.

Le **fournisseur de modèles est unique**. Le fichier d'environnement utilisé
pour la campagne de référence ne comportait pas de clé pour l'un des deux
fournisseurs configurés ; les quatre alias de modèles sont donc retombés sur
les modèles d'un seul fournisseur, l'un léger et l'autre fort. Toute latence et
tout coût rapportés au chapitre 8 se lisent avec cette réserve, et une campagne
conduite avec la configuration d'alias nominale donnerait d'autres chiffres. La
conception qui interdit tout nom de modèle en dur dans le code rend ce
remplacement possible sans toucher au code, mais ne rend pas les chiffres
transposables.

Le **dépôt n'était pas propre** au moment de la campagne de référence. Le
rapport le dit en tête et son empreinte de code porte un suffixe qui le
signale : il n'est pas rejouable à l'identique depuis cette seule empreinte.
C'est une entorse à la reproductibilité, et le chapitre 8 la rappelle sous les
tableaux concernés plutôt que de la laisser dans une note de bas de page.

### Validité externe

Les documents du jeu doré sont **lisibles par construction** : le niveau est
fixé avant la rédaction, et le texte est assemblé pour l'exprimer. Un CV réel
est ambigu, lacunaire, parfois trompeur. Le jeu mesure donc la capacité du
pipeline à appliquer une grille à un document clair, non sa capacité à démêler
un document confus, et les résultats de présélection doivent être lus comme une
borne supérieure. La même réserve vaut pour le CRM : le double de test est
peuplé de quarante-cinq enregistrements cohérents, là où une base Salesforce
d'entreprise contient des doublons, des champs vides et des conventions de
saisie locales.

Aucune mesure n'a été prise **en environnement de production**, ni avec des
utilisateurs, ni sur une base Salesforce réelle. Et les mesures de charge
portent sur une machine unique, dont la configuration est consignée avec le
rapport ; elles renseignent sur un ordre de grandeur, pas sur le comportement
d'un déploiement dimensionné autrement.

Enfin, une dimension importante du domaine n'est pas mesurée du tout. La
littérature documente des biais de sélection reproduits par des modèles de
langue appliqués au tri de candidatures, portant notamment sur le nom, le genre
ou l'origine supposée [@wilson2024resumebias ; @armstrong2024siliconceiling ;
@bloomberg2024gpthiring]. Le jeu doré, dont les identités sont tirées au hasard
et sans corrélation avec les niveaux, ne permet pas de mesurer ce biais : il
faudrait pour cela un protocole de paires appariées, où deux CV identiques ne
diffèrent que par un attribut d'identité. **Aucune mesure d'équité n'est donc
produite par ce mémoire**, et l'absence de mesure ne doit pas être lue comme
une absence de risque.

### Validité de conclusion statistique

Les effectifs sont petits et il faut s'en souvenir en lisant les décimales. La
suite de coaching porte sur dix textes : ses corrélations bougent beaucoup d'une
exécution à l'autre, ce que le seuil délibérément bas de cette suite reconnaît.
La suite commerciale porte sur trente questions, si bien que le
95\textsuperscript{e} centile de latence s'appuie sur un très petit nombre
d'observations en queue de distribution et qu'une seule question lente le
déplace visiblement. Les seules mesures assises sur un effectif confortable
sont celles de présélection, avec cent quatre-vingts documents.

Par ailleurs, le rapport de référence est une **exécution unique**. Le
dispositif permet de rejouer une campagne et de comparer deux rapports terme à
terme, mais la variance d'exécution à exécution du système complet n'a pas été
estimée par répétition. Les chiffres du chapitre 8 sont donc des observations,
non des moyennes assorties d'un intervalle, et deux campagnes successives
donneraient des valeurs voisines mais différentes. Les recommandations de
publication en apprentissage automatique demandent précisément ce genre de
précision, et son absence est une limite du travail [@dodge2019showyourwork ;
@wohlin2012experimentation].

## Ce que ce dispositif permet de conclure

Le dispositif décrit ici mesure avec sérieux ce que le système produit, dans des
conditions documentées jusqu'à leurs défauts. Il ne mesure pas ce que le système
fait gagner à un utilisateur, parce qu'aucun utilisateur n'a été observé. Le
chapitre 8 s'en tient donc à ce qui a été mesuré, et le chapitre 9 distingue
soigneusement, parmi les quatre hypothèses, celle qui est infirmée, celles qui
sont partiellement établies et celles qui restent hors d'atteinte de ce
dispositif.
