# Architecture et choix technologiques

## Objet et périmètre du chapitre

Ce chapitre décrit la structure du système livré et justifie les décisions qui
lui ont donné cette forme. Il est organisé autour des enregistrements de
décision d'architecture consignés dans `docs/adr/`, onze documents courts qui
fixent, pour chaque question structurante, la décision retenue et les
alternatives écartées. Cinq d'entre eux sont traités ici dans leur intégralité,
parce qu'ils portent sur la charpente : le découpage en modules, l'isolation
entre clients, l'authentification, la passerelle vers les modèles de langue et
la nomination de ces modèles. Les six autres concernent le fonctionnement des
agents et l'intégration au système d'information du client ; ils sont traités
aux chapitres 5 et 6, là où ils s'appliquent.

La forme retenue pour restituer une décision est toujours la même : le contexte
qui rendait la question ouverte, les options réellement disponibles au moment
du choix, la décision, puis ses conséquences, y compris désagréables. Une
décision dont on ne sait pas énoncer le coût n'est pas une décision mais une
habitude.

Une précision de périmètre. Ce chapitre décrit ce qui est dans le dépôt à la
date de rédaction. Lorsque le code et les documents de cadrage divergent, c'est
le code qui est décrit, et la divergence est signalée explicitement. Trois
divergences de ce type apparaissent dans les pages qui suivent ; elles sont
mineures mais instructives, car elles montrent ce qu'une intention
d'architecture devient une fois confrontée à l'exécution.

## Vue d'ensemble du système livré

Miara est une plateforme applicative multi-locataire qui offre à une
organisation cliente deux agents : un assistant pour ses commerciaux, adossé à
son logiciel de gestion de la relation client, et un agent de présélection de
candidatures pour son équipe de recrutement. Le système se compose d'une
interface web, d'une interface de programmation, de deux exécutants de tâches
de fond, et de trois services d'infrastructure. La figure \ref{fig:macro} en
donne la vue d'ensemble.

![Architecture macroscopique du système. Les ports 3010 et 8010 sont fixes, en développement comme en production ; seul le serveur frontal est exposé sur le réseau.\label{fig:macro}](figures/out/architecture-macro.pdf){width=95%}

Le navigateur ne parle qu'à un seul processus, le serveur frontal `nginx`, qui
termine la connexion chiffrée et répartit : ce qui commence par `/api/` va vers
l'interface de programmation, le reste vers le serveur Next.js. Cette
répartition est doublée côté développement par une réécriture interne au
serveur Next.js, de sorte que dans les deux environnements le navigateur
n'émette de requêtes que vers une seule origine. Ce point, qui paraît
anecdotique, supprime en pratique toute la classe de problèmes liés au partage
de ressources entre origines et permet de tester l'application depuis une
machine distante par un simple tunnel chiffré, sans ouvrir de port.

Les deux ports applicatifs, 3010 pour l'interface et 8010 pour l'interface de
programmation, sont fixés une fois pour toutes et identiques en développement,
en test et en production. La contrepartie est assumée : deux instances de
l'application ne peuvent pas coexister sur une même machine. En échange, aucune
configuration ne dépend de l'environnement, ce qui élimine une source
récurrente d'écarts entre ce que l'on teste et ce que l'on exploite. On notera
que la carte de cadrage initiale mentionnait les ports 8000 et 3000 : l'écart
est documenté dans le dépôt, à la fois dans les consignes du projet et dans le
fichier de configuration du serveur frontal.

La figure \ref{fig:tdb} donne à voir le résultat, du point de vue d'un
utilisateur de l'organisation de démonstration. Elle est reproduite ici non
pour ses chiffres, dont l'examen appartient au chapitre 8, mais parce qu'elle
matérialise ce que l'assemblage décrit plus haut produit effectivement : une
application unique où les deux agents coexistent sous la même
authentification et la même organisation active.

![Tableau de bord de l'organisation active, capture du 22 septembre 2026 sur la révision `d793943`. Le gain de temps affiché repose sur une hypothèse de configuration discutée plus loin, non sur une mesure.\label{fig:tdb}](figures/captures/out/ecran-tableau-de-bord.png){width=92%}

## Un monolithe modulaire plutôt que des services distribués

### La décision ADR-001

**Contexte.** Le système comporte des domaines fonctionnels nettement
distincts : la gestion des comptes et des organisations, la présélection de
candidatures, l'assistance commerciale, et un socle technique commun. La
tentation d'en faire autant de services déployables séparément est forte, parce
que le découpage fonctionnel est net et que le traitement par lots de
candidatures a un profil de charge très différent de celui d'une conversation.

**Options.** Trois options étaient ouvertes. Des services indépendants, chacun
avec sa base et son cycle de déploiement, offrent l'isolation des pannes et la
montée en charge sélective, au prix d'une infrastructure de communication, de
découverte et d'observabilité. Un monolithe sans discipline interne minimise le
coût d'exploitation mais produit, à six mois, un enchevêtrement que plus
personne ne peut découper. Un monolithe modulaire, enfin, conserve le
déploiement unique mais impose des frontières explicites entre modules, avec un
sens de dépendance déclaré.

**Décision.** Le système est un monolithe modulaire. Le code applicatif se
répartit en quatre paquets sous `backend/app/` : `auth` pour les utilisateurs,
organisations et rôles, `hr` pour la présélection, `sales` pour l'assistance
commerciale, et `core` pour le socle technique, qui contient le moteur
d'exécution des agents, la passerelle vers les modèles, la gestion de session
de base de données, la journalisation et les sondes de santé. La règle de
dépendance est asymétrique : les modules métier peuvent s'appuyer sur `core`,
`core` ne connaît aucun module métier. L'argument est prosaïque et il est bon
qu'il le soit : un développeur, six mois, et une exploitation qui doit tenir
sur un seul serveur.

**Conséquences.** La discipline de frontières ne se maintient pas toute seule.
Elle est vérifiable, et elle est vérifiée : la figure \ref{fig:deps} est
produite par analyse syntaxique de toutes les importations du dossier
`backend/app/`, et non dessinée.

![Dépendances entre paquets du backend, obtenues par analyse des importations. L'étiquette d'une flèche est le nombre de fichiers du paquet source qui importent le paquet cible.\label{fig:deps}](figures/out/dependances-modules.pdf){width=85%}

Cette figure établit deux choses. La première est que la règle principale est
tenue : aucune flèche ne part de `core` vers `auth`, `hr` ou `sales`. La
seconde est plus intéressante, car elle n'était pas prévue par les documents de
cadrage : `hr` et `sales` importent `auth`, respectivement dans deux et quatre
fichiers. L'inspection des importations montre qu'il s'agit à chaque fois de la
dépendance fonctionnelle `require_role`, qui vérifie qu'un appelant possède
bien, dans l'organisation active, un rôle autorisé. Ce n'est donc pas un
couplage métier mais une dépendance à un service transverse logé dans le
mauvais paquet. La décomposition de Parnas suggérait déjà qu'un module se
définit par le secret qu'il cache et non par l'étape de traitement qu'il
exécute [@parnas1972criteria] : la vérification de rôle n'a rien à faire dans
le module qui gère l'inscription des utilisateurs, et devrait à terme migrer
vers `core`. Le dépôt vit aujourd'hui avec cette imperfection, qui est
documentée ici plutôt que dissimulée.

Un second point mérite d'être relevé. Six fichiers vivent directement sous
`backend/app/`, en dehors des quatre paquets : le point d'entrée de
l'application, le registre des modèles de données, l'enregistrement des tâches
de fond, et trois routeurs transverses qui exposent le tableau de bord, la file
de traitement et la consommation de modèles. Ce sont des points de composition,
c'est-à-dire les seuls endroits où les modules ont le droit de se rencontrer.
Les isoler dans un espace nommé est un choix : il rend visible, dans le graphe,
l'endroit exact où la règle de dépendance est volontairement suspendue.

## L'isolation entre clients, garantie par la base de données

### La décision ADR-002

**Contexte.** La plateforme héberge plusieurs organisations sur la même
installation. Une fuite de données d'une organisation vers une autre n'est pas
un défaut parmi d'autres : c'est le défaut qui termine le produit. La question
n'est donc pas seulement d'éviter l'erreur, mais de choisir l'endroit où
l'erreur sera rattrapée.

**Options.** Filtrer par identifiant d'organisation dans le code applicatif est
l'option la plus simple et la plus fragile : elle suppose qu'aucune requête,
jamais, n'oubliera sa clause de restriction. Un schéma de base par organisation
isole mieux mais transforme chaque migration en boucle sur des dizaines de
schémas. Une base par organisation isole parfaitement et coûte, pour dix
clients sur un seul serveur, un prix sans rapport avec le bénéfice.

**Décision.** Base unique, schéma unique, colonne `organization_id` sur toute
table métier, et politiques de sécurité au niveau des lignes appliquées par
PostgreSQL. Chaque transaction pose l'organisation courante avant toute requête
métier ; le serveur de base de données refuse alors de restituer les lignes des
autres organisations, que la requête ait pensé ou non à les exclure. Deux rôles
PostgreSQL distincts matérialisent la séparation : le rôle d'exécution, soumis
aux politiques, et le rôle de migration, qui les contourne. L'application
utilise le premier, le gestionnaire de migrations le second.

La politique elle-même tient en une expression, reproduite ici parce que sa
forme exacte porte une décision de sûreté :

```sql
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidates FORCE  ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_candidates ON candidates
  USING (organization_id
         = NULLIF(current_setting('app.current_org', true), '')::uuid);
```

Le mot-clé `FORCE` étend la politique au propriétaire de la table, qui en
serait sinon exempté. Le troisième argument de `current_setting` demande de
renvoyer une valeur vide plutôt que de lever une erreur lorsque le réglage
n'existe pas, et `NULLIF` transforme cette valeur vide en absence de valeur. La
comparaison vaut alors l'indéterminé, et aucune ligne n'est visible. Le
comportement par défaut, en cas d'oubli du réglage, est donc de ne rien
montrer ; c'est l'inverse d'un filtre applicatif oublié, qui montre tout.

La pose du contexte est centralisée dans une unique fonction de `core`, qui
ouvre une session, démarre une transaction, appelle `set_config` pour
l'organisation puis, le cas échéant, pour l'utilisateur, et cède la main. La
forme transactionnelle de `set_config`, avec son troisième argument à vrai,
équivaut à `SET LOCAL` : les réglages disparaissent avec la transaction, et ne
peuvent donc pas fuir vers la requête suivante servie par la même connexion du
réservoir. Le second réglage, l'utilisateur courant, n'est pas décoratif : il
sert la politique qui autorise un utilisateur à lire ses propres appartenances
avant même qu'une organisation active n'existe, c'est-à-dire au moment de la
connexion.

**Conséquences.** Le coût est réel. Toute écriture qui contourne la fonction de
session, par exemple dans un script d'administration, doit utiliser le rôle de
migration et perd donc la protection. La table `users` n'est pas rattachée à
une organisation, puisqu'un même utilisateur peut appartenir à plusieurs
organisations : elle échappe par construction au mécanisme, et sa protection
repose sur le fait qu'elle n'est jamais lue autrement que par identifiant.
Enfin, les politiques doivent être écrites à la main dans chaque migration, le
générateur automatique ne les produisant pas ; c'est une ligne de plus à ne pas
oublier à chaque nouvelle table, et la revue de code est le seul garde-fou.

La pratique adoptée dans le dépôt atténue ce risque sans l'annuler. Chacune des
migrations qui introduit une table métier active la sécurité au niveau des
lignes, la force pour le propriétaire de la table, crée la politique
d'isolation et attribue les privilèges dans la même unité de migration, de
sorte qu'il n'existe pas d'état intermédiaire du schéma où la table existerait
sans sa politique. Sept des onze migrations du dépôt contiennent ainsi une
déclaration de politique. Les privilèges eux-mêmes sont attribués au plus
juste : le journal des écritures vers le logiciel client ne reçoit que le droit
de lecture et d'insertion, parce qu'une piste d'audit qui peut être modifiée ou
effacée par le compte applicatif n'est plus une piste d'audit. La protection
repose donc sur deux barrières distinctes, la politique qui filtre les lignes
visibles et le privilège qui borne les opérations permises, et la seconde reste
en vigueur même si la première venait à être mal écrite.

### Le modèle de données socle

La figure \ref{fig:socle} présente les quatre tables du socle. Elle est
produite à partir des métadonnées de l'outil de correspondance
objet-relationnel, c'est-à-dire des classes réellement déclarées dans le code,
et les types y sont compilés pour le dialecte PostgreSQL : ce sont donc les
types que les migrations créent, et non une approximation.

![Modèle de données du socle multi-locataire, dérivé des classes SQLAlchemy. Les politiques de sécurité au niveau des lignes portent sur `memberships` et `integrations`.\label{fig:socle}](figures/out/schema-socle.pdf){width=80%}

Trois observations. D'abord, `memberships` n'a pas de clé primaire technique :
sa clé est le couple formé de l'utilisateur et de l'organisation, ce qui
interdit par construction deux rôles contradictoires pour une même personne
dans une même organisation. Ensuite, `integrations` stocke les identifiants
d'accès au logiciel client sous forme d'un bloc binaire chiffré, jamais en
clair, point sur lequel le chapitre 6 revient. Enfin, `organizations` et
`users` ne portent pas de politique d'isolation, pour la raison indiquée plus
haut ; ce sont les deux seules tables du système dans ce cas.

Le modèle complet compte quinze tables. Les onze autres relèvent des agents et
de leur exploitation et sont présentées au fil des chapitres 5 et 6, avec les
mécanismes qu'elles servent.

## Authentification et rôles

### La décision ADR-003

**Contexte.** Le système doit authentifier des personnes qui peuvent appartenir
à plusieurs organisations et y détenir des rôles différents. L'autorisation ne
peut donc pas être une propriété de l'utilisateur : elle est une propriété du
couple utilisateur-organisation.

**Options.** Déléguer l'authentification à une bibliothèque du monde JavaScript
intégrée au cadriciel d'interface, ou à un serveur d'identité dédié, évite
d'écrire du code sensible. Les deux options se heurtent au même obstacle :
aucune ne modélise nativement l'appartenance multiple avec rôle par
organisation, qui est précisément le cœur du problème, et toutes deux déplacent
la source de vérité hors de la base où vivent les politiques d'isolation.

**Décision.** L'interface de programmation émet elle-même ses jetons. Un jeton
d'accès signé, de durée de vie courte, porte l'identifiant de l'utilisateur,
celui de l'organisation active et le rôle. Un jeton de rafraîchissement opaque,
tiré aléatoirement et stocké côté serveur avec une durée de vie longue, permet
de renouveler le premier ; sa consommation est atomique, ce qui le rend
utilisable une seule fois. Les mots de passe sont hachés avec une fonction
conçue pour résister au calcul parallèle spécialisé [@biryukov2016argon2]. Les
deux jetons voyagent dans des cookies inaccessibles au script de la page, celui
de rafraîchissement étant restreint au chemin des routes d'authentification.

Cette restriction de chemin a une conséquence que la décision n'avait pas
anticipée, et qui n'est apparue qu'en manipulant une session expirée : le
navigateur n'envoie le jeton de rafraîchissement qu'aux routes
d'authentification, si bien qu'un rendu serveur d'une page applicative ne le
reçoit jamais et ne peut pas renouveler la session lui-même. Tant que la garde
de navigation, qui ne lit que la présence du cookie d'accès, renvoyait les
pages publiques vers l'accueil pendant que le rendu serveur renvoyait l'accueil
vers la connexion, un jeton expiré produisait une boucle de redirections et non
un écran de connexion. La séparation des responsabilités est désormais
explicite : le serveur constate le refus et délègue à une page cliente, seule à
pouvoir déclencher la rotation ou, à défaut, l'effacement des cookies. C'est un
exemple net de propriété qui ne se déduit d'aucun des deux composants pris
isolément, chacun étant correct de son côté.

Une précision qui n'est pas un détail : le rôle inscrit dans le jeton est
traité comme une information d'affichage. À chaque requête, la dépendance qui
construit le contexte relit l'appartenance dans la base, à l'intérieur de la
transaction où le contexte d'organisation vient d'être posé. Un rôle révoqué
cesse donc d'agir au moment de la révocation et non à l'expiration du jeton.

**Conséquences.** Écrire soi-même l'émission de jetons expose à des erreurs
classiques, que le code traite explicitement : limitation du nombre de
tentatives de connexion par couple adresse-origine, égalisation du temps de
réponse lorsque l'adresse est inconnue afin de ne pas révéler l'existence d'un
compte, et refus de modifier son propre rôle ou de retirer le dernier
propriétaire d'une organisation. En contrepartie, le système ne dépend d'aucun
service d'identité externe et la vérification d'autorisation partage la
transaction des requêtes métier.

La figure \ref{fig:auth} retrace le trajet complet d'une requête authentifiée,
depuis le cookie jusqu'à la politique d'isolation.

![Trajet d'une requête authentifiée et pose du contexte d'organisation. Le rôle porté par le jeton n'est jamais cru : l'appartenance est relue en base dans la même transaction.\label{fig:auth}](figures/out/flux-auth-rls.pdf){width=90%}

Les routes d'authentification et d'administration des organisations sont
regroupées sous un préfixe unique de version. L'inscription et la connexion
sont publiques ; la création d'organisation, le basculement d'organisation
active et la lecture de ses propres appartenances demandent seulement un jeton
valide ; l'invitation d'un membre et la modification d'un rôle exigent le rôle
de propriétaire ou d'administrateur, et refusent d'opérer sur une organisation
autre que l'organisation active. Cette dernière règle ferme une faille discrète
mais réelle : sans elle, un administrateur d'une organisation pourrait agir sur
une autre en changeant un identifiant dans l'adresse.

![Écran de connexion, capture du 22 septembre 2026. Les jetons ne transitent jamais par le stockage local du navigateur : ils sont posés en cookies inaccessibles au script.\label{fig:connexion}](figures/captures/out/ecran-connexion.png){width=85%}

## La passerelle vers les modèles de langue

### La décision ADR-004

**Contexte.** Le système appelle des modèles de langue depuis plusieurs
endroits : l'agent commercial, l'agent de coaching, l'extraction de profils, la
notation de candidatures. Ces appels doivent être facturés, tracés, et
survivre à l'indisponibilité d'un fournisseur.

**Options.** Appeler directement l'interface de chaque fournisseur donne le
contrôle le plus fin et multiplie le code spécifique. Déployer un serveur
mandataire dédié, qui centralise le routage et la mesure, est la solution
propre à grande échelle ; elle ajoute ici un service à installer, surveiller et
redémarrer sur un serveur qui n'utilise pas de conteneurs. Intégrer une
bibliothèque de routage dans le processus applicatif offre la centralisation
sans le service supplémentaire.

**Décision.** Une passerelle unique, dans `core`, enveloppe un routeur en
processus. Aucun autre module du dépôt n'a le droit d'importer la bibliothèque
sous-jacente ; la règle est écrite dans le fichier d'exportation du paquet. La
passerelle expose une seule opération de complétion, qui prend un alias, une
suite de messages, un contexte d'appel, éventuellement une liste d'outils et
éventuellement un schéma de sortie attendu. Elle mesure la latence, lit la
consommation de jetons et le coût dans la réponse du fournisseur, et écrit une
ligne dans la table de traçage.

**Conséquences.** Cette écriture est délibérément détachée du chemin de
réponse : elle est planifiée comme une tâche concurrente, et son échec est
journalisé sans interrompre l'appel. Un incident de base de données ne prive
donc pas l'utilisateur de sa réponse, mais il crée un trou dans la
comptabilité. Le compromis a été retenu en connaissance de cause ; il implique
que les chiffres de coût du chapitre 8 soient toujours accompagnés du nombre
d'appels effectivement journalisés. Une méthode de vidange permet d'attendre
les écritures en attente, ce dont les tests et les scripts de mesure se
servent.

### La décision ADR-011

**Contexte.** Un nom de modèle est une dépendance de fournisseur déguisée en
constante. Écrit dans le code, il rend une expérience non reproductible et un
changement de fournisseur impossible sans modification du code.

**Options.** Nommer les modèles dans le code, les nommer dans des variables
d'environnement, ou les nommer dans un fichier de configuration versionné et ne
manipuler dans le code que des alias fonctionnels.

**Décision.** Le code ne connaît que des alias, nommés d'après la tâche et non
d'après le modèle : `sales.route` pour le choix d'outils, `sales.synthesize`
pour la rédaction du briefing, `hr.extract` pour la structuration de documents,
`hr.score` pour la notation. Un unique fichier de configuration associe à
chaque alias un modèle principal et une liste de replis. La passerelle refuse
un alias absent de ce fichier avec une erreur dédiée, plutôt que de tenter un
appel qui échouerait plus loin et plus obscurément.

![Carte des alias de modèles, produite à partir du fichier de configuration. C'est le seul endroit du dépôt où un nom de modèle apparaît.\label{fig:alias}](figures/out/alias-modeles.pdf){width=95%}

La figure \ref{fig:alias} est engendrée à partir de ce fichier. Elle fait
apparaître deux alias que les documents de cadrage ne mentionnaient pas :
`hr.calibrate`, qui sert la passe comparative optionnelle discutée au
chapitre 5, et `eval.judge`, réservé au modèle juge du harnais d'évaluation. Ce
dernier est délibérément distinct des alias métier, pour une raison qui relève
de la méthode expérimentale : si le juge changeait de modèle parce qu'un agent
a changé du sien, deux rapports d'évaluation cesseraient d'être comparables. Le
harnais lui-même relève de la partie 3 et n'est pas décrit ici.

**Conséquences.** Le mécanisme de repli tel qu'il est implémenté mérite d'être
décrit avec exactitude, car il ne correspond pas tout à fait à ce que le nom
suggère. Chaque alias donne lieu à une entrée de modèle portant son nom, et
chaque repli à une entrée supplémentaire portant un nom dérivé ; la liste de
replis du routeur associe ensuite le premier aux seconds. Les réessais de
transport, au nombre de deux par défaut, s'appliquent avant la bascule. Cette
organisation fonctionne, mais elle signifie qu'un même modèle physique peut
apparaître sous plusieurs entrées ; c'est sans conséquence fonctionnelle et
utile à savoir en lisant les journaux.

## Ce que le chapitre ne traite pas et pourquoi

Deux décisions structurantes sont annoncées ici et traitées au chapitre 6,
parce que leur exposé n'a de sens qu'avec le mécanisme qu'elles servent. La
connexion au logiciel de gestion commerciale, organisation par organisation,
derrière une interface abstraite, est la décision ADR-005 ; elle commande la
forme des outils de l'agent commercial et la manière dont les identifiants
d'accès sont chiffrés. Le choix du courtier de messages et des files
d'exécution est la décision ADR-006 ; il commande la forme de la chaîne de
présélection. Les décisions ADR-007, ADR-008, ADR-009 et ADR-010 portent
respectivement sur la notation candidature par candidature, la récupération
contextuelle sans index vectoriel, la validation humaine des écritures et le
versionnement des prompts : les trois premières sont traitées aux chapitres 5
et 6, la quatrième au chapitre 5.

## Le reste de la pile technique

Les choix qui suivent n'ont pas fait l'objet d'un enregistrement de décision,
parce qu'ils n'étaient pas structurants au sens où leur révision n'entraînerait
pas la réécriture du système. Ils méritent néanmoins d'être énoncés, car ils
conditionnent la lecture du code.

Le serveur applicatif est écrit en Python 3.12 avec le cadriciel FastAPI. Le
choix tient à trois propriétés : la validation des données par annotations de
types, qui sert aussi bien les corps de requêtes que les arguments d'outils
soumis au modèle de langue ; la génération automatique d'une description
d'interface, dont le frontal tire ses types ; et l'exécution asynchrone, qui
importe parce que l'essentiel du temps du serveur est passé à attendre des
services distants. L'accès à la base passe par SQLAlchemy en mode asynchrone,
avec des migrations gérées par Alembic. Les dépendances Python sont résolues et
figées par `uv`, dont le fichier de verrouillage est versionné : le serveur de
production installe exactement les versions testées, sans résolution au
démarrage.

L'interface web est une application Next.js en TypeScript strict. La
navigation et les droits par section sont déclarés dans un tableau unique, qui
sert à la fois à construire les onglets visibles et à garder les segments côté
serveur ; un onglet masqué est donc, par construction, un segment interdit, et
non un onglet masqué devant une page accessible.

Enfin, l'infrastructure est native. PostgreSQL, RabbitMQ et Redis sont
installés comme paquets du système d'exploitation, sans conteneurs. Ce choix
est daté et réversible : il économise, pour un seul serveur et un seul
développeur, la mise en place d'une chaîne d'images et d'orchestration, au prix
d'une reproductibilité moindre de l'environnement. Le script de provisionnement
et les fichiers de service compensent partiellement ce prix en rendant
l'installation rejouable.

## Configuration, secrets et observabilité

Un système multi-locataire dont les choix structurants tiennent dans des
réglages plutôt que dans du code impose de traiter la configuration comme une
surface de conception à part entière. Le dépôt la concentre en un objet unique,
construit par `pydantic-settings` à partir de l'environnement et d'un fichier
`.env` non versionné, et exposé comme singleton. La règle associée est
énoncée dans le module lui-même : aucune lecture directe de l'environnement
ailleurs, ni dans un routeur, ni dans un service. Elle a une conséquence
pratique appréciable, celle de rendre l'inventaire des paramètres lisible d'un
seul fichier, et une conséquence méthodologique plus intéressante, celle de
rendre visibles les valeurs qui encodent une hypothèse.

Car ces réglages ne sont pas homogènes. Certains sont des adresses de services
et des clés, dont la seule propriété notable est d'être vides par défaut, de
sorte qu'un démarrage sans fichier de secrets échoue à l'endroit où il doit
échouer plutôt que de fonctionner avec une valeur de confort. Deux chaînes de
connexion distinctes coexistent, l'une pour le rôle d'exécution soumis aux
politiques de sécurité au niveau des lignes, l'autre pour le rôle de migration
qui les contourne : la séparation étudiée plus haut n'est pas seulement une
propriété de la base, elle est matérialisée dans la configuration, et un service
qui se tromperait de rôle le ferait de façon visible.

D'autres réglages, en revanche, sont des paramètres de conception déguisés en
variables d'environnement. Le budget de jetons du contexte structuré injecté à
l'agent commercial, la cadence maximale d'appels au modèle par organisation, le
nombre de candidatures traitées de front, la durée de validité des jetons
d'accès et le seuil de limitation des tentatives de connexion appartiennent à
cette catégorie : leur valeur est un compromis, et le fait qu'ils soient
paramétrables signifie que le compromis peut être déplacé sans recompiler ni
redéployer le code. Le cas le plus net est la durée de tri manuel d'une
candidature qui sert de référence au gain affiché sur le tableau de bord. Le
commentaire qui l'accompagne dans le code la qualifie explicitement
d'hypothèse de l'organisation et non de mesure, précisément pour qu'elle puisse
être contestée sans toucher au code. Cette précaution prendra tout son sens
dans la partie 3, où l'écart entre une hypothèse paramétrée et une mesure
observée est l'objet même de la discussion.

Un dernier groupe mérite d'être signalé parce qu'il documente une option
étudiée puis écartée. La passe de calibration comparative des meilleures
candidatures, envisagée lors de la décision sur la présélection, est présente
dans le code mais désactivée par un paramètre valant zéro. Le système livré ne
l'exécute donc pas, tout en conservant le chemin qui permettrait de l'activer
pour une expérience. Décrire ce paramètre comme actif serait inexact ; passer
la mécanique sous silence le serait tout autant.

L'observabilité suit la même logique de minimalisme assumé. La journalisation
est structurée au format JSON et chaque requête reçoit un identifiant, repris
de l'en-tête entrant lorsqu'il existe et engendré sinon, lié au contexte de
journalisation pour toute la durée du traitement puis renvoyé dans la réponse.
Une seule ligne est émise par requête, portant la méthode, le chemin, le code
de statut et la durée en millisecondes. Ce dispositif est délibérément pauvre
au regard de ce qu'offrirait une chaîne de télémétrie complète, mais il suffit
à corréler une trace d'agent, un appel de modèle et une requête entrante, ce
qui est la seule corrélation dont la partie 3 aura besoin.

La sonde de disponibilité obéit à une contrainte voisine. Elle interroge les
trois dépendances d'infrastructure, la base par une requête triviale, le
courtier de messages par une ouverture de connexion bornée dans le temps et le
cache par une commande de vivacité, et ne répond favorablement que si les trois
répondent. Aucun de ces contrôles ne laisse échapper d'exception : la sonde
rapporte un état, elle ne le provoque pas. Le contrôle du courtier, dont la
bibliothèque est synchrone, est déporté dans un fil d'exécution afin de ne pas
bloquer la boucle événementielle du serveur, détail d'implémentation qui
illustre le genre de précaution qu'impose un serveur asynchrone dont la
disponibilité est elle-même interrogée sous charge.

Une dernière convention, mineure en apparence, s'est révélée structurante à
l'usage : les ports d'écoute sont fixes, en développement comme en production,
le serveur applicatif sur un port et l'interface web sur un autre, le navigateur
ne s'adressant jamais qu'à cette dernière. Les documents de cadrage initiaux
mentionnaient les ports par défaut des deux cadriciels ; le code livré, la
configuration du serveur frontal et les scripts de déploiement utilisent les
ports décalés, et l'écart est assumé et documenté à l'endroit où il se
constate. Cette uniformité entre environnements est ce qui rend les captures
d'écran de ce mémoire et les mesures de la partie 3 comparables à ce qui tourne
effectivement sur le serveur.

## Déploiement

Le système est exploité sur un serveur privé virtuel sous Ubuntu, avec quatre
unités de service supervisées par `systemd`, décrites par la
figure \ref{fig:deploiement}.

![Topologie de déploiement. Un seul déployable, quatre processus, un seul fichier de secrets.\label{fig:deploiement}](figures/out/deploiement-systemd.pdf){width=95%}

L'interface de programmation et l'interface web n'écoutent que sur l'adresse de
bouclage ; le serveur frontal est le seul processus joignable depuis le réseau.
Les secrets vivent dans un unique fichier lisible par le seul groupe du compte
de service. Les unités ne lancent pas le gestionnaire de dépendances mais
directement les exécutables de l'environnement virtuel : au démarrage d'un
service, on ne veut ni résolution de dépendances ni accès au réseau. C'est le
script de déploiement qui synchronise l'environnement, applique les migrations,
construit l'interface et redémarre les unités, dans cet ordre.

Deux réglages méritent d'être relevés parce qu'ils encodent une contrainte
mesurée plutôt qu'une valeur par défaut. Le délai de redémarrage de l'interface
de programmation est fixé à deux secondes et non cinq, parce que l'importation
des bibliothèques prend déjà plusieurs secondes et que le critère retenu était
un retour en service sous dix secondes ; la valeur par défaut ne le tenait pas.
Les exécutants de tâches de fond acquittent tardivement les messages et
reçoivent un délai d'arrêt long, trois cents secondes pour la file lourde :
interrompre un traitement en cours ferait repartir le message en file et
paierait une seconde fois l'appel au modèle. Les tâches sont idempotentes, mais
elles ne sont pas gratuites.

Le serveur frontal porte trois réglages non triviaux. La taille maximale de
corps de requête est alignée sur la borne applicative du dépôt de candidatures,
de sorte qu'un envoi trop volumineux soit refusé avant que l'interface de
programmation n'ait commencé à le lire. La compression est faite là et
seulement là, le serveur Next.js ayant été configuré pour ne pas compresser,
parce qu'il compressait aussi le flux d'événements de l'agent et retardait
l'affichage de la trace jusqu'à la fin du tour. Les routes de flux, enfin,
reçoivent une configuration distincte qui désactive la mise en tampon et allonge
les délais d'attente. Le certificat est obtenu et renouvelé automatiquement, un
crochet de renouvellement rechargeant le serveur frontal.

La sauvegarde est quotidienne, par tâche planifiée, avec un script de
restauration versionné à côté du script de sauvegarde. La rétention des
journaux est bornée à la fois côté journal système et par rotation des fichiers
sur disque.

## Ce que cela implique pour l'évaluation

Trois propriétés établies dans ce chapitre conditionnent ce qui pourra être
mesuré dans la partie 3. L'isolation par la base rend l'étanchéité entre
organisations testable par une requête plutôt que par relecture du code : il
suffit de poser une organisation et de vérifier qu'une ligne d'une autre est
invisible. La traçabilité de chaque appel de modèle, avec son alias, sa version
de prompt, ses jetons et son coût, rend possible une mesure du coût par
organisation et par agent sans instrumentation supplémentaire, sous la réserve
formulée plus haut sur les écritures détachées. Enfin, l'absence de tout nom de
modèle dans le code rend possible un balayage coût-qualité par alias : changer
de modèle pour une expérience est une modification de configuration, que l'on
peut donc versionner et associer au rapport de mesure correspondant.
