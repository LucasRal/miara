# Besoins et contraintes des petites et moyennes entreprises malgaches

## Objet, méthode et limites de ce chapitre

Les deux chapitres précédents ont décrit ce qu'il est techniquement possible
de construire. Celui-ci décrit le terrain sur lequel ce produit devrait
fonctionner, et en déduit les contraintes que ce terrain impose au logiciel.
La démarche est délibérément descendante : des conditions macroéconomiques et
d'infrastructure vers des critères d'acceptabilité, puis vers des décisions
d'architecture vérifiables dans le dépôt.

La méthode est une **analyse documentaire** de sources institutionnelles
primaires : bases statistiques internationales, publications de l'institut
national de la statistique, textes de loi, rapports de bailleurs. Elle n'est
pas une enquête de terrain. Aucune entreprise malgache n'a été interrogée dans
le cadre de ce mémoire, aucun questionnaire n'a été administré, aucune
observation directe de poste de travail n'a été conduite. Cette limite est
importante et il faut l'énoncer d'emblée : les besoins présentés ici sont
**déduits** de conditions observables, non **constatés** auprès d'utilisateurs.
Les critères d'acceptabilité formulés à la fin du chapitre sont donc des
hypothèses de conception, et non des résultats d'étude d'usage. La partie 3 du
mémoire reprend cette limite au titre des menaces à la validité.

Deux précautions de lecture valent pour tous les chiffres qui suivent. Chaque
donnée est présentée avec **l'année à laquelle elle se rapporte**, distincte de
l'année de publication de la source ; les deux sont souvent éloignées de
plusieurs années, ce qui est la règle en statistique publique. Et lorsqu'une
information n'a pas pu être retrouvée dans une source primaire accessible, le
texte le signale par la mention `[À SOURCER]` plutôt que de proposer une valeur
approchée.

## Cadrage macroéconomique

Le troisième recensement général de la population et de l'habitation,
conduit en 2018 et publié en décembre 2020, dénombrait 25 674 196 habitants,
dont 80,7 % résidant en milieu rural [@instat_rgph3_2020]. Les indicateurs du
développement dans le monde de la Banque mondiale estiment la population à
environ 32,0 millions d'habitants en 2024 [@worldbank2026wdi].

Le produit intérieur brut par habitant s'établissait à environ 550 dollars des
États-Unis courants en 2024, soit environ 1 889 dollars internationaux en
parité de pouvoir d'achat [@worldbank2026wdi]. L'enquête permanente auprès des
ménages 2021-2022, publiée par l'institut national de la statistique en mars
2024, fixe le seuil national de pauvreté monétaire à 1 453 987 ariary par
personne et par an et mesure un taux de pauvreté monétaire de 77 % de la
population, dont 53,3 % en situation d'extrême pauvreté ; le taux descend à
37 % dans la capitale et monte à 83,3 % en milieu rural [@instat_epm_2024].
La même enquête relève que 68,6 % des chefs de ménage exercent dans le secteur
informel, contre 5,3 % dans le secteur formel [@instat_epm_2024]. La mise à
jour économique de la Banque mondiale consacrée au pays en février 2025 place
la productivité au centre de son diagnostic [@worldbank_meu_2025].

Ces chiffres fixent l'ordre de grandeur qui gouverne tout le reste du
chapitre : le pouvoir d'achat logiciel d'une entreprise malgache moyenne n'est
pas celui d'une entreprise européenne, et un abonnement facturé au tarif du
marché européen est hors d'atteinte pour la quasi-totalité de la cible. Le
prix n'est donc pas une variable d'ajustement commerciale : c'est une
**contrainte de conception**, qui remonte jusque dans le choix des modèles
appelés et dans la façon dont le contexte leur est envoyé.

## Le tissu productif

### Une définition de travail

La définition de la petite et moyenne entreprise varie selon le texte qui la
fixe. Plutôt que de trancher, nous adoptons ici la classification employée par
les enquêtes auprès des entreprises de la Banque mondiale, qui a le mérite
d'être celle dans laquelle les chiffres cités plus bas sont produits :
**petite** de cinq à dix-neuf salariés, **moyenne** de vingt à
quatre-vingt-dix-neuf, **grande** au-delà [@wbes_madagascar_2022]. S'y ajoute,
pour notre propos, un critère fonctionnel : l'entreprise visée n'a pas de
département informatique constitué, et ses décisions d'outillage sont prises
par son dirigeant ou par un responsable opérationnel.

### La masse : des unités individuelles, hors du champ d'un logiciel payant

L'enquête nationale sur l'emploi et le secteur informel conduite par l'institut
national de la statistique dénombre, pour le dernier trimestre de 2012,
2 268 900 unités de production individuelles hors agriculture, élevage, chasse
et pêche dans les branches marchandes, dont 99,9 % sont classées comme unités
de production informelles, c'est-à-dire ne possédant pas de numéro statistique
ou ne tenant pas de comptabilité écrite ayant une valeur administrative
[@instat_enempsi2012_tome2]. La même enquête établit une taille moyenne de
1,4 emploi par unité, un taux de salarisation de 10 %, et relève que sept
unités sur dix ne comptent qu'un seul actif occupé, le chef d'unité lui-même.

Ces chiffres se rapportent à 2012 et ont été publiés en novembre 2013. Nos
recherches n'ont pas permis d'identifier d'enquête nationale ultérieure portant
spécifiquement sur l'emploi et le secteur informel : cet écart de plus d'une
décennie est la limite temporelle la plus sérieuse du corpus disponible, et
nous ne la comblons pas par extrapolation. L'enquête permanente auprès des
ménages 2021-2022 en donne toutefois un écho concordant, avec 68,6 % de chefs
de ménage exerçant dans le secteur informel [@instat_epm_2024].

La conséquence est nette et il faut l'énoncer sans détour : **l'écrasante
majorité des unités économiques malgaches ne constitue pas un marché pour un
logiciel d'entreprise payant**. Le marché adressable n'est pas le tissu
productif dans son ensemble ; c'est la frange formelle et structurée qui le
surplombe.

Une lacune doit par ailleurs être énoncée plutôt que contournée : **nous
n'avons trouvé aucun dénombrement officiel, récent et vérifiable des petites et
moyennes entreprises formelles malgaches**. Le site de l'organisme public
chargé du développement économique ne publie pas de statistique exploitable, et
les chiffres qui circulent sur le nombre de créations d'entreprises
proviennent de la presse, sans document source identifiable. Nous nous
abstenons donc de chiffrer le marché adressable, et le mémoire assume cette
absence.

### La frange formelle : petite, peu équipée, sous contrainte

C'est sur cette frange que porte l'enquête auprès des entreprises de 2022,
menée auprès de 402 dirigeants entre mars et novembre 2022, sur un échantillon
représentatif de l'économie privée formelle non agricole
[@wbes_madagascar_2022]. Une réserve s'impose avant d'en tirer quoi que ce
soit : cette enquête exclut les entreprises de moins de cinq salariés. Elle
décrit donc le haut de la frange formelle, et non la très petite structure qui
constitue précisément la cible envisagée ici. Ses résultats valent comme borne
supérieure de l'équipement et de la capacité d'investissement, pas comme
portrait de la cible. Trois d'entre eux éclairent directement la conception
d'un produit logiciel.

L'effectif moyen y est de 24,3 travailleurs, et de 7,4 pour les petites
entreprises. Le nombre d'utilisateurs par client payant sera donc faible : un
produit qui n'est rentable qu'à partir de plusieurs dizaines de licences par
client ne trouvera pas son marché.

L'intensité technologique est basse : 10,1 % des entreprises déclarent avoir
introduit un procédé innovant, contre 31,8 % pour la moyenne de l'Afrique
subsaharienne, et 10,3 % déclarent des dépenses de recherche et développement.
De même, 10,5 % seulement proposent une formation formelle à leurs salariés.
Un produit qui suppose une conduite du changement interne, ou une formation
préalable des utilisateurs, se heurtera à cette réalité : il doit être
compréhensible sans formation.

Enfin, interrogées sur l'obstacle principal à leur activité, 26,2 % des
entreprises citent l'accès au financement, 17,3 % l'électricité et 17,3 %
l'instabilité politique. Le logiciel n'apparaît pas dans cette liste, et c'est
un enseignement en soi : un outil numérique ne sera adopté que s'il s'adresse
à une douleur immédiate et mesurable, et non comme une modernisation en soi.

Ces constats rejoignent la littérature sur l'adoption des technologies de
l'information par les petites entreprises d'Afrique subsaharienne, qui
identifie de façon convergente le coût, les compétences et l'infrastructure
comme les trois freins dominants [@achieng_malatji_2022 ; @makiwa_steyn_2016 ;
@jeza_lekhanya_2022 ; @tsambou_kamga_2020]. Aucune de ces études ne porte
spécifiquement sur Madagascar, ce qui limite la portée du transfert.

## L'infrastructure : deux contraintes dures

### L'électricité

L'accès à l'électricité concernait 42,5 % de la population en 2024
[@worldbank2026wdi]. Ce taux, qui progresse mais reste bas, se double d'un
problème de **continuité** du service : la régularité de la fourniture,
mesurée par la fréquence et la durée des coupures subies par les entreprises,
détermine autant que le taux de raccordement ce qu'un logiciel peut supposer
de son environnement d'exécution.
L'enquête auprès des entreprises de 2022 mesure précisément cette
discontinuité du côté des entreprises formelles : 52,4 % d'entre elles
déclarent subir des pannes d'électricité, avec une moyenne de 6,3 coupures par
mois type, et le raccordement au réseau demande 73,0 jours en moyenne à
compter de la demande [@wbes_madagascar_2022]. Rappelons que ces chiffres
portent sur des entreprises déjà raccordées et déclarées : ils décrivent le
meilleur cas, non le cas moyen du pays. La mise à jour économique de février
2025 décrit une fourniture électrique insuffisante et instable qui pèse sur la
production et renchérit les coûts, les entreprises se rabattant sur des groupes
électrogènes plus onéreux, et chiffre à 1,1 % du produit intérieur brut le coût
budgétaire des subventions à la société nationale d'électricité et aux
carburants en 2024 [@worldbank_meu_2025].

La conséquence pour la conception est double. Côté client, on ne peut pas
supposer un poste de travail allumé en continu, ni une session longue non
interrompue : toute opération longue doit être **reprenable**, et son état doit
vivre sur le serveur et non dans l'onglet du navigateur. Côté serveur, un
hébergement local sur site est exclu ; le service doit vivre dans un centre de
données disposant d'une alimentation garantie, ce qui, pour un projet de cette
taille, signifie un serveur virtuel loué.

### La connectivité

Trois sources de niveaux différents décrivent la connectivité du pays, et leur
divergence est instructive.

Les indicateurs du développement dans le monde établissent la proportion
d'individus utilisant Internet à 18,7 % en 2024, les abonnements de téléphonie
mobile à 75,5 pour cent habitants en 2023, et les abonnements au haut débit
fixe à 0,124 pour cent habitants pour cette même année 2023
[@worldbank2026wdi]. L'enquête permanente auprès des ménages 2021-2022 mesure,
elle, que 54,6 % de la population utilise au moins un téléphone et que 7,1 %
seulement a accès à Internet [@instat_epm_2024]. L'observatoire de l'autorité
de régulation des technologies de communication recense pour l'exercice 2023
23 539 295 cartes SIM actives, 9 609 422 abonnés à l'Internet mobile et
38 141 abonnements à l'Internet fixe [@artec_observatoire_2023].

L'écart entre 18,7 % et 7,1 % ne doit pas être dissimulé, mais il ne
s'explique pas par la différence d'année. La même série des indicateurs du
développement dans le monde donne 13,7 % en 2021 et 17,8 % en 2022, c'est à
dire sur la période de référence de l'enquête permanente elle-même : à année
comparable, le rapport entre les deux mesures reste de l'ordre de deux. L'écart
est définitionnel. L'enquête permanente mesure la part de la population qui a
*accès* à Internet, sans plancher d'âge, sa ventilation descendant jusqu'à la
tranche des dix à quinze ans. L'indicateur repris par la Banque mondiale, dont
les métadonnées désignent l'Union internationale des télécommunications comme
organisme producteur, mesure les individus ayant *utilisé* Internet au cours
d'une période récente. Ce sont deux objets différents, mesurés sur deux bases
de population différentes. Nous n'avançons pas d'explication sur la méthode
d'estimation employée en amont de cet indicateur : l'entrepôt de données de
l'Union internationale des télécommunications refuse les requêtes automatisées
et nous n'avons pas pu en lire la documentation. Nous retenons la fourchette
plutôt que l'un des deux chiffres, et nous en tirons deux conclusions qui,
elles, ne dépendent pas du choix.

La première est que **la connectivité est mobile, et seulement mobile** :
38 141 abonnements fixes pour un pays de plus de trente millions d'habitants
signifient qu'aucun poste de travail ne peut être supposé relié par une liaison
fixe fiable. La seconde est que **la bande passante par utilisateur est faible
et le volume est compté**, l'accès passant par des forfaits de données mobiles.

Nous n'avons pas pu vérifier le coût d'un gigaoctet de données mobiles rapporté
au revenu : les jeux de données publiés par l'Alliance for Affordable Internet
ne répondent plus à leurs adresses connues, et les prix publiés par l'Union
internationale des télécommunications n'ont pas été accessibles.
`[À SOURCER : coût d'un gigaoctet de données mobiles à Madagascar rapporté au
revenu national brut par habitant — source primaire à retrouver]`

En revanche, un élément de coût est établi : l'évaluation de l'économie
numérique conduite par la Banque mondiale en 2019 relevait une fiscalité de
30 % sur les biens et services des technologies de l'information, taxe sur la
valeur ajoutée et droits d'accise cumulés [@worldbank_dea_madagascar_2019]. Le
coût d'accès n'est donc pas seulement un coût d'opérateur : il est aussi un
coût fiscal.

Les conséquences pour la conception sont précises. L'interface doit être
**économe en octets** : pas de transfert de données massif vers le navigateur,
pas de rechargement complet de page pour une mise à jour partielle. Les
opérations longues, comme le traitement d'un lot de candidatures, ne doivent
pas maintenir une connexion ouverte pendant plusieurs minutes, mais notifier
une progression. Et surtout, la latence d'un aller-retour vers un fournisseur
de modèles hébergé hors du pays s'ajoute à toutes les autres : le budget de
trois secondes que nous nous fixons pour une réponse conversationnelle doit
être tenu **malgré** cette latence réseau, ce qui interdit de multiplier les
appels au modèle et impose de regrouper les requêtes vers le système
d'information client.

### Payer le service

Un produit vendu par abonnement suppose un moyen d'encaissement. L'évaluation
de l'économie numérique de 2019 dénombrait 2,3 agences bancaires pour
100 000 adultes, 1,2 million d'utilisateurs actifs de monnaie électronique et
trois opérateurs de monnaie mobile [@worldbank_dea_madagascar_2019] ; l'enquête
auprès des entreprises de 2022 établit que 8,0 % seulement des entreprises
formelles disposent d'un prêt bancaire ou d'une ligne de crédit, et que 94,5 %
de leurs investissements sont financés sur fonds propres
[@wbes_madagascar_2022]. La carte de crédit internationale, moyen de paiement
implicite de la quasi-totalité des logiciels en tant que service, n'est donc
pas un moyen de paiement raisonnable sur ce marché. Cette question n'est pas
traitée dans le périmètre technique du présent mémoire, mais elle doit être
signalée comme un obstacle réel à la commercialisation.

## Compétences et exploitation

Un produit destiné à ce marché ne peut pas supposer la présence, chez le
client, de compétences d'administration système ; il ne peut pas non plus
supposer, chez l'éditeur, une équipe d'exploitation. Le projet décrit dans ce
mémoire est conduit par une seule personne, sur six mois, et devrait être
exploité dans les mêmes conditions.

Cette contrainte a deux traductions techniques directes. D'une part, le produit
doit être livré en **logiciel en tant que service** : l'installation chez le
client est exclue, puisqu'elle supposerait une compétence locale d'exploitation
et multiplierait les environnements à maintenir. D'autre part, la pile
technique retenue doit privilégier le **nombre de pièces mobiles minimal**
compatible avec les exigences fonctionnelles : chaque service supplémentaire à
superviser, sauvegarder et mettre à jour est un coût récurrent pour une
personne seule.

Du côté du client, le chiffre déjà cité de 10,5 % d'entreprises proposant une
formation formelle [@wbes_madagascar_2022] indique que la montée en compétence
des utilisateurs ne peut pas être supposée : elle doit être portée par
l'interface elle-même. La mise à jour économique de 2025 relève de son côté
qu'environ un tiers des entreprises citent le manque de main-d'œuvre qualifiée
parmi leurs contraintes principales, et, plus frappant encore, que l'adoption
technologique des entreprises malgaches a **reculé** depuis 2013 sur plusieurs
dimensions, dont la possession d'un site internet propre
[@worldbank_meu_2025]. Nous reprenons ce constat sous sa forme qualitative :
les valeurs chiffrées de la figure correspondante n'ont pas pu être extraites
du document de façon fiable, et nous ne les approximons pas.

`[À SOURCER : indicateurs sur les compétences numériques et sur le vivier de
développeurs à Madagascar — source institutionnelle primaire à identifier ;
l'évaluation de l'économie numérique de la Banque mondiale de 2019 comporte une
section sur les compétences et le secteur des services externalisés, mais son
encodage de police empêche l'extraction fiable des chiffres
[@worldbank_dea_madagascar_2019]]`

## Le cadre juridique des données personnelles

Deux questions juridiques se posent à un service qui traite, pour le compte
d'entreprises malgaches, des données de clients et de candidats à l'emploi :
quelles obligations pèsent sur ce traitement, et que signifie le fait d'envoyer
ces données à un fournisseur de modèles situé à l'étranger.

Madagascar dispose d'un texte dédié : la loi n° 2014-038 sur la protection des
données à caractère personnel, adoptée par l'Assemblée nationale le 16 décembre
2014 et promulguée le 9 janvier 2015 [@loi_2014_038]. Son article 4 institue
une autorité indépendante, la Commission malagasy de l'informatique et des
libertés. Un manuel de procédures de cette commission a été publié en décembre
2025 par l'unité de gouvernance digitale de la République
[@cmil_manuel_procedures_2025], ce qui atteste d'une activité effective ; nous
n'avons toutefois pas pu établir l'étendue réelle de son contrôle ni son
activité de sanction. `[À SOURCER : rapport d'activité ou décisions publiées de
la Commission malagasy de l'informatique et des libertés ; régime applicable
aux transferts de données à caractère personnel vers un pays tiers selon la loi
n° 2014-038, article par article]`

Un second texte encadre les atteintes aux systèmes d'information : la loi
n° 2014-006 du 17 juillet 2014 sur la lutte contre la cybercriminalité
[@loi_2014_006], modifiée et complétée par la loi n° 2016-031, dont la Haute
Cour constitutionnelle a examiné la conformité en 2016
[@hcc_decision_32_2016].

Le point le plus sensible pour notre produit est celui du **transfert
transfrontalier**. Appeler un modèle hébergé à l'étranger, c'est faire sortir
du territoire le contenu d'un curriculum vitæ ou d'une fiche client. Dans
l'état de notre vérification, nous ne pouvons pas affirmer quel régime la loi
malgache applique à ce transfert, et nous nous gardons de l'approximer. Cette
question doit être tranchée par une lecture juridique avant toute mise en
service commerciale ; elle figure parmi les travaux restants signalés au
chapitre 9.

Indépendamment de l'état du droit local, trois obligations pratiques sont
retenues comme des exigences de conception, parce qu'elles sont communes à tous
les régimes sérieux de protection des données et parce que le produit vise à
terme des clients établis dans l'Union européenne, où le règlement général sur
la protection des données s'applique [@gdpr2016] et où le règlement sur
l'intelligence artificielle classe le tri de candidatures parmi les usages à
haut risque [@euaiact2024].

La première est la **minimisation** : ce qui est envoyé au fournisseur de
modèles doit être limité à ce qui est nécessaire à la tâche, et le budget de
contexte évoqué au chapitre 2 y contribue directement. La deuxième est la
**traçabilité** : il faut pouvoir répondre à la question « quelles données de
quel client sont sorties du système, quand, vers quel fournisseur, et pour
quelle finalité », ce qui suppose une journalisation par organisation de chaque
appel au modèle. La troisième est le **droit à l'effacement** : un candidat
doit pouvoir faire supprimer sa candidature et tout ce qui en dérive, ce qui
impose que les données dérivées, profils structurés et notations, soient
rattachées à la candidature et supprimées avec elle.

Enfin, la politique publique est portée par un ministère dédié, dont le
libellé officiel actuel est « Ministère du Développement Numérique, des Postes
et des Télécommunications » [@mndpt_site_2026] ; nous n'avons pas retrouvé de
document de stratégie nationale de transformation numérique en vigueur
accessible en ligne. `[À SOURCER : document de stratégie nationale du numérique
en vigueur à Madagascar — intitulé exact, autorité émettrice, année]`

## Deux besoins retenus, et le statut de ce choix

### La fonction commerciale

Le besoin visé n'est pas l'adoption d'un logiciel de gestion de la relation
client, mais la **rentabilisation** d'un logiciel déjà adopté. Le raisonnement
est le suivant : les entreprises qui disposent d'un tel outil sont, dans ce
contexte, les plus structurées — exportateurs, filiales de groupes, sociétés de
services — et ce sont aussi celles qui en sous-exploitent les données faute de
temps de saisie et de consultation. Un assistant qui lit et synthétise ces
données, et qui propose des écritures à valider, s'adresse à ce sous-ensemble.

Il faut être explicite sur le statut de ce choix. La plateforme Salesforce a
été retenue comme première intégration pour des raisons **techniques et
documentaires** — interface de programmation stable, autorisation déléguée bien
spécifiée, environnement de développement gratuit permettant des essais
reproductibles — et non parce qu'une adoption large de cette plateforme aurait
été constatée sur le marché malgache. C'est précisément pour cette raison que
l'accès au logiciel client est placé derrière une interface abstraite : le
produit doit pouvoir servir un autre outil sans réécriture du code métier.
Nous n'avons trouvé ni statistique publique sur le taux d'équipement des
entreprises malgaches en logiciel de gestion de la relation client, ni étude
revue par les pairs sur l'adoption de ces logiciels en Afrique subsaharienne.
Ce vide documentaire est, en lui-même, un argument en faveur de l'abstraction :
concevoir le produit autour d'une plateforme dont on ne peut pas établir la
présence sur le marché visé serait un pari, et l'interface abstraite en est
l'assurance.

### La présélection de candidatures

Le second besoin est moins dépendant de l'équipement logiciel préalable, ce qui
en fait le cas d'usage le plus directement transposable. Une offre d'emploi
qualifiée publiée dans un marché du travail où l'emploi formel est rare attire
un volume de candidatures sans rapport avec la capacité d'examen du recruteur,
et ces candidatures arrivent sous la forme la moins exploitable qui soit : des
documents bureautiques hétérogènes, parfois des images numérisées. Le gain
attendu n'est donc pas d'automatiser une décision, mais de produire un
**classement motivé** qui rende l'examen humain possible dans un temps
raisonnable.
Le contexte général est celui d'une économie où l'emploi salarié formel est
minoritaire : l'enquête sur le secteur informel déjà citée établissait un taux
de salarisation de 10 % dans les unités de production individuelles
[@instat_enempsi2012_tome2], et le rapport national de l'observatoire mondial
de l'entrepreneuriat consacré à Madagascar documente le poids de
l'entrepreneuriat de nécessité [@gem_madagascar_2020]. Le rapport national de l'observatoire mondial de l'entrepreneuriat consacré au
pays relève par ailleurs que 97,8 % des entrepreneurs émergents opéraient en
2019 dans des secteurs à faible intensité technologique, et 1,9 % seulement
dans la haute technologie [@gem_madagascar_2020].
`[À SOURCER : ordre de grandeur du nombre de candidatures reçues par offre
d'emploi qualifiée à Madagascar ; statistique de chômage ou de sous-emploi des
diplômés — non extraite de l'enquête permanente auprès des ménages 2021-2022]`

C'est aussi le cas d'usage le plus exposé sur le plan éthique, pour les raisons
exposées au chapitre 2 : un système qui classe des candidatures agit sur
l'accès à l'emploi, et les biais démographiques de ces modèles en contexte de
recrutement sont documentés [@wilson2024resumebias ;
@armstrong2024siliconceiling]. Le produit doit donc être conçu pour que la
décision reste humaine, pour que chaque note soit justifiée par un extrait
vérifiable du document, et pour que le classement produit soit mesurable contre
une référence.

## Critères d'acceptabilité

De l'analyse qui précède, nous retenons six critères. Ils sont formulés de
manière à être vérifiables, et la partie 3 du mémoire les confronte à des
mesures. Ce sont des critères de conception, pas des résultats d'enquête.

| Critère | Énoncé | Origine |
| --- | --- | --- |
| C1. Coût mesurable | Le coût des appels au modèle est connu par organisation et par lot, et consultable | Faible pouvoir d'achat logiciel |
| C2. Aucune installation | Le client n'installe ni ne maintient rien ; l'accès se fait par navigateur | Absence de compétence d'administration chez le client |
| C3. Exploitation par une personne | L'ensemble du service est exploitable par une seule personne sur un serveur virtuel unique | Absence d'équipe d'exploitation chez l'éditeur |
| C4. Tolérance à la coupure | Toute opération longue est asynchrone, reprenable, et son état vit côté serveur | Fourniture électrique et connexion discontinues |
| C5. Sobriété réseau | L'interface et les échanges sont économes en volume ; la réponse conversationnelle tient sous trois secondes au 95e centile | Bande passante limitée, latence intercontinentale |
| C6. Réversibilité | Changer de fournisseur de modèle ou de logiciel client se fait par configuration ou par implémentation d'une interface, jamais par réécriture du code métier | Dépendance à des fournisseurs étrangers |
| C7. Décision humaine | Aucune décision produisant un effet sur une personne n'est prise par le système ; il produit un classement motivé, chaque note étant justifiée par un extrait vérifiable | Cadre de protection des données et biais documentés |

## Ce que cela implique pour notre conception

**C1 se traduit par une table de journalisation des appels au modèle.** Chaque
appel écrit une ligne portant l'organisation, l'agent, l'alias de modèle
employé, la version de l'invite, le nombre de jetons d'entrée et de sortie, la
latence et le coût estimé. Une page d'usage expose ces chiffres par
organisation. C'est également ce qui rend mesurable l'hypothèse H4.

**C1 se traduit aussi par le routage entre modèles.** Les étapes qui ne
demandent pas de rédaction — choisir un outil, structurer un document — partent
sur un alias léger ; seules la synthèse et la notation partent sur un alias
fort. Le budget de contexte, qui borne le nombre de jetons envoyés, agit sur la
même grandeur.

**C2 et C3 se traduisent par un monolithe modulaire** (décision ADR-001) :
un seul déployable, des modules internes à frontières nettes, et un déploiement
sur un serveur virtuel unique en unités de service du système d'exploitation,
derrière un serveur mandataire assurant le chiffrement du transport. Les
services d'infrastructure — base de données, courtier de messages, cache — sont
installés nativement. Ce choix est assumé comme un choix de coût
d'exploitation, et ses limites sont discutées au chapitre 9.

**C2 se traduit par l'isolation multi-locataire au niveau de la base de
données** (décision ADR-002) : une seule base sert toutes les organisations,
avec un identifiant d'organisation sur chaque table métier et des politiques de
sécurité au niveau des lignes. C'est la seule façon de servir de nombreux
petits clients sans multiplier les bases à migrer et à sauvegarder.

**C4 se traduit par une architecture asynchrone à deux files** (décision
ADR-006). La présélection s'exécute dans un traitement par lots dont l'état est
persisté à chaque étape ; l'interface suit la progression par une diffusion
d'événements et non par une connexion bloquante ; chaque tâche est idempotente
et identifiée par une clé, de sorte qu'une reprise après incident ne produise
pas de doublon. Un échec unitaire ne fait jamais tomber le lot : une
candidature illisible s'arrête sur un état explicite, et le traitement des
autres continue.

**C5 se traduit par la récupération structurée et l'outil composite**
(décision ADR-008). Un outil unique regroupe les quatre requêtes nécessaires à
la préparation d'un rendez-vous en un seul aller-retour vers le logiciel
client, ce qui économise autant d'allers-retours réseau depuis un serveur
distant. Le module de construction de contexte tronque ensuite à un budget de
jetons fixé par la configuration. C'est ce dispositif, et non le choix d'un
modèle rapide, qui rend plausible la cible de trois secondes formulée en H3.

**C6 se traduit par deux points d'indirection.** Les modèles ne sont désignés
dans le code que par des alias fonctionnels, résolus par un fichier de
configuration unique qui déclare aussi des replis (décision ADR-011). L'accès
au logiciel client passe par une interface abstraite, dont l'implémentation
Salesforce n'est qu'une réalisation parmi d'autres possibles (décision
ADR-005). Aucun de ces deux points d'indirection n'est gratuit, mais l'un et
l'autre protègent contre une dépendance que le contexte rend
particulièrement risquée : celle d'un éditeur situé dans un pays à faible
revenu vis-à-vis de fournisseurs étrangers dont il ne maîtrise ni les tarifs,
ni les conditions d'accès.

**C7 se traduit par la forme même de la sortie de la chaîne de présélection.**
Le système produit un classement assorti, pour chaque critère, d'une note et
d'une preuve extraite du document évalué ; le harnais d'évaluation vérifie que
ces preuves figurent réellement dans le texte source, et le seuil associé est
fixé à un niveau quasi total, parce qu'une preuve absente du document est une
preuve inventée.

**Les exigences de protection des données se traduisent par la traçabilité et
par l'effacement en cascade.** La journalisation par organisation répond à la
question de ce qui est sorti du système ; la suppression d'une candidature
entraîne celle du document stocké, du profil structuré et des notations qui en
dérivent.

## Limites de cette analyse

Trois limites doivent être retenues par le lecteur. D'abord, l'absence
d'enquête de terrain, déjà signalée : les besoins sont déduits de conditions
structurelles, et un entretien avec cinq dirigeants d'entreprise pourrait
invalider une partie des critères ci-dessus. Ensuite, la fraîcheur inégale des
données : les statistiques d'infrastructure sont récentes, celles qui décrivent
le tissu d'entreprises le sont beaucoup moins, et il est possible que la
situation ait évolué depuis l'année de collecte. Enfin, le caractère non
vérifié de plusieurs éléments signalés par la mention `[À SOURCER]` : ils sont
laissés visibles à dessein, parce qu'une donnée approchée dans un mémoire vaut
moins qu'une lacune assumée, et ils constituent la première tâche de la
prochaine passe de rédaction.
