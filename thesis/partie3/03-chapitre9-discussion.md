# Discussion, limites et perspectives

## Verdict sur les quatre hypothèses

Les verdicts qui suivent portent sur les énoncés exacts de l'introduction de la
partie 1. Aucun n'a été reformulé après les mesures, et lorsqu'un énoncé
comporte deux affirmations, les deux sont traitées séparément.

### H1 : présélection de candidatures

*Une chaîne de traitement de présélection fondée sur un modèle de langue produit
un classement de candidatures dont l'ordre s'accorde avec celui d'un annotateur
humain, pour un temps de traitement très inférieur à un examen manuel.*

**Verdict : non établie.** L'hypothèse n'est pas infirmée ; elle n'est pas
prouvée, et pour deux raisons distinctes qui tiennent l'une et l'autre au
dispositif et non au système.

La première porte sur le terme de comparaison. La corrélation de rang mesurée
est de 0,910 sur cent quatre-vingts CV, largement au-dessus du seuil de 0,75, et
stable sur les trois offres. Mais cette corrélation est établie contre une
référence **calculée**, la règle de la grille appliquée à un profil de
construction connu, et non contre le jugement d'un annotateur humain. Ce qui est
démontré est donc l'énoncé plus faible, et néanmoins utile : le pipeline
applique correctement une grille d'évaluation à un document qui l'exprime
lisiblement. La double annotation humaine de dix pour cent du jeu, qui aurait
relié cette référence calculée à un jugement humain, n'a pas été réalisée ; ses
fichiers existent, vides, dans le dépôt.

La seconde porte sur le temps. Le pipeline traite un CV en 11,5 secondes de
travail cumulé et cent quatre-vingts CV en six minutes d'horloge, sans aucun
échec. Ces chiffres sont solides. Mais aucune durée d'examen manuel n'a été
mesurée ni empruntée à une source vérifiée : la comparaison exigée par
l'hypothèse n'est donc pas faite, et écrire que six minutes sont « très
inférieures » à un examen manuel de cent quatre-vingts candidatures relèverait
de l'évidence de sens commun, pas de la mesure.

À ces deux manques s'ajoute un résultat qui, lui, est mesuré et contraire au
produit : l'exactitude sur les critères éliminatoires est de 0,7611 pour un
engagement de 0,90, avec quarante et un faux négatifs contre deux faux
positifs, tous concentrés à la frontière du niveau deux sur cinq. Même si les
deux manques de dispositif étaient comblés demain, ce défaut suffirait à
interdire une mise en service : quarante et un des cent trente-cinq candidats
que la référence déclare recevables, soit près d'un sur trois, seraient écartés
sans que le recruteur puisse s'en apercevoir.
L'hypothèse H1 n'est donc pas seulement non prouvée, elle est prématurée.

### H2 : préparation d'un rendez-vous commercial

*Un agent doté d'outils de lecture typés réduit le temps nécessaire à la
préparation d'un rendez-vous commercial par rapport à une consultation directe
du logiciel de gestion de la relation client.*

**Verdict : non démontrée, et non démontrable par ce dispositif.** L'énoncé est
intégralement comparatif : il porte sur un écart de durée entre deux façons de
travailler. Aucune des deux durées n'a été mesurée sur un opérateur humain. Le
chapitre 8 rapporte ce que l'agent produit, en 2,25 secondes de médiane, contre
un double de test ; il ne rapporte rien sur le temps qu'un commercial passerait
à obtenir la même information dans Salesforce, parce que personne n'a été
observé en train de le faire.

Cette absence n'est pas un oubli de dernière minute : elle était inscrite dans
le choix, assumé au chapitre 7, d'évaluer sans terrain. La conclusion honnête
est donc que H2 reste une hypothèse de conception, et que sa vérification
appelle un protocole d'un autre genre — un test utilisateur comparatif, sur une
base réelle, avec des commerciaux chronométrés sur des tâches appariées.

Il faut ajouter que la qualité du briefing, qui est le préalable du gain de
temps, est elle-même en deçà de l'engagement. Sept réponses sur trente omettent
au moins une entité attendue, dont deux par lacune de couverture de l'outil
composite et quatre alors que l'agent disposait pourtant de l'information ; et
le taux de faits de référence énoncés est de 0,6818 pour un seuil de 0,80, même
en tenant compte du fait que la relecture du juge en fait une estimation basse.
Un assistant dont près d'un briefing sur quatre omet une information attendue
ne fait pas gagner du temps : il déplace le travail de la consultation vers la
vérification.

### H3 : latence conversationnelle

*Une récupération contextuelle structurée, sans index vectoriel, permet de tenir
une latence de réponse conversationnelle inférieure à trois secondes au
95\textsuperscript{e} centile.*

**Verdict : infirmée.** C'est le seul énoncé entièrement vérifiable par la
machine, et la mesure le contredit : le 95\textsuperscript{e} centile est de
4,00 secondes pour un seuil de 3,00 secondes. La médiane, à 2,25 secondes, tient
largement, mais l'hypothèse ne porte pas sur la médiane, et le choix du centile
n'était pas arbitraire : c'est la queue de distribution qui décide de l'abandon
d'un outil interactif.

Quatre précisions rendent ce verdict plus utile qu'un simple échec. La
première, et de loin la plus importante, vient de la campagne de charge : elle
décompose chaque tour de conversation et attribue plus de quatre-vingt-dix-huit
pour cent du temps aux appels au modèle, contre une quinzaine de millisecondes
à l'exécution des outils et une trentaine au reste du travail local. Autrement
dit, **la partie de l'hypothèse qui portait sur la récupération est vérifiée, et
c'est la partie qui portait sur le seuil qui échoue.** La récupération
structurée ne coûte rien de mesurable ; un index vectoriel n'aurait rien fait
gagner sur ce poste, puisqu'il n'y a rien à y gagner. L'énoncé de H3 liait ces
deux choses comme si la première devait produire la seconde : la mesure les
sépare.

Deuxième précision, les questions les plus lentes sont celles qui appellent
l'outil composite de contexte de compte, dont la latence moyenne de réponse est
de 2,70 secondes contre 1,96 seconde pour la recherche de contact, et les deux
questions les plus lentes de la campagne l'appellent toutes deux. Au vu de la
décomposition ci-dessus, cet écart ne mesure pas un coût de récupération mais la
longueur de la réponse à rédiger. Troisièmement, il n'y a pas d'étapes
superflues à supprimer : chaque question consomme exactement deux appels au
modèle, aucune n'épuise la limite d'étapes, et la boucle d'agent ne tourne pas à
vide. Enfin, et c'est le point qui interdit tout optimisme, ces mesures ont été
prises contre un double de test local ; une instance Salesforce réelle
ajouterait un ou plusieurs appels réseau vers un service distant et dégraderait
le résultat.

L'hypothèse n'est pas pour autant réfutée dans son principe. Ce qu'elle
affirmait est qu'une récupération structurée **permet** de tenir trois secondes ;
la médiane mesurée montre que l'ordre de grandeur est le bon et que l'écart ne
relève pas d'une erreur de conception mais d'une queue de distribution. Le
chemin de correction est identifié, et la décomposition en écarte la moitié :
paralléliser les requêtes de l'outil composite ne rapporterait rien, puisqu'il
ne consomme rien. Restent le nombre d'appels au modèle par tour, qui est de deux
et pourrait descendre à un pour les questions dont l'outil est évident, et le
choix du modèle de rédaction, qui est aujourd'hui le repli d'un alias. Aucune de
ces deux pistes n'a été mesurée, et tant qu'elles ne le sont pas, l'hypothèse
reste infirmée.

### H4 : coût unitaire

*Le coût unitaire des appels au modèle, mesuré par organisation et par lot,
reste compatible avec le budget logiciel d'une petite ou moyenne entreprise
malgache.*

**Verdict : partiellement établie ; la mesure est faite, le jugement de
compatibilité ne l'est pas.** Le coût par CV noté est de 0,012219 dollar, il est
remarquablement stable entre les trois offres, et il est **prévisible**, parce
que la consommation par CV est régulière : deux appels au modèle et de l'ordre
de cinq mille deux cents jetons. Un lot de cent candidatures coûte donc de
l'ordre de 1,22 dollar en appels au modèle. Le dispositif d'imputation par
organisation fonctionne, chaque appel étant journalisé avec son organisation,
son agent, son alias et son coût estimé : la grandeur demandée par H4 est bien
mesurable par organisation et par lot, et elle l'est effectivement.

Ce qui manque au verdict complet est de l'autre côté de la comparaison. Le
chapitre 3 a établi que le prix est une contrainte de conception et non une
variable d'ajustement commerciale, mais il n'a pas fixé de budget logiciel
chiffré pour une entreprise cible, et aucun prix de vente n'a été arrêté par ce
mémoire. Le coût mesuré ne comprend par ailleurs ni l'hébergement, ni le
stockage, ni l'exploitation, ni aucune marge, et il est établi auprès d'un
fournisseur unique aux tarifs en vigueur à une date donnée. Affirmer la
compatibilité supposerait donc de comparer un coût partiel à un budget non
chiffré : ce chapitre s'en abstient. Ce qui peut être dit, et qui n'est pas
rien, est que le coût direct du modèle se situe à un ordre de grandeur qui ne
disqualifie pas le produit et qu'il est suffisamment prévisible pour supporter
une tarification au lot.

## Ce que les échecs enseignent

Cinq seuils manqués sur treize, une hypothèse infirmée et deux non démontrées :
il serait commode d'en conclure que le dispositif était trop exigeant. Ce serait
manquer quatre enseignements que ce travail doit à ses échecs plus qu'à ses
réussites.

**Une métrique mal définie ment avec l'assurance d'une métrique juste.** Trois
mesures de ce mémoire se sont révélées mal construites : celle des cas adverses,
qui confondait une défaillance de sécurité avec une imprécision de notation et
affichait le système comme quatre fois plus vulnérable qu'il ne l'était ; celle
des preuves du coach, qui comptait comme inventé un constat d'absence pourtant
autorisé par l'invite ; et celle du rappel sur les outils, dont le chapitre 8
montre qu'elle pénalise un sur-ensemble d'appels pourtant sans perte
d'information. Aucune des trois ne se signalait par un symptôme : le nombre
était bien formé, stable d'une exécution à l'autre, et faux. Le seul garde-fou
qui ait fonctionné est l'inspection à la main des cas individuels derrière un
agrégat surprenant. Un dispositif d'évaluation doit donc archiver le détail cas
par cas, et pas seulement les agrégats, faute de quoi il n'est pas auditable.

**Écrire les seuils avant de mesurer change ce qu'on publie.** Les treize barres
ont été posées, avec leur justification rédigée, avant la campagne de référence.
Cette antériorité n'a rien d'une formalité : elle a rendu impossible le geste
qui consiste à découvrir un résultat décevant et à ajuster la barre pour qu'il
passe. Cinq seuils manqués sont, de ce point de vue, le signe que le dispositif
fonctionne, et non qu'il est mal calibré. Un harnais qui ne produirait jamais de
mauvaise nouvelle ne mesurerait rien.

**Les garde-fous de code tiennent, les promesses de modèle ne tiennent pas
encore.** La répartition des échecs n'est pas aléatoire. Les deux barres
que le fichier de seuils qualifie explicitement de sécurité sont tenues à leur
valeur stricte de zéro, aucune consigne injectée suivie et aucune citation
inventée, comme le sont les trois autres barres de robustesse ; et la mesure
sans seuil qui relève du même ordre, le nombre d'écritures proposées hors de la
procédure de confirmation, est nulle elle aussi. Les cinq seuils manqués
relèvent tous de la qualité d'une sortie de modèle. C'est une
confirmation directe des choix de conception de la partie 2 : ce qui a été mis
dans le code — bornage de la boucle, validation de schéma, confirmation humaine
des écritures, isolation des locataires — se comporte comme prévu, parce que ce
sont des propriétés de programme. Ce qui a été confié au modèle se comporte
comme un modèle, c'est-à-dire bien en moyenne et mal aux frontières.

**Un critère peut passer alors que la propriété visée est fausse.** Le quatrième
enseignement n'était pas cherché, et c'est le plus instructif sur la valeur d'un
dispositif d'évaluation. La campagne de charge porte un critère destiné à
vérifier que la file légère n'est pas affamée par la file lourde : il compare la
latence de l'agent commercial pendant un lot à sa latence à vide, et il passe
largement, à 0,825 pour une tolérance de 1,5. Il passe pour une mauvaise raison.
L'agent commercial répond à l'intérieur du processus de l'API et ne traverse
jamais les files ; sa latence ne pouvait donc pas répondre à la question posée,
et elle aurait passé le critère même si la file légère avait été totalement
bloquée. Une sonde secondaire, qui poste une tâche légère minimale pendant le
lot, montre précisément cela : deux sondes sur cinq sans réponse, et un
95\textsuperscript{e} centile passant de 0,07 seconde à vide à 25,37 secondes
sous charge.

La leçon de méthode est qu'un critère doit être vérifié sur un point : que la
grandeur mesurée traverse bien le composant dont on veut établir la propriété.
Ce contrôle est facile à omettre parce qu'un critère mal branché ne se signale
par rien — il produit un nombre plausible, stable, et favorable. C'est le même
mécanisme que celui des trois métriques mal définies discutées plus haut, à ceci
près qu'ici la mesure était juste et que c'est la propriété inférée qui ne
suivait pas.

La leçon technique, elle, est que la séparation en deux files, `heavy` et
`light`, posée dès le départ comme une contrainte d'architecture et correctement
déclarée dans le code, ne produit aucun effet tant que les mêmes travailleurs
consomment les deux. La décision d'architecture correspondante justifiait cette
séparation en écrivant qu'un lot de cinq cents CV ne doit jamais affamer une
écriture vers le CRM ; c'est exactement ce que la campagne a observé, sur un lot
de cent CV. L'erreur n'est pas de conception, ce qui la rend à la fois bénigne à
corriger et facile à ne jamais voir : aucun test fonctionnel ne l'aurait
révélée, seule une mesure sous charge le pouvait. Une propriété que rien ne
mesure n'est pas une propriété du système, c'est une intention.

Il faut aller au bout de ce raisonnement, car la vérification d'après campagne a
démenti l'explication qui venait naturellement à l'esprit. Le serveur ne
confondait pas les deux files : ses deux unités `systemd` les séparaient déjà.
Ce qui les confondait était la cible de lancement du développement, et surtout
le harnais de charge, qui recopiait cette cible plutôt que la topologie
déployée. La mesure était donc exacte et portait sur une machine que personne
ne faisait tourner. Un banc d'essai est un artefact de recherche comme un autre :
il incarne des hypothèses, ici celle qu'un travailleur de développement
ressemble à un travailleur de production, et cette hypothèse méritait d'être
écrite et vérifiée au même titre que les autres. Après correction des deux
topologies et remesure du même point, les cinq sondes répondent, le
95\textsuperscript{e} centile de la file légère tombe de 11,72 à 0,02 seconde,
le débit de la file lourde ne se dégrade pas et la facture est mémorielle :
785,9 Mo pour le travailleur dédié.

## Limites de ce travail

Aux limites déjà exposées comme menaces à la validité, il faut ajouter celles
qui portent sur la portée de l'ensemble.

**L'annotation est unique et calculée.** La référence de présélection n'a pas
d'annotateur humain, la double annotation n'a pas eu lieu, et les annotations de
coaching portent la mention qu'elles restent à confirmer. Une convention
discutable, celle qui attribue d'office la valeur neutre au critère de gestion
des objections en l'absence d'objection exprimée, explique vraisemblablement une
partie du décrochage mesuré sur ce critère.

**Les données sont synthétiques et lisibles par construction.** Les résultats de
présélection sont une borne supérieure : un CV réel est ambigu, lacunaire,
parfois trompeur, et rien dans ce travail ne dit comment le pipeline s'y
comporte.

**Le CRM est un bac à sable.** Quarante-cinq enregistrements cohérents ne
ressemblent pas à une base d'entreprise, et le mode connecté à un bac à sable
Salesforce réel n'est pas branché : la commande le déclare et s'arrête plutôt
que de laisser croire à une exécution distante.

**Le fournisseur de modèles est unique.** Toutes les latences et tous les coûts
du chapitre 8 sont ceux d'un fournisseur unique, par retombée d'alias faute de
clé pour le second. La conception qui interdit les noms de modèle en dur rend le
remplacement possible sans toucher au code ; elle ne rend pas les chiffres
transposables.

**Aucune mesure d'équité n'a été produite.** Le risque de biais de sélection
reproduits par un modèle appliqué au tri de candidatures est documenté par la
littérature ; le jeu doré, dont les identités sont tirées au hasard et sans
corrélation avec les niveaux, ne permet pas de le mesurer. Il faudrait un
protocole de paires appariées, où deux CV identiques ne diffèrent que par un
attribut d'identité. L'absence de mesure n'est pas une absence de risque, et
c'est probablement le manque le plus sérieux de ce travail au regard d'un usage
réel en recrutement.

**Les effectifs sont petits et l'exécution est unique.** Dix textes de coaching,
trente questions commerciales, un seul rapport de référence sans répétition :
les décimales publiées ne supportent pas d'interprétation fine, et la variance
d'une campagne à l'autre n'est pas estimée.

**La campagne de charge est réduite.** Douze lots ont tourné sur les
trente-neuf points prévus, le plan complet étant estimé à près de cinq fois le
budget autorisé. Seuls les lots de cinquante CV sont répétés : la courbe de
débit en fonction de la concurrence n'est donc établie qu'à cette taille, et les
lots de cent et de cinq cents CV, qui portent les résultats les plus souvent
cités, n'ont pas de dispersion connue. La sonde de la file légère, qui a mis au
jour le défaut le plus net de l'ensemble, ne compte que cinq points de mesure.

## Portée pour le terrain malgache

Trois constats du chapitre 3 se trouvent éclairés par les mesures, et un
quatrième s'en trouve compliqué.

La **prévisibilité du coût** est probablement le résultat le plus directement
utile. Un coût par CV stable à moins de cinq pour cent près entre trois offres
différentes autorise une tarification au lot, c'est-à-dire un mode de
facturation où le client sait avant d'engager la dépense ce qu'elle sera. Pour
un marché où le prix est une contrainte de conception et non une variable
commerciale, c'est plus important qu'un coût bas obtenu de façon erratique.

Le **traitement asynchrone par lots** est validé par les mesures de temps :
cent quatre-vingts candidatures traitées en six minutes d'horloge, sans échec,
avec un suivi de progression, est un mode d'usage qui tolère une connexion
intermittente. Le chapitre 3 relevait un taux d'individus utilisant Internet de
18,7 % en 2024 et un parc d'abonnements fixes très restreint ; un traitement qui
se poursuit côté serveur pendant que l'utilisateur ferme son navigateur est
adapté à ce contexte, là où une interaction synchrone longue ne le serait pas.

L'**échec sur la latence conversationnelle** prend en revanche un relief
particulier sur ce terrain. Quatre secondes au 95\textsuperscript{e} centile ont
été mesurées depuis un serveur bien connecté, contre un double de test local.
Un utilisateur situé à Madagascar ajoute à cette chaîne sa propre liaison, et
l'appel au modèle part de toute façon vers un fournisseur hébergé hors du pays.
L'écart au seuil n'est donc pas un arrondi : il indique que la promesse
conversationnelle est, en l'état, la plus fragile des quatre.

Enfin, le **défaut sur les critères éliminatoires** a une portée qui dépasse la
technique. Un système qui écarte silencieusement quarante et un candidats
recevables sur cent quatre-vingts ne pose pas seulement un problème de qualité :
il pose un problème d'acceptabilité, et il le pose d'autant plus vivement sur un
marché du travail où une candidature écartée sans motif visible n'a aucun
recours. La conclusion pratique est que la présélection doit être présentée
comme une aide au tri et jamais comme une décision, et que l'interface doit
rendre visible et réversible l'élimination pour un critère éliminatoire, ce qui
est une exigence de produit issue directement d'une mesure.

## Évolutions identifiées

Les travaux à reprendre se rangent en trois ordres d'urgence.

**Ce qui conditionne toute mise en service.** Corriger le décalage de notation à
la frontière des critères éliminatoires, par calibrage de l'invite de notation
et, si cela ne suffit pas, en rendant l'élimination explicite et contestable
dans l'interface plutôt que silencieuse. Compléter la couverture de l'outil
composite de contexte, qui ignore les opportunités closes et dont la fenêtre
d'activités est trop étroite. Conduire la double annotation humaine de dix pour
cent du jeu, sans laquelle H1 restera non établie quelle que soit la
corrélation mesurée. Enfin, réviser la définition du rappel sur les outils pour
qu'un sur-ensemble d'appels sans perte d'information cesse d'être compté comme
un défaut. Dédier enfin des travailleurs à chacune des deux files plutôt que de
laisser un pool unique les consommer toutes deux : c'est un paramètre de
lancement, et sans lui la file légère est affamée dès qu'un lot tourne. Il
faudra ajouter au harnais une sonde permanente sur cette file, avec un seuil,
puisque cinq sondes ont suffi à établir le problème mais pas à le mesurer.

**Ce qui rendrait les mesures concluantes.** Rejouer une campagne complète avec
la configuration d'alias nominale, sur les deux fournisseurs, afin que les
chiffres de latence et de coût ne dépendent plus d'une retombée accidentelle.
Répéter la campagne de référence pour estimer la variance d'exécution à
exécution. Conduire l'expérience de comparaison entre alias léger et alias fort
sur le jeu complet et **en archiver les rapports**, ce qui n'a pas été fait.
Mesurer l'effet du budget de contexte sur la qualité et le coût. Construire un
protocole de paires appariées pour mesurer le biais d'équité en présélection.
Et, pour H2, monter un test utilisateur comparatif avec des commerciaux
chronométrés sur des tâches appariées, seul dispositif capable de trancher cette
hypothèse.

**Ce qui relève de l'évolution du produit.** L'extraction des travailleurs de
présélection sur un hôte dédié, une fois le volume établi, puisque le chapitre
8 montre que tout le temps est dans les appels au modèle et que la charge est
séparable. Le passage du stockage de documents à un service compatible avec les
interfaces objet du marché. La conteneurisation du déploiement, différée
jusqu'ici au profit d'unités système natives. L'ouverture à d'autres logiciels
de gestion de la relation client, que l'interface abstraite adoptée en partie 2
rend possible sans réécrire les agents. La reconnaissance optique de
caractères, laissée hors périmètre par le code d'extraction lui-même : les
trois CV scannés du jeu adverse sortent proprement avec un motif explicite,
mais ils sortent, et un lot réel en contient. L'entrée audio pour les comptes
rendus d'entretien, qui introduirait des données non structurées. Et, seulement
à ce moment-là, la réévaluation de l'index vectoriel écarté par la décision
d'architecture : il n'a pas de justification sur des données structurées, il en
aurait sur des transcriptions.

## Contributions

Ce mémoire revendique quatre contributions, dont aucune n'est un résultat de
recherche fondamentale.

La première est un **système complet et cohérent**, où chaque décision
d'architecture est consignée, justifiée et vérifiable dans un dépôt : un
monolithe modulaire multi-locataire, isolé au niveau de la base de données,
doté d'un exécutif d'agent unique et borné, d'invites versionnées et d'une
passerelle qui ne connaît que des alias de modèles.

La deuxième, et la plus transposable, est un **dispositif d'évaluation
exécutable** : un jeu de données de référence synthétique, régénérable à
l'identique et sans donnée personnelle, un harnais qui rejoue ce jeu contre le
code de production et échoue lorsqu'un engagement de service n'est pas tenu, et
des seuils écrits avant la mesure avec leur justification. Ce dispositif est ce
qui a permis au présent chapitre de rendre des verdicts négatifs plutôt que des
impressions favorables.

La troisième est un **corpus de résultats négatifs documentés**, ce qui est plus
rare que l'inverse dans la littérature d'ingénierie : trois métriques dont la
définition s'est révélée fausse à l'usage et dont le mode de défaillance est
décrit, un défaut de notation localisé à une frontière précise, un échec de
latence dont la cause est identifiée, et deux hypothèses dont le mémoire établit
qu'elles ne peuvent pas être tranchées par le dispositif choisi.

La quatrième est une **mise à l'épreuve du contexte** décrit en partie 1 : les
contraintes déduites d'une analyse documentaire du terrain malgache ont été
traduites en décisions d'architecture, puis confrontées à des mesures, et le
chapitre montre lesquelles résistent et laquelle ne résiste pas.

## Conclusion de la partie 3

Le système construit fonctionne, au sens où il traite de bout en bout les deux
parcours qu'il promet, sans échec et sans franchir aucun de ses garde-fous de
sécurité. Il ne tient pas encore ses promesses de qualité : cinq engagements de
service sur treize sont manqués, l'hypothèse de latence est infirmée, et les
deux hypothèses qui comportaient une comparaison avec un opérateur humain
restent hors d'atteinte du dispositif retenu.

Ce résultat mitigé est, tel quel, le principal acquis du travail. Il n'a été
possible de l'énoncer que parce que les seuils avaient été écrits avant les
mesures, parce que le détail de chaque cas a été archivé à côté des agrégats, et
parce que trois métriques ont été refaites lorsqu'il est apparu qu'elles
mesuraient autre chose que leur nom. Un mémoire qui aurait présenté une
corrélation de 0,910 et une médiane de 2,25 secondes sans dire le reste aurait
été plus flatteur et moins vrai.
