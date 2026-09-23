# Intégration au logiciel client et chaîne de traitement asynchrone

## Objet et périmètre du chapitre

Les deux chapitres précédents ont décrit un système qui calcule. Celui-ci
décrit ce qui le relie au monde : au système d'information de l'organisation
cliente d'une part, au temps d'autre part. Trois enregistrements de décision y
sont traités : la connexion au logiciel de gestion de la relation client
organisation par organisation derrière une interface abstraite, la validation
humaine de toute écriture, et le choix de la chaîne de traitement asynchrone.

Ces trois décisions ont un point commun qui justifie de les réunir. Elles
portent toutes sur des actions dont l'effet sort du système : une écriture dans
le logiciel du client, un fichier déposé, un appel facturé. Une action qui sort
du système ne peut pas être annulée par une transaction. Tout ce chapitre
tourne donc autour d'une seule question : comment faire pour qu'une action
irréversible ne soit pas exécutée deux fois, ni exécutée sans accord.

## Connecter le logiciel du client, organisation par organisation

### La décision ADR-005

**Contexte.** Chaque organisation cliente possède sa propre instance de
logiciel de gestion de la relation client, avec ses identifiants, ses champs et
ses règles. La plateforme doit y accéder au nom de chaque organisation, sans
jamais confondre deux instances, et sans détenir de mot de passe.

**Options.** La première option, la plus directe, consiste à stocker des
identifiants techniques et à écrire le client d'accès dans le code des outils.
Elle est rapide et elle enferme : les outils deviennent inséparables du
fournisseur, et les tests exigent un accès réseau à une instance réelle. La
seconde consiste à faire autoriser la plateforme par chaque organisation selon
le protocole d'autorisation déléguée [@rfc6749], et à placer le client derrière
une interface que le reste du système est seul à connaître.

**Décision.** La seconde option. Un administrateur d'organisation autorise la
plateforme depuis l'interface ; les jetons obtenus sont chiffrés et stockés
dans la table des intégrations, une ligne par organisation. Le reste du système
ne connaît qu'un contrat à cinq opérations : interroger, lire un
enregistrement, créer, mettre à jour, fermer. Une fabrique fournit
l'implémentation adéquate à partir du contexte de requête.

**Conséquences.** Le contrat contraint ce que les outils peuvent demander, ce
qui est précisément l'effet recherché : aucun outil ne peut inventer un appel
exotique au fournisseur sans passer par l'une des cinq opérations. Une seconde
implémentation du même contrat, entièrement en mémoire et dotée d'un analyseur
minimal du langage de requête, permet d'exécuter les tests et le mode de
démonstration sans accès réseau. Le prix est un analyseur à maintenir, qui ne
couvre qu'un sous-ensemble du langage réel ; la contrepartie est qu'une suite
de tests complète s'exécute en quelques secondes et hors ligne.

### Le déroulement de l'autorisation

La figure \ref{fig:oauth} détaille l'échange. Trois éléments y méritent un
commentaire, car ils correspondent à des choix de sécurité explicites.

![Autorisation d'accès au logiciel client, par organisation. Le paramètre d'état est un jeton signé ; le vérificateur ne quitte jamais le serveur.\label{fig:oauth}](figures/out/oauth-salesforce.pdf){width=95%}

Le premier est l'emploi de la variante avec preuve de possession du code
[@rfc7636]. Un secret aléatoire est tiré au début de l'échange, son empreinte
est transmise au fournisseur, et le secret lui-même est conservé côté serveur,
dans le cache, avec une durée de vie de dix minutes. L'échange final du code
contre des jetons exige de présenter le secret ; un code intercepté ne suffit
donc pas.

Le deuxième est la forme du paramètre d'état. Plutôt qu'une valeur aléatoire
associée à une session, c'est un jeton signé portant l'organisation,
l'utilisateur, un identifiant unique et une date d'expiration. La conséquence
pratique est que la route de retour, qui est nécessairement publique puisque
c'est le fournisseur qui y renvoie le navigateur, n'a pas besoin d'être
authentifiée pour savoir de manière sûre pour quelle organisation elle
travaille : l'information est dans la signature.

Le troisième est la consommation atomique du secret. La lecture et la
suppression se font en une seule opération du cache ; un second passage sur la
même route de retour ne trouve plus rien et échoue proprement.

Les jetons obtenus sont sérialisés puis chiffrés par une méthode symétrique
authentifiée, avec une clé unique de l'installation, et rangés dans une colonne
binaire. Ils ne sont jamais journalisés. Le refus d'enregistrer une intégration
qui ne fournirait pas de jeton de renouvellement est explicite : sans lui,
l'accès expirerait sans possibilité de le prolonger, et le défaut ne se
manifesterait qu'au premier appel après expiration.

Le renouvellement est géré dans le client, non dans les outils. Lorsqu'un appel
est refusé pour cause d'authentification, le client renouvelle son jeton puis
rejoue l'appel une seule fois. L'opération est protégée par un verrou, et une
fonction de rappel réenregistre les jetons chiffrés, en conservant l'ancien
jeton de renouvellement si le fournisseur n'en émet pas de nouveau. Ce dernier
détail évite un mode de panne discret : certains fournisseurs font tourner le
jeton de renouvellement, d'autres non, et écraser aveuglément conduirait à
perdre l'accès dans le second cas.

![Écran de paramètres, avec l'état de la connexion au logiciel client. Capture du 22 septembre 2026 sur l'instance de développement.\label{fig:ecran-params}](figures/captures/out/ecran-parametres.png){width=95%}

## Les écritures ne partent jamais sans accord

### La décision ADR-009

**Contexte.** L'agent commercial dispose d'outils qui créent des tâches,
journalisent des appels et font avancer des opportunités. Ces actions modifient
le système d'information de l'organisation cliente et sont visibles par toute
son équipe. Un modèle de langue qui se trompe de compte produit alors une
erreur que personne ne peut rattraper silencieusement.

**Options.** Laisser le modèle écrire directement donne l'expérience la plus
fluide et fait porter tout le risque sur la qualité du modèle. Interdire
purement et simplement les écritures élimine le risque et une bonne part de la
valeur. Interposer une confirmation humaine conserve la valeur et déplace la
décision.

**Décision.** Un outil déclaré comme écrivant n'est jamais exécuté à l'issue de
la décision du modèle. Le moteur d'exécution s'arrête et renvoie à l'interface
une demande de confirmation portant le nom de l'outil, ses arguments validés et
une phrase en français décrivant l'action. L'exécution n'a lieu qu'après un
appel explicite à la route de confirmation, et une seule fois.

**Conséquences.** Le tour de conversation est interrompu et doit être repris,
ce qui a deux implications qu'il vaut la peine d'expliciter.

La première concerne la reprise elle-même. Les messages produits jusqu'à
l'interruption sont renvoyés avec la demande de confirmation et persistés, de
sorte que la reprise recharge l'historique complet, y compris la demande
d'outil non encore satisfaite. Le moteur détecte les appels d'outils en attente
en cherchant, dans le dernier message de l'assistant, ceux auxquels aucun
message de résultat ne répond. Si l'utilisateur envoie un nouveau message au
lieu de confirmer, ces appels en attente sont clos par un résultat explicite
indiquant que l'action n'a pas été confirmée et n'a pas été exécutée, et
l'événement est tracé comme un refus. Le modèle voit donc que sa proposition a
été déclinée, ce qui lui évite de la reproduire à l'identique.

La seconde concerne l'idempotence, et elle est traitée à la section suivante.

La figure \ref{fig:confirmation} présente la séquence complète.

![Écriture dans le logiciel client avec confirmation humaine. L'identifiant de trace de la reprise est dérivé de façon déterministe, ce qui rend deux clics équivalents à un seul.\label{fig:confirmation}](figures/out/confirmation-ecriture.pdf){width=95%}

### Un clic deux fois n'écrit qu'une fois

La confirmation crée un risque nouveau : un double clic, un rechargement de
page ou un réessai réseau peut appeler deux fois la route de confirmation. Deux
tâches identiques apparaîtraient alors dans le logiciel du client, et la
confiance que la confirmation devait établir serait perdue par le mécanisme
censé l'établir.

La parade est en deux temps. D'abord, l'identifiant de trace de la reprise
n'est pas tiré au hasard : il est dérivé de manière déterministe de
l'identifiant de la conversation et de l'identifiant de l'appel d'outil. Deux
confirmations du même appel produisent donc le même identifiant de trace.
Ensuite, l'exécution de l'outil d'écriture est gardée par une clé de cache
construite à partir de l'organisation, de cet identifiant de trace et de
l'identifiant d'appel. Si la clé existe, le résultat mémorisé est renvoyé et
aucun appel n'est émis vers le logiciel client. Seuls les succès sont
mémorisés : un échec doit pouvoir être réessayé.

Chaque écriture effectivement tentée laisse en outre une ligne dans une table
d'audit, qui enregistre l'outil, les arguments, l'identifiant de
l'enregistrement créé, l'utilisateur qui a confirmé, et l'état de l'opération.
Cette table ne reçoit que des droits de lecture et d'insertion : une trace
d'écriture consentie ne peut être ni modifiée ni supprimée par l'application.

Un dernier détail montre le niveau de méfiance retenu. L'outil qui fait avancer
une opportunité ne se contente pas de transmettre l'étape proposée par le
modèle : il lit d'abord la liste des étapes actives du logiciel client, mise en
cache pour une heure, et refuse une valeur qui n'y figure pas. Un modèle qui
inventerait un nom d'étape plausible verrait sa proposition rejetée avant tout
appel d'écriture.

## La chaîne de traitement asynchrone

### La décision ADR-006

**Contexte.** Une campagne de présélection peut porter sur plusieurs centaines
de candidatures, chacune donnant lieu à deux appels de modèle et à une lecture
de fichier. La durée totale se compte en minutes. Pendant ce temps, les actions
commerciales, qui sont interactives, doivent continuer à s'exécuter sans
attendre.

**Options.** Traiter les lots dans le processus de l'interface de programmation
est exclu par la durée. Une file unique de tâches de fond est la solution la
plus simple, et elle garantit qu'un lot de cinq cents candidatures affame les
tâches courtes. Deux files séparées, servies par deux exécutants distincts,
suppriment cette famine au prix d'un processus de plus.

**Décision.** Deux files dès le départ. La file lourde reçoit l'extraction de
texte et la notation ; la file légère reçoit le classement final, les
synchronisations et les notifications, et sert de file par défaut. Le courtier
de messages est RabbitMQ, choisi pour ses garanties de routage et
d'acquittement ; le cache sert de dépôt de résultats et de support aux
compteurs. Toute tâche métier doit être idempotente.

**Conséquences.** La configuration déclare explicitement un échange et une clé
de routage par file. Ce n'est pas une précaution de style : sans cela, les deux
files se lient au même échange par défaut avec la même clé, et chaque message
est délivré deux fois. Le commentaire correspondant est dans le code, et il
raconte une erreur qui a été commise puis corrigée.

Une seconde conséquence n'a pas été comprise au moment de la décision, mais
mesurée bien plus tard, et elle mérite d'être énoncée ici plutôt qu'au chapitre
des résultats : **déclarer deux files ne sépare rien si un même exécutant les
consomme toutes les deux.** Les emplacements d'un exécutant abonné aux deux
files sont un pool unique ; une tâche légère attend alors derrière les
notations exactement comme s'il n'y avait qu'une file. La propriété recherchée
ne tient pas à la déclaration des files, qui est une écriture de configuration,
mais à la topologie des processus, qui est une décision d'exploitation. La
campagne de charge a mesuré les deux topologies sur le même scénario, et le
chapitre 8 en donne les chiffres.

La figure \ref{fig:celery} présente la topologie.

![Topologie des files et des exécutants. Les deux exécutants sont deux unités de service distinctes, avec des concurrences et des délais d'arrêt différents.\label{fig:celery}](figures/out/topologie-celery.pdf){width=95%}

### La forme de la chaîne de présélection

Le lancement d'une campagne répond immédiatement, avec un code indiquant que le
traitement est accepté et non terminé. La publication des tâches est
délibérément différée après l'envoi de la réponse, au moyen du mécanisme de
tâches d'arrière-plan du cadriciel. La raison est une condition de course
classique : publier avant la validation de la transaction ferait chercher à un
exécutant rapide une campagne que la base n'a pas encore vue.

La structure retenue est un regroupement de chaînes indépendantes suivi d'un
rappel. Chaque candidature donne lieu à une chaîne de deux tâches, extraction
puis notation, placées sur la file lourde ; lorsque toutes les chaînes sont
terminées, une tâche de classement s'exécute sur la file légère.

On notera un écart avec le découpage annoncé par les documents de cadrage, qui
prévoyaient trois tâches : extraction, structuration, notation. Le code n'en
compte que deux, la structuration du profil et la notation partageant la même
tâche. La justification est écrite dans le code et elle est solide : les deux
appels partagent le texte du document et se suivent immédiatement ; les séparer
imposerait une relecture de la base sans gagner de parallélisme, puisque chaque
candidature est déjà une chaîne indépendante. C'est le code qui fait foi, et la
figure \ref{fig:pipeline} le représente tel qu'il est.

![Chaîne de présélection. N chaînes indépendantes sur la file lourde, une tâche de classement sur la file légère.\label{fig:pipeline}](figures/out/pipeline-rh.pdf){width=95%}

### Idempotence : cinq verrous plutôt qu'un

L'exigence d'idempotence est facile à énoncer et difficile à tenir. Elle est
ici obtenue par une superposition de mécanismes, chacun couvrant ce que le
précédent laisse passer.

Le premier est la contrainte d'unicité sur le couple campagne-candidature,
déjà mentionnée au chapitre 5. C'est le dernier recours : quoi qu'il arrive en
amont, la base refuse la seconde notation.

Le deuxième est une vérification explicite avant tout appel de modèle : si une
notation existe déjà pour ce couple et qu'elle est en succès, la tâche se
termine immédiatement en signalant qu'elle n'avait rien à faire. C'est ce
verrou qui rend un réessai bon marché, puisqu'il économise les deux appels
facturés.

Le troisième est la conservation du texte extrait. Une tâche d'extraction
rejouée sur une candidature dont le texte est déjà en base le renvoie sans
relire le fichier.

Le quatrième est le refus d'écraser un succès. La fonction qui marque un échec
vérifie l'état existant et ne dégrade jamais une notation réussie ; un échec
tardif d'une tâche dont une autre exécution a déjà abouti ne détruit donc pas
le résultat.

Le cinquième est le recalcul du classement depuis la base plutôt que depuis les
valeurs renvoyées par les tâches. Le rappel final ne fait pas confiance à ce
que les chaînes lui transmettent ; il relit, trie et écrit les rangs. Une tâche
rejouée, dont le résultat arriverait en double, n'a donc aucun effet sur
l'ordre.

À ces cinq verrous s'ajoute une politique de réessai différenciée. Les
exceptions considérées comme transitoires, erreurs de la passerelle de modèles,
dépassements de délai, ruptures de connexion et erreurs de système de fichiers,
déclenchent un réessai avec un délai qui double à chaque tentative, dans la
limite de trois. Toute autre exception est capturée et transformée en ligne de
notation en échec : le lot doit survivre à tout, y compris à une candidature
qui déclencherait un défaut imprévu. Lorsque les réessais sont épuisés, l'échec
est enregistré comme tel, avec son motif tronqué.

Un dernier mécanisme, propre au chapitre 5 mais dont l'effet est ici, régule le
débit. Un quota d'appels de modèle par organisation et par minute est tenu dans
le cache, partagé par tous les exécutants. Lorsqu'il est atteint, la tâche
attend la minute suivante plutôt que d'échouer ; au-delà d'une attente maximale,
elle lève une erreur de délai, laquelle fait partie des exceptions transitoires
et déclenche donc un réessai. Une organisation ne peut pas, par un lot
volumineux, consommer la capacité d'appel d'une autre.

### Voir ce qui tourne

Une tâche de fond qui échoue sans laisser de trace visible est une tâche dont
personne ne sait rien. Le système journalise donc chaque exécution dans une
table dédiée, au moyen des signaux émis par l'exécutant plutôt que par du code
inséré dans chaque tâche. Ce choix a une conséquence heureuse : l'instrumentation
couvre toutes les tâches, y compris celles qui seront ajoutées plus tard, sans
que leur auteur ait à y penser.

Trois règles gouvernent ce journal. La première est que l'organisation est lue
dans les arguments de la tâche, par une convention de position qui place
l'identifiant d'organisation en dernier ; la fonction de lecture balaie les
arguments à l'envers et n'accepte qu'un identifiant bien formé. La deuxième est
que le signal ne doit jamais faire échouer la tâche : chaque écriture est
enveloppée et son échec se contente d'un avertissement. La troisième est que
seuls les arguments positionnels, qui sont des identifiants, sont enregistrés ;
jamais un contenu de candidature, jamais un jeton.

La figure \ref{fig:taskevents} décrit le cycle de vie d'une ligne.

![Cycle de vie d'une exécution de tâche. Un réessai interne rouvre la ligne existante ; une relance depuis l'interface crée une ligne nouvelle.\label{fig:taskevents}](figures/out/cycle-task-events.pdf){width=95%}

La distinction entre les deux formes de réessai est importante. Un réessai
interne à l'exécutant réutilise le même identifiant de tâche ; la ligne
existante est donc rouverte plutôt que dupliquée, ce qui évite d'empiler une
ligne par tentative. Une relance demandée depuis l'interface, en revanche,
publie une nouvelle exécution : elle crée une ligne nouvelle et incrémente un
compteur sur l'ancienne, qui reste en échec. Rien n'a le droit de supprimer une
ligne, et les droits accordés à l'application le garantissent.

La route de relance applique trois vérifications avant de republier : l'état
doit être en échec, l'organisation lue dans les arguments enregistrés doit
correspondre à celle du contexte de requête, et la file doit être l'une des
deux connues, faute de quoi la tâche part sur la file légère. La deuxième
vérification mérite d'être soulignée : elle relit l'organisation dans les
arguments plutôt que de se fier à la ligne, ce qui ferme la possibilité de
republier, depuis une organisation, une tâche portant sur les données d'une
autre.

![File de traitement, capture du 22 septembre 2026 sur l'instance de développement.\label{fig:ecran-queue}](figures/captures/out/ecran-file-traitement.png){width=95%}

### Le modèle de données de l'exploitation

La figure \ref{fig:schema-exploit} présente les trois tables d'exploitation,
dérivées des classes déclarées.

![Tables d'audit et d'exploitation, dérivées des classes SQLAlchemy.\label{fig:schema-exploit}](figures/out/schema-exploitation.pdf){width=95%}

Les droits accordés au rôle d'exécution diffèrent d'une table à l'autre, et
cette différence encode une intention. Les journaux d'appels de modèles et de
traces d'agent ne reçoivent que la lecture et l'insertion : ce sont des
journaux, ils ne se corrigent pas. La table des écritures dans le logiciel
client suit la même règle. La table des exécutions de tâches reçoit en outre la
mise à jour, parce qu'une ligne y est ouverte au démarrage et complétée à la
fin ; elle ne reçoit pas la suppression. Les tables de la présélection, enfin,
ont reçu tardivement un droit de suppression restreint aux candidatures et à
leurs résultats, pour servir le droit à l'effacement des données personnelles ;
ni les offres ni les campagnes ne sont supprimables, car effacer une campagne
effacerait la trace d'une décision de présélection qui doit rester auditable.

La figure \ref{fig:schema-agents} complète le tableau avec les quatre tables
des conversations et du traçage, qui relèvent du chapitre 5 mais dont la
lecture est plus claire ici, à côté des tables d'audit.

![Tables des conversations et du traçage des agents, dérivées des classes SQLAlchemy.\label{fig:schema-agents}](figures/out/schema-agents.pdf){width=95%}

## Ce que cela implique pour l'évaluation

Ce chapitre a établi trois propriétés dont la partie 3 aura besoin. La première
est qu'aucune action irréversible ne s'exécute sans accord explicite et, en cas
d'accord, ne s'exécute qu'une fois : une suite d'évaluation peut donc être
rejouée sans polluer le système d'information d'une organisation. La deuxième
est que l'ensemble des exécutions de tâches est journalisé par des signaux
indépendants du code métier, ce qui rend mesurables le taux d'échec et la durée
par étape sans instrumentation supplémentaire. La troisième est que le débit
d'appels au modèle est borné par organisation et paramétrable, y compris
désactivable, ce qui permet de mesurer un temps de traitement de lot sans que
la régulation en fausse la lecture.
