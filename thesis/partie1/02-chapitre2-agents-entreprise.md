# Agents conversationnels et systèmes multi-agents en entreprise

## Objet et périmètre du chapitre

Le chapitre précédent a montré comment un modèle de langue devient capable
d'appeler des fonctions. Ce chapitre examine ce que l'on construit avec cette
capacité dans un contexte professionnel : quelles architectures d'agents
existent, comment elles se branchent sur un système d'information, ce qu'elles
apportent aux fonctions commerciale et ressources humaines, et à quelles
conditions on peut affirmer qu'elles fonctionnent.

Nous y défendons deux positions qui structurent l'ensemble du système décrit
dans la partie 2. La première est qu'un **exécutif d'agent unique, paramétré
par plusieurs définitions d'agents**, est préférable à l'adoption d'un cadriciel
multi-agents généraliste pour un produit de cette taille. La seconde est que,
face à des données déjà structurées, la **récupération contextuelle
structurée** l'emporte sur la génération augmentée par récupération vectorielle,
sur les trois critères qui comptent pour un utilisateur professionnel :
exactitude, fraîcheur et explicabilité.

## Ce qu'on appelle un agent

### Définitions

Le mot **agent** est employé en intelligence artificielle, depuis longtemps,
pour désigner une entité qui perçoit un environnement et agit sur lui en vue
d'un objectif. Appliquée aux modèles de langue, la notion se resserre : un
**agent fondé sur un modèle de langue** est un programme dans lequel un modèle
de langue décide, à chaque étape, soit de répondre, soit d'invoquer une
fonction mise à sa disposition, dont le résultat lui est ensuite communiqué.

Trois composants le définissent entièrement : une **invite système**, qui fixe
le rôle, les règles et le format attendu ; un **catalogue d'outils**, c'est-à-dire
un ensemble de fonctions décrites par un schéma de données ; et une **boucle
d'exécution**, qui alterne appels au modèle et exécutions d'outils jusqu'à
l'obtention d'une réponse ou l'atteinte d'une limite. Tout le reste, y compris
la mémoire et la planification, se ramène à des variantes de ces trois
composants.

### Une typologie par degré d'autonomie

Il est utile de distinguer quatre degrés, par autonomie croissante, car les
risques et les coûts changent de nature à chaque palier.

Au premier degré, l'**assistant sur invite** ne fait que transformer un texte
en un autre : résumer, reformuler, traduire, noter. Il n'accède à rien et
n'agit sur rien. Son risque est celui d'un énoncé faux ; son coût est d'un
appel.

Au deuxième degré, l'**agent à outils en lecture** peut consulter des données
de l'organisation. Son risque devient celui d'une fuite de données entre
organisations et celui d'une réponse fondée sur une lecture partielle. Son coût
est de plusieurs appels.

Au troisième degré, l'**agent à outils en écriture** modifie l'état d'un
système tiers. Le risque change de nature : une écriture erronée est une
atteinte à l'intégrité des données de production, et non plus seulement une
réponse insatisfaisante.

Au quatrième degré, le **système multi-agents** confie à plusieurs agents des
rôles distincts qui coopèrent. Les risques précédents s'y composent, et
s'y ajoutent ceux de l'orchestration : boucles improductives, propagation
d'erreurs, opacité du diagnostic.

Notre produit se situe aux deuxième et troisième degrés, délibérément. Le
quatrième est discuté plus bas et écarté.

### Boucle d'exécution et mémoire

Yao et ses collègues ont formalisé la boucle sous le nom de ReAct : le modèle
alterne un énoncé de raisonnement, une action et une observation
[@yao2023react]. Shinn et ses collègues y ont ajouté une phase de
réflexion verbale, où l'agent critique sa propre tentative précédente avant de
recommencer [@shinn2023reflexion]. Ces travaux, issus de contextes de
recherche, supposent des budgets d'essais que peu de produits peuvent offrir :
une boucle d'auto-critique multiplie le nombre d'appels au modèle, donc la
latence et le coût.

La **mémoire** d'un agent recouvre trois choses souvent confondues :
l'historique de la conversation en cours, transmis au modèle à chaque appel ;
un état persistant propre à l'utilisateur ou à l'organisation, conservé en
base de données ; et l'ensemble des données métier, qui ne sont pas une
mémoire de l'agent mais le système d'information de l'entreprise, consulté par
des outils. Confondre les deux dernières conduit à dupliquer dans un magasin
propre à l'agent des données dont le logiciel client est déjà la source de
vérité, avec les problèmes de synchronisation et de fraîcheur que cela
implique.

### La gestion de l'historique d'une conversation

Un agent conversationnel doit renvoyer au modèle, à chaque tour, l'historique
de la conversation, faute de quoi celui-ci ne sait plus de quoi il est
question. Or cet historique grossit à chaque tour, et il grossit deux fois plus
vite dans un agent à outils que dans un simple dialogue, puisqu'il contient
aussi les appels d'outils et leurs résultats. Le coût d'un tour croît donc avec
le rang du tour.

Trois stratégies existent, avec des compromis explicites. La **fenêtre
glissante** ne conserve que les derniers tours : coût borné, mais perte des
informations anciennes. Le **résumé progressif** remplace les tours anciens par
un résumé produit par le modèle : coût borné, mais introduction d'une
réécriture, donc d'une source supplémentaire d'erreur. La **rétention
sélective** ne conserve que certains éléments, typiquement les résultats
d'outils les plus récents et les messages de l'utilisateur, en écartant les
raisonnements intermédiaires.

La question importe d'autant plus qu'un résultat d'outil peut être volumineux.
Un principe simple s'impose : ce qui est conservé dans l'historique doit être
la forme condensée d'un résultat, et non sa forme brute. Le lieu naturel de
cette condensation est le même module déterministe qui applique le budget de
contexte.

## L'orchestration multi-agents et son coût

### Ce que la littérature propose

Park et ses collègues ont montré qu'une population d'agents dotés de mémoire,
de réflexion et de planification produit des comportements sociaux crédibles
dans un environnement simulé [@park2023generative]. Wu et ses collègues
proposent avec AutoGen un cadriciel où des agents conversent entre eux et avec
des humains pour résoudre une tâche [@wu2024autogen]. Hong et ses collègues,
avec MetaGPT, assignent à chaque agent un rôle d'une organisation logicielle
et encodent les procédures de travail correspondantes [@hong2024metagpt] ;
Qian et ses collègues poursuivent la même idée avec ChatDev
[@qian2024chatdev].

Ces travaux établissent la faisabilité de la coopération entre agents. Ils
n'établissent pas qu'elle soit le bon choix pour une application d'entreprise
donnée, et plusieurs de leurs évaluations portent sur des tâches de
programmation à l'énoncé fermé, assez éloignées d'un usage commercial ou de
recrutement.

### Les patrons d'orchestration et leur contrepartie

Trois patrons reviennent : la **chaîne**, où la sortie d'un agent est l'entrée
du suivant ; le **superviseur**, où un agent répartit le travail entre des
agents spécialisés et agrège leurs résultats ; le **débat**, où plusieurs
agents produisent des réponses concurrentes qu'un arbitre départage.

Chacun a la même contrepartie, sous trois formes. La latence s'additionne :
un utilisateur qui attend une réponse conversationnelle ne tolère pas la somme
de cinq appels séquentiels à un modèle. Le coût se multiplie par le nombre
d'agents et par le nombre de tours. Et le diagnostic se dégrade : quand une
réponse est mauvaise, il faut déterminer lequel des agents a fauté, sur quelle
entrée, à quel tour.

Il existe une exception importante, qui n'est pas de l'orchestration
conversationnelle : la **parallélisation d'une tâche homogène**. Noter deux
cents curriculum vitæ revient à exécuter deux cents fois la même opération
indépendante. Ce n'est pas un système multi-agents mais un traitement par lots,
et il relève d'une file de tâches asynchrone, pas d'une conversation entre
agents. Cette distinction est au cœur de notre conception.

### Position retenue : un exécutif, plusieurs définitions

Nous soutenons qu'à l'échelle d'un produit servant quelques dizaines
d'organisations, il faut un **exécutif d'agent unique**, écrit et maintenu
dans le dépôt, et autant de **définitions d'agents** que de cas d'usage. Une
définition d'agent est une donnée : une invite système versionnée, une liste
d'outils, un alias de modèle, un schéma de sortie attendu et une limite
d'étapes. L'exécutif, lui, est du code : il valide les arguments, applique la
politique de confirmation, journalise, et borne la boucle.

Trois arguments soutiennent cette position. Le premier est la maîtrise du
chemin critique : la latence, le coût et la sécurité d'un agent dépendent
entièrement de ce que fait la boucle, et une boucle écrite à la main tient en
quelques centaines de lignes lisibles en revue de code. Le deuxième est la
stabilité : les cadriciels d'agents les plus répandus, comme LangChain ou
LlamaIndex [@langchain2022 ; @llamaindex2022], connaissent un rythme de
changement d'interface incompatible avec un logiciel que l'on doit maintenir
sans équipe dédiée. Le
troisième est l'évaluabilité : pour mesurer l'effet d'un changement d'invite
ou de modèle, il faut que tout le reste soit identique, ce qui suppose de
contrôler l'exécutif.

L'argument inverse, qu'il faut reconnaître, est le coût de réimplémentation
des fonctions que ces cadriciels offrent gratuitement : intégrations toutes
faites, observabilité, gestion des reprises. Notre réponse est que le
périmètre d'outils requis ici est étroit, connu à l'avance et stable, ce qui
rend cet argument peu contraignant. Il ne le serait pas pour un produit dont le
catalogue d'outils serait ouvert.

## Alimenter le modèle : deux stratégies de récupération

### La génération augmentée par récupération

Lewis et ses collègues ont proposé d'adjoindre à un modèle génératif un
récupérateur de documents, l'ensemble étant entraîné conjointement
[@lewis2020rag]. Le terme de **génération augmentée par récupération** désigne
aujourd'hui, par extension, tout dispositif qui recherche des passages
pertinents et les insère dans l'invite avant génération. La recherche s'appuie
le plus souvent sur des **plongements** de passages, comparés par similarité
dans un espace vectoriel ; Karpukhin et ses collègues ont établi l'efficacité
de cette approche dense face à la recherche lexicale classique
[@karpukhin2020dpr]. Gao et ses collègues en proposent une synthèse
[@gao2024ragsurvey].

Ce dispositif est adapté lorsque la connaissance utile réside dans un corpus
de documents en langue naturelle : notes internes, documentation, contrats,
transcriptions. Il l'est beaucoup moins lorsque la connaissance utile réside
dans une base de données relationnelle, et ce pour quatre raisons.

La similarité vectorielle est **approximative** : elle ramène des passages
proches, sans garantie d'exhaustivité ni d'exactitude. Or la question « quelles
sont les opportunités ouvertes de ce compte » appelle une réponse exacte et
complète, pas un échantillon plausible.

L'index est **en retard** sur la source : toute donnée écrite dans le logiciel
client doit être réindexée pour devenir visible. Un commercial qui vient de
saisir un compte rendu s'attend à ce que l'assistant en tienne compte
immédiatement.

L'index est une **copie**, donc un second lieu de stockage des données d'un
client, avec les obligations de sécurité et d'isolation correspondantes. Pour
un service multi-locataire, c'est une surface de risque supplémentaire pour un
gain nul.

Enfin, le résultat est **peu explicable** : on peut citer le passage retrouvé,
mais on ne peut pas montrer la requête qui l'a produit, ni la rejouer.

### La récupération structurée

L'alternative consiste à donner au modèle non pas un corpus mais un
**catalogue de requêtes typées**, dont il choisit la ou les pertinentes et
dont le programme exécute le contenu contre la source de vérité. La
littérature sur la conversion d'une question en requête de base de données
relationnelle en est le cas d'école [@yu2018spider ; @rajkumar2022text2sql].
Dans un produit d'entreprise, on ne laisse cependant pas le modèle rédiger une
requête libre : on lui expose des fonctions paramétrées, dont le corps de
requête est écrit et testé par le développeur, et dont seuls les arguments sont
produits par le modèle, puis validés.

Cette approche a un coût propre qu'il serait malhonnête de taire. Elle suppose
que les données soient effectivement structurées et que le catalogue d'outils
couvre les questions posées : une question hors catalogue reste sans réponse,
là où une recherche vectorielle aurait au moins ramené quelque chose. Elle
demande un travail d'ingénierie par source de données, non réutilisable
ailleurs. Et elle impose de mesurer la qualité de la sélection d'outils, qui
devient la première cause d'échec du système.

Le critère de choix est donc la nature des données, non une préférence
technique : structurées, on interroge ; non structurées, on indexe. Un système
qui traiterait des transcriptions d'appels commerciaux aurait besoin des deux.

### Le budget de contexte

Quelle que soit la stratégie, ce qui est récupéré doit être mis en forme sous
contrainte. Le chapitre 1 a rappelé que la fenêtre de contexte est coûteuse et
inégalement exploitée [@liu2024lost]. Il s'ensuit qu'un système sérieux doit
décider explicitement **ce qui entre dans le contexte, dans quel ordre, et ce
qui est écarté**. Cette décision ne doit pas être confiée au modèle : elle doit
être déterministe, écrite en code, et instrumentée, faute de quoi ni le coût ni
la qualité ne sont reproductibles d'un appel à l'autre.

## L'intégration au système d'information

### Les systèmes concernés

Trois familles de logiciels de gestion sont en jeu. Un **logiciel de gestion de
la relation client** centralise les comptes, les contacts, les opportunités de
vente et les activités commerciales. Un **progiciel de gestion intégré**
couvre les processus financiers, logistiques et de production. Un **système
d'information des ressources humaines** gère les salariés, les candidatures et
les processus de recrutement. Les deux agents décrits dans ce mémoire touchent
respectivement au premier et au troisième.

### Les modes d'intégration

L'intégration peut se faire par **interface de programmation applicative**,
c'est-à-dire en appelant directement les services exposés par le logiciel
client ; par **notification sortante**, où le logiciel client signale un
événement à l'application ; par **plateforme d'intégration**, service tiers qui
assure la médiation entre systèmes ; ou par **connecteur natif** installé dans
le logiciel client. Pour un produit qui doit rester déployable sur une
infrastructure modeste, l'appel direct à l'interface de programmation est le
seul mode dont le coût d'exploitation soit nul.

### Authentification déléguée et isolation

L'intégration à un logiciel client d'entreprise repose sur le protocole
d'autorisation **OAuth 2.0**, qui permet à une organisation d'autoriser une
application tierce à agir en son nom sans lui communiquer de mot de passe,
au moyen de jetons révocables. Trois exigences en découlent pour un service
multi-locataire.

Les jetons sont des secrets **par organisation** : ils doivent être chiffrés au
repos et ne jamais transiter par le modèle de langue. Plus généralement,
l'identifiant d'organisation et les identifiants d'accès doivent provenir du
contexte authentifié de la requête, jamais d'un argument produit par le modèle,
sous peine de transformer une injection de consigne en accès transversal entre
clients.

L'accès doit être **abstrait derrière une interface**. Coupler le code métier à
un logiciel client particulier interdit d'en servir un second sans réécriture.

Enfin, les interfaces de programmation des logiciels d'entreprise imposent des
**quotas d'appels**. Un traitement par lots doit donc être régulé côté
application, sous peine de voir une organisation saturer un quota partagé et
dégrader le service des autres.

### Quotas, reprise et dégradation

Les interfaces de programmation en jeu — celle du fournisseur de modèles comme
celle du logiciel client — imposent des limites de débit et connaissent des
indisponibilités. Un produit qui les ignore fonctionne en démonstration et
échoue en exploitation. Trois dispositions y répondent.

La première est la **limitation de débit côté application**, par organisation :
c'est ce qui empêche un client lançant un lot de cinq cents documents de
consommer le quota partagé et de dégrader le service des autres. Le choix
d'attendre plutôt que de refuser un jeton de débit est discutable ; il se
justifie lorsque le travail est asynchrone et que l'attente d'un exécutant
coûte moins cher que la perte d'une unité de travail.

La deuxième est la **reprise** : toute unité de travail doit pouvoir être
réexécutée sans effet de bord, ce qui suppose l'idempotence, et tout échec doit
produire un état explicite plutôt qu'une disparition silencieuse.

La troisième est la **dégradation contrôlée** : lorsqu'un modèle est
indisponible, un repli déclaré en configuration prend le relais ; lorsqu'aucun
n'est disponible, le système doit le dire, et non produire une réponse vide ou
inventée.

### Lecture et écriture ne sont pas symétriques

Une lecture erronée produit une réponse incomplète ; une écriture erronée
corrompt les données de production d'un client. Cette asymétrie justifie un
traitement différencié : les outils de lecture peuvent être invoqués librement
par l'agent, les outils d'écriture doivent être soumis à une validation
humaine explicite avant exécution, et l'exécution doit être idempotente, c'est-à-dire produire le même effet qu'elle soit exécutée une ou plusieurs fois avec
la même clé.

## Deux cas d'usage professionnels

### La fonction commerciale

Le travail d'un commercial comporte une part importante de préparation et de
saisie : reconstituer l'historique d'un compte avant un rendez-vous,
retrouver l'état d'une opportunité, consigner un compte rendu, créer une tâche
de suivi. Ces tâches supposent de naviguer dans plusieurs écrans d'un logiciel
de gestion de la relation client, dont l'ergonomie est conçue pour la saisie
structurée et non pour la synthèse.

Un agent apporte ici deux choses distinctes. En lecture, il **condense** en une
réponse ce qui demandait plusieurs consultations ; le gain est un gain de temps
et d'exhaustivité. En écriture, il **raccourcit** le chemin entre une intention
formulée en langue naturelle et un enregistrement correctement rempli ; le gain
est un gain de qualité de la donnée, à condition que l'humain valide.

Une seconde famille d'usages relève du **conseil** plutôt que de l'accès aux
données : évaluer un compte rendu, un courriel de relance ou un argumentaire
au regard d'une grille explicite, et proposer des améliorations. Cet usage ne
requiert aucun accès au système d'information, ce qui en fait le premier
livrable raisonnable d'un produit.

La littérature économique récente sur l'effet des assistants génératifs sur la
productivité des agents de service et des travailleurs du savoir fournit des
ordres de grandeur, mais elle porte sur des contextes et des populations
éloignés des nôtres [@brynjolfsson2025genai ; @noy2023experimental ;
@dellacqua2026jagged]. Nous nous en servons comme cadrage, non comme
prédiction : aucun de ces travaux ne porte sur des petites et moyennes
entreprises d'un pays à faible revenu, et le transfert de leurs résultats à
notre contexte n'est pas établi.

### La présélection de candidatures

Une offre d'emploi diffusée en ligne peut recevoir plusieurs centaines de
candidatures, dont l'examen initial est répétitif et faiblement qualifié. Les
logiciels de suivi des candidatures automatisent depuis longtemps le filtrage
par mots-clés, avec les effets pervers connus : les candidats optimisent leur
document pour le filtre plutôt que pour le lecteur.

Un modèle de langue change la nature de l'opération : il peut lire un document
non structuré, en extraire un profil normalisé, puis évaluer ce profil contre
une grille de critères dérivée de l'offre, en justifiant chaque note par un
extrait du document. La sortie utile n'est pas une décision mais un
**classement motivé**, que le recruteur conserve la responsabilité d'examiner.

Deux questions de conception s'y posent. La première est celle de l'unité
d'évaluation : noter chaque candidature **indépendamment** contre la grille,
ou soumettre au modèle un lot de candidatures à comparer. La notation
indépendante se parallélise, permet de reprendre un échec unitaire, applique
la même grille à tous et échappe au biais de position dans une longue liste ;
la comparaison apporte en revanche un jugement relatif que la notation
indépendante rend mal, notamment pour départager des profils proches. Un
compromis consiste à noter indépendamment puis à comparer seulement les
meilleurs.

La seconde question est celle du **cadre juridique et éthique**. Le règlement
général sur la protection des données encadre les décisions fondées
exclusivement sur un traitement automatisé produisant des effets juridiques ou
significatifs [@gdpr2016]. Le règlement européen sur l'intelligence
artificielle range les systèmes destinés au recrutement et à la sélection de
candidats dans les usages à haut risque, assortis d'obligations de
documentation, de supervision humaine et de gestion des risques
[@euaiact2024]. Ces textes ne s'appliquent pas directement à un déploiement
malgache, mais ils constituent la référence de fait pour tout éditeur qui vise,
à terme, des clients établis dans l'Union européenne, et leurs exigences
recoupent celles d'un traitement responsable. Le biais démographique de tels systèmes n'est pas une crainte théorique.
Wilson et Caliskan ont mesuré, sur une tâche de présélection par récupération
fondée sur des modèles de langue, des écarts de sélection corrélés au genre et
à l'origine supposés du nom porté par le curriculum vitæ
[@wilson2024resumebias]. Armstrong et ses collègues rapportent des résultats
convergents sur des tâches de recrutement confiées à un modèle commercial
[@armstrong2024siliconceiling]. Une enquête journalistique, dont le code et
les données de réplication sont publics mais qui n'a pas fait l'objet d'une
relecture par les pairs, aboutit à un constat de même nature
[@bloomberg2024gpthiring]. Ces travaux ne condamnent pas l'usage de tels
systèmes ; ils établissent que l'absence de biais ne peut être présumée et
doit être mesurée sur le dispositif effectivement déployé. La critique plus
générale de Bender et ses collègues sur la reproduction de stéréotypes par les
modèles de langue garde ici toute sa portée [@bender2021parrots].

## Comment sait-on qu'un tel système fonctionne ?

### Les limites des jeux d'épreuves généralistes

Les jeux d'épreuves standard mesurent des connaissances et des capacités
générales [@hendrycks2021mmlu ; @srivastava2023bigbench]. Ils informent sur le
choix d'un modèle, non sur la qualité d'un produit : un modèle excellent sur
des questions à choix multiples peut échouer à sélectionner le bon outil dans
un catalogue donné, ou à respecter un schéma de sortie.

### L'évaluation par un modèle juge et ses biais

Faute de références écrites à la main en quantité suffisante, l'usage s'est
répandu de faire évaluer les sorties d'un système par un autre modèle
[@zheng2023mtbench ; @liu2023geval]. La méthode est utile mais biaisée : les
travaux cités documentent notamment une préférence pour les réponses longues,
une sensibilité à l'ordre de présentation et une indulgence envers les sorties
de modèles apparentés au juge. Elle ne peut donc servir qu'à trancher des
questions factuelles fermées, et sous contrôle d'un échantillon relu par un
humain.

### Les métriques qui décident vraiment

Pour un produit, quatre familles de mesures comptent. La **qualité de la
tâche**, exprimée dans les termes du métier : corrélation de rang avec un
classement de référence pour une présélection, rappel sur les outils
effectivement nécessaires pour un assistant. La **latence**, mesurée en
percentiles et non en moyenne, car c'est la queue de distribution qui détermine
l'abandon. Le **coût** par unité de travail, seule grandeur qui permette de
discuter d'un prix de vente. Et la **robustesse** face aux entrées hostiles ou
malformées, mesurée par des cas construits à cet effet.

### Observabilité : ce qu'il faut enregistrer

Un système fondé sur un modèle de langue échoue de façons qui ne laissent pas
de trace dans les journaux applicatifs ordinaires : la requête a réussi, le
code n'a pas levé d'exception, et la réponse est pourtant mauvaise. Diagnostiquer
suppose donc une instrumentation propre, et cette instrumentation doit être
conçue avant la mise en service, non ajoutée après le premier incident.

Trois niveaux de trace sont nécessaires et suffisants. Au niveau de l'**appel
au modèle**, on enregistre l'organisation, l'agent, l'alias employé, la version
de l'invite, le nombre de jetons d'entrée et de sortie, la latence, le statut et
le coût estimé : c'est ce qui permet de répondre aux questions de coût et de
performance. Au niveau de l'**exécution d'agent**, on enregistre la suite
ordonnée des étapes — appel au modèle, appel d'outil, résultat résumé — sous un
identifiant de trace unique : c'est ce qui permet de reconstituer pourquoi une
réponse a été produite, et c'est aussi ce que l'on peut montrer à l'utilisateur
pour qu'il juge de la fiabilité de ce qu'il lit. Au niveau de la **tâche
asynchrone**, on enregistre les transitions d'état de chaque unité de travail :
c'est ce qui permet de dire à un utilisateur où en est son lot et pourquoi un
élément a échoué.

Une règle de discrétion accompagne ces trois niveaux : les journaux applicatifs
ne doivent jamais contenir le contenu des messages échangés avec le modèle.
Les métadonnées suffisent au diagnostic, et le contenu, lorsqu'il doit être
conservé, relève d'un stockage soumis aux mêmes règles d'isolation et
d'effacement que les données métier.

## Sécurité et gouvernance

Les risques propres aux applications fondées sur des modèles de langue font
l'objet d'un recensement structuré par l'OWASP, où l'injection de consigne, la
divulgation d'informations sensibles et l'autonomie excessive accordée à un
agent figurent aux premiers rangs [@owasp2025llmtop10], et dont la première
version datait de 2023 [@owasp2023llmtop10v11]. Le NIST propose un
cadre de gestion des risques applicable aux systèmes d'intelligence artificielle
[@nist2023airmf] ainsi qu'une taxonomie des attaques adverses et de leurs
atténuations [@nist2025aml]. La norme ISO/IEC 42001 définit les exigences d'un
système de management de l'intelligence artificielle [@iso2023iec42001].

Pour un éditeur de notre taille, ces cadres ne sont pas des objectifs
de certification mais des listes de vérification. Trois principes en sont
extraits et appliqués : **moindre autorité** accordée à l'agent, toute
opération d'écriture étant confirmée ; **cloisonnement** strict des données
entre organisations, vérifié au niveau de la base de données et non seulement
du code applicatif ; **traçabilité** de chaque appel au modèle, condition de
tout audit ultérieur.

## Ce que cela implique pour notre conception

**Un exécutif d'agent unique, sans cadriciel.** Le dépôt contient une boucle
d'exécution unique, d'environ cent cinquante lignes, partagée par tous les
agents. Elle appelle le modèle, valide les arguments d'outils contre un schéma,
exécute, réinjecte les résultats, et s'arrête au plus tard après six appels ;
l'épuisement de cette limite est un état de sortie explicite, distinct d'une
erreur. Chaque agent n'est qu'une définition : invite versionnée, outils, alias
de modèle, schéma de sortie.

**Deux modèles par agent, selon l'étape.** Le premier appel, qui choisit les
outils, part sur un alias léger ; les appels de rédaction partent sur un alias
fort. Ce routage traduit dans le code l'écart de coût établi au chapitre 1.

**La récupération structurée plutôt qu'un index vectoriel** (décision ADR-008).
L'agent commercial choisit parmi des outils de lecture typés, dont un outil
composite qui regroupe en un seul aller-retour les quatre requêtes nécessaires
à la préparation d'un rendez-vous : c'est ce regroupement, et non le choix du
modèle, qui rend tenable la cible de trois secondes. Aucun index vectoriel
n'est construit ; la décision précise la condition de sa réévaluation, à savoir
l'arrivée de données non structurées comme des transcriptions d'appels.

**Un module de construction de contexte déterministe.** Le classement des
informations, leur ordre de priorité et la troncature au budget de jetons sont
écrits en code, sans appel au modèle ; le nombre de jetons utilisés et le
nombre d'éléments écartés sont retournés et journalisés. À données identiques,
le texte envoyé au modèle est identique.

**L'isolation multi-locataire est appliquée par la base de données** (décision
ADR-002). Chaque table métier porte un identifiant d'organisation et des
politiques de sécurité au niveau des lignes ; chaque transaction pose
l'organisation courante avant toute requête. Une erreur de programmation dans
le code applicatif ne suffit donc pas à faire fuir les données d'un client vers
un autre.

**L'accès au logiciel client passe par une interface abstraite** (décision
ADR-005). Les identifiants d'accès sont obtenus par autorisation déléguée,
organisation par organisation, et conservés chiffrés.

**Les écritures sont confirmées** (décision ADR-009). Un outil d'écriture
n'est jamais exécuté à l'issue de la décision du modèle : l'exécutif retourne à
l'interface une demande de confirmation portant le nom de l'outil et ses
arguments ; l'exécution n'a lieu qu'après accord explicite, et une seule fois.

**Le traitement par lots est asynchrone et régulé.** La présélection de
candidatures s'exécute sur une file de tâches dédiée aux traitements lourds,
distincte de celle des synchronisations légères, afin qu'un lot de cinq cents
candidatures n'affame jamais une écriture commerciale (décision ADR-006). Les
appels au modèle sont limités en débit par organisation.

**La notation est faite candidature par candidature** (décision ADR-007), pour
les raisons de parallélisme, de reprise unitaire et d'absence de biais de
position exposées plus haut ; une passe comparative sur les meilleurs profils
est prévue en option, là où le jugement relatif apporte quelque chose.

**L'évaluation est un livrable, pas une annexe.** Le dépôt contient un harnais
qui rejoue un jeu de données de référence contre le code de production et
produit un rapport daté, assorti de seuils qui font échouer la commande
lorsqu'ils ne sont pas tenus. Une suite est consacrée aux cas hostiles, dont
des candidatures porteuses d'une injection de consigne. Le modèle juge n'y
tranche que des présences de faits, et un échantillon de ses verdicts est relu
à la main avant que les chiffres qui en dépendent soient déclarés valides.
