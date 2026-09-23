# Annexe A — Glossaire {-}

Les termes sont définis à leur première occurrence dans le corps du texte ;
cette annexe rassemble ces définitions pour consultation. Lorsqu'un terme
anglais est d'usage courant dans la littérature, il est donné entre
parenthèses, sans être employé dans le mémoire.

**Agent (fondé sur un modèle de langue).** Programme dans lequel un modèle de
langue décide, à chaque étape, soit de produire une réponse, soit d'invoquer
une fonction mise à sa disposition, dont le résultat lui est ensuite
communiqué. Défini par trois composants : une invite système, un catalogue
d'outils et une boucle d'exécution bornée. Chapitre 2.

**Alias de modèle.** Nom fonctionnel désignant une tâche (par exemple
`hr.score`) et résolu en un modèle concret par un fichier de configuration.
Aucun nom de modèle n'apparaît dans le code du projet. Décision ADR-011.

**Alignement.** Ensemble des procédures d'entraînement postérieures au
pré-entraînement visant à rendre le comportement d'un modèle conforme à des
instructions et à des préférences humaines : ajustement supervisé sur
instructions, apprentissage par renforcement à partir de préférences humaines.
Chapitre 1.

**Apprentissage en contexte** (*in-context learning*). Capacité d'un modèle à
accomplir une tâche décrite dans son entrée, éventuellement illustrée par
quelques exemples, sans aucune mise à jour de ses paramètres. Chapitre 1.

**Attention.** Mécanisme par lequel une position d'une séquence calcule une
pondération apprise sur l'ensemble des autres positions et en agrège les
représentations. L'auto-attention applique ce calcul à l'intérieur d'une même
séquence. Chapitre 1.

**Boucle d'exécution (d'un agent).** Alternance d'appels au modèle et
d'exécutions d'outils, jusqu'à une réponse finale ou l'atteinte d'une limite
d'étapes. Bornée à six appels dans notre système. Chapitres 2 et 5.

**Budget de contexte.** Nombre maximal de jetons que le système s'autorise à
placer dans l'invite d'un appel, fixé par la configuration et appliqué par un
module déterministe. Chapitres 2 et 5.

**Chaîne de traitement.** Suite ordonnée d'étapes appliquées à une même unité
de travail, ici : extraction du texte d'un document, structuration en profil,
notation contre une grille. Chaque étape est une tâche asynchrone distincte et
reprenable. Chapitres 2 et 5.

**Chaîne de pensée** (*chain of thought*). Technique consistant à demander au
modèle d'énoncer les étapes intermédiaires de son raisonnement avant sa
conclusion. Chapitre 1.

**Confirmation humaine.** Règle selon laquelle un outil modifiant l'état d'un
système tiers n'est jamais exécuté sur la seule décision du modèle :
l'exécutif retourne la demande à l'interface, qui la soumet à l'utilisateur.
Décision ADR-009.

**Définition d'agent.** Donnée décrivant un agent : invite système versionnée,
liste d'outils, alias de modèle, schéma de sortie attendu, limite d'étapes. À
distinguer de l'exécutif, qui est du code partagé. Chapitre 2.

**Décodage et préremplissage.** Les deux phases d'un appel à un modèle
génératif : le préremplissage traite d'un bloc tous les jetons de l'entrée, le
décodage produit les jetons de la réponse un à un. L'entrée pèse surtout sur le
coût, la sortie surtout sur la latence. Chapitre 1.

**Fenêtre de contexte.** Nombre maximal de jetons qu'un modèle peut prendre en
compte en une seule fois. Ressource coûteuse, l'attention ayant un coût
quadratique en la longueur de la séquence. Chapitre 1.

**File de tâches.** Canal de distribution de travaux asynchrones entre un
service applicatif et des exécutants. Le projet en emploie deux : une pour les
traitements lourds, une pour les traitements légers. Décision ADR-006.

**Génération augmentée par récupération** (*retrieval-augmented generation*).
Dispositif qui recherche des passages pertinents dans un corpus et les insère
dans l'invite avant génération. Écartée ici au profit de la récupération
structurée, les données concernées étant déjà structurées. Chapitre 2,
décision ADR-008.

**Grand modèle de langue.** Modèle de langue neuronal dont le nombre de
paramètres se compte en milliards et entraîné sur des corpus de plusieurs
centaines de milliards de jetons. La frontière est conventionnelle. Chapitre 1.

**Grille de critères.** Ensemble de critères pondérés, dont certains
éliminatoires, dérivé d'une offre d'emploi et appliqué identiquement à chaque
candidature. Chapitres 2 et 5.

**Hallucination.** Production par un modèle d'un énoncé faux mais fluide et
assuré. Conséquence de l'objectif d'entraînement, non défaut d'implémentation.
Chapitre 1.

**Idempotence.** Propriété d'une opération qui produit le même effet qu'elle
soit exécutée une ou plusieurs fois avec la même clé. Exigée de toute tâche
asynchrone du projet. Décision ADR-006.

**Injection de consigne** (*prompt injection*). Attaque consistant à faire
ignorer au modèle sa consigne initiale au profit d'une instruction fournie
dans l'entrée. L'injection est dite indirecte lorsque l'instruction est
dissimulée dans un document que l'application donne elle-même à lire au
modèle. Chapitres 1 et 2.

**Invite** (*prompt*). Texte fourni au modèle pour le mettre au travail. On
distingue l'invite système, qui fixe rôle et règles, de l'invite utilisateur,
qui porte la demande. Les invites du projet sont des fichiers versionnés du
dépôt. Chapitre 1, décision ADR-010.

**Isolation multi-locataire.** Garantie qu'une organisation cliente ne peut
accéder aux données d'une autre. Appliquée ici au niveau de la base de données
par des politiques de sécurité au niveau des lignes, et non seulement par le
code applicatif. Chapitre 2, décision ADR-002.

**Jeton** (*token*). Fragment de texte issu d'un découpage appris : mot entier,
morceau de mot ou signe de ponctuation. Unité de facturation des modèles
commerciaux. Chapitre 1.

**Jeu de données de référence.** Ensemble d'entrées et de sorties attendues,
construit et annoté à l'avance, rejoué à chaque évaluation. Chapitre 2,
partie 3.

**Latence au 95e centile.** Durée en deçà de laquelle se situent quatre-vingt-quinze pour cent
 des réponses. Préférée à la moyenne, la queue de distribution
déterminant l'abandon par l'utilisateur. Chapitre 2.

**Logiciel de gestion de la relation client** (*customer relationship
management*). Logiciel centralisant comptes, contacts, opportunités de vente et
activités commerciales. Chapitre 2.

**Logiciel en tant que service** (*software as a service*). Mode de
distribution où une même application, exploitée par l'éditeur, sert plusieurs
organisations clientes sur abonnement. Chapitre 3.

**Modèle de langue.** Fonction attribuant une probabilité à une suite de
symboles et permettant donc de prédire la suite la plus vraisemblable d'un
texte. Chapitre 1.

**Outil (d'un agent).** Fonction exposée au modèle sous forme de schéma de
données, que le modèle peut demander d'exécuter en produisant ses arguments.
L'exécution est réalisée par le programme, jamais par le modèle. Chapitres 1
et 2.

**Perplexité.** Mesure intrinsèque de la qualité d'un modèle de langue :
inverse de la probabilité moyenne géométrique attribuée aux jetons d'un texte
de référence. Chapitre 1.

**Plongement lexical** (*word embedding*). Représentation d'un mot ou d'un
passage par un vecteur de nombres réels, apprise de telle sorte que la
proximité dans l'espace traduise une proximité de sens. Chapitres 1 et 2.

**Pré-entraînement.** Phase d'apprentissage d'un modèle sur un grand corpus
non annoté, par prédiction du jeton suivant ou reconstitution de jetons
masqués, préalable à toute spécialisation. Chapitre 1.

**Progiciel de gestion intégré** (*enterprise resource planning*). Logiciel
couvrant les processus financiers, logistiques et de production d'une
organisation. Chapitre 2.

**Récupération structurée.** Stratégie consistant à exposer au modèle un
catalogue de requêtes typées, dont il choisit la ou les pertinentes et dont le
programme exécute le contenu contre la source de vérité. Chapitre 2, décision
ADR-008.

**Repli** (*fallback*). Modèle de substitution déclaré en configuration et
employé lorsque le modèle principal d'un alias est indisponible ou en erreur.
Décision ADR-011.

**Réseau de neurones récurrent.** Réseau traitant une séquence élément par
élément en maintenant un état interne mis à jour à chaque pas. Chapitre 1.

**Sécurité au niveau des lignes** (*row-level security*). Mécanisme de
PostgreSQL filtrant, au niveau du moteur de base de données, les lignes
visibles par une transaction selon une politique déclarée. Chapitre 2,
décision ADR-002.

**Sortie structurée.** Réponse d'un modèle conforme à un schéma de données
plutôt qu'à du texte libre. Obtenue par consigne ou par contrainte du décodage ;
dans les deux cas, elle doit être validée côté application avant usage.
Chapitre 1.

**Système d'information des ressources humaines.** Logiciel gérant salariés,
candidatures et processus de recrutement. Chapitre 2.

**Système multi-agents.** Dispositif confiant à plusieurs agents des rôles
distincts qui coopèrent. Écarté ici au profit d'un exécutif unique paramétré
par plusieurs définitions d'agents. Chapitre 2.

**Transformeur** (*transformer*). Architecture neuronale reposant sur
l'attention et sur des transformations appliquées position par position, sans
récurrence, ce qui permet la parallélisation de l'entraînement. Chapitre 1.

**Trace d'exécution.** Enregistrement ordonné des étapes d'une exécution
d'agent (appel au modèle, appel d'outil, résultat résumé, latence), conservé
en base et présentable à l'utilisateur. Chapitres 2 et 5.
