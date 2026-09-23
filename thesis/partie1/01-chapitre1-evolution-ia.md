# Évolution des modèles de langue : des réseaux récurrents aux grands modèles instruits

## Objet et périmètre du chapitre

Ce chapitre retrace la filiation technique qui mène des premiers modèles
neuronaux de séquences aux systèmes conversationnels capables d'appeler des
outils logiciels. Son but n'est pas encyclopédique : il s'agit d'isoler, à
chaque étape, la propriété nouvelle qui rend possible le produit décrit dans la
suite du mémoire, et le coût qu'elle introduit. Le chapitre se clôt donc sur
les limites établies de ces modèles, car ce sont elles, et non leurs réussites,
qui ont dicté l'essentiel de nos choix d'architecture.

Deux conventions de vocabulaire valent pour tout le mémoire. Un **modèle de
langue** est une fonction qui attribue une probabilité à une suite de mots,
et qui permet donc de prédire la suite la plus vraisemblable d'un texte
donné. Un **grand modèle de langue** désigne, par usage, un modèle de langue
neuronal dont le nombre de paramètres se compte en milliards et qui a été
entraîné sur des corpus de plusieurs centaines de milliards d'unités
textuelles ; la frontière est conventionnelle et non théorique. Le terme
anglais *large language model* et son sigle sont écartés au profit de
l'expression française, employée telle quelle dans la suite.

## Modéliser une langue : la tâche et son évaluation

### La tâche

Modéliser une langue consiste à estimer la probabilité d'une suite de symboles
$w_1, \dots, w_n$. La règle des probabilités composées ramène cette estimation
à un produit de probabilités conditionnelles : chaque symbole est prédit à
partir de ceux qui le précèdent. Tous les modèles évoqués dans ce chapitre,
des plus anciens aux plus récents, résolvent cette même tâche ; ce qui change
est la façon dont le contexte antérieur est représenté.

Les symboles manipulés ne sont pas des mots au sens ordinaire mais des
**jetons** : des fragments de texte issus d'un découpage appris sur le corpus,
qui peuvent correspondre à un mot entier, à un morceau de mot ou à un signe de
ponctuation. Ce point, d'apparence technique, a une conséquence économique
directe : les fournisseurs de modèles facturent au jeton, et le découpage est
moins efficace pour le français que pour l'anglais, et davantage encore pour
le malgache. Un même texte coûte donc plus cher à traiter selon la langue dans
laquelle il est écrit.

### L'évaluation intrinsèque

La mesure intrinsèque historique est la **perplexité** : l'inverse de la
probabilité moyenne géométrique attribuée par le modèle aux jetons d'un texte
de référence. Une perplexité basse signifie que le modèle est peu surpris par
le texte observé. Cette mesure a longtemps suffi parce que les modèles ne
servaient qu'à des tâches internes (reconnaissance de la parole, traduction
automatique). Elle est devenue insuffisante dès lors que les modèles ont été
employés comme assistants : un modèle peut être peu surpris par un texte et
produire malgré tout une réponse fausse, mal formée ou dangereuse. L'évaluation
des systèmes construits sur ces modèles fait l'objet d'une littérature propre,
abordée au chapitre 2 et reprise dans la partie 3.

### Des mots aux vecteurs

Les modèles à n-grammes, qui estiment la probabilité d'un mot à partir des
$n-1$ mots précédents comptés dans un corpus, souffrent de deux défauts
rédhibitoires : ils ne généralisent pas entre mots de sens voisin, et le nombre
de combinaisons à estimer croît de façon prohibitive avec $n$.

La réponse a consisté à représenter chaque mot par un vecteur de nombres réels,
appelé **plongement lexical** (*plongement* au sens mathématique
d'une immersion d'un ensemble discret dans un espace continu). Les travaux de
Mikolov et ses collègues ont montré qu'un tel espace, appris sur de grands
corpus non annotés, organise les mots selon des régularités sémantiques
exploitables [@mikolov2013word2vec]. Deux mots de sens proche y occupent des
positions proches, ce qui donne au modèle une capacité de généralisation que
les décomptes de n-grammes n'avaient pas. Ces plongements sont toutefois
statiques : un mot polysémique reçoit un vecteur unique, quel que soit son
contexte d'emploi.

## Les réseaux récurrents et leur plafond

### Récurrence, mémoire, oubli

Un **réseau de neurones récurrent** traite une séquence élément par élément en
maintenant un état interne mis à jour à chaque pas. Cet état joue le rôle de
mémoire du passé. En pratique, l'apprentissage de ces réseaux se heurte à la
disparition ou à l'explosion du gradient sur les longues séquences : le signal
d'erreur, propagé de proche en proche vers l'arrière, s'évanouit ou diverge, et
le réseau devient incapable d'apprendre des dépendances distantes.

L'architecture **à mémoire court-terme longue**, proposée par Hochreiter et
Schmidhuber, contourne ce problème en introduisant une cellule de mémoire
protégée par des portes multiplicatives qui décident explicitement de ce qui
est conservé, écrit ou oublié [@hochreiter1997lstm]. Cho et ses collègues ont
proposé ensuite une variante simplifiée, l'unité récurrente à portes, dans le
cadre d'un modèle encodeur-décodeur pour la traduction automatique
[@cho2014learning].

### Encodeur-décodeur et attention

Sutskever, Vinyals et Le ont généralisé ce schéma sous le nom d'apprentissage
de séquence à séquence : un premier réseau, l'encodeur, comprime la phrase
source en un vecteur unique de taille fixe ; un second réseau, le décodeur,
engendre la phrase cible à partir de ce vecteur [@sutskever2014seq2seq]. Le
goulot d'étranglement est manifeste : tout le contenu d'une phrase longue doit
tenir dans un vecteur de dimension fixe.

Le mécanisme d'**attention** lève cette contrainte. Bahdanau, Cho et Bengio
ont proposé que le décodeur, à chaque pas de génération, calcule une pondération
sur l'ensemble des états de l'encodeur et se construise ainsi un résumé du
contexte adapté au mot qu'il est en train de produire [@bahdanau2015attention].
L'attention n'est pas encore une architecture, seulement un complément aux
réseaux récurrents ; mais elle introduit l'idée décisive d'un accès direct,
pondéré et appris, à l'ensemble du contexte.

Le plafond qui subsiste est d'ordre pratique plus que théorique : la récurrence
impose un traitement séquentiel, donc une parallélisation impossible sur la
dimension du temps. Or c'est la parallélisation qui conditionne l'entraînement
sur de très grands corpus.

## Le transformeur

Vaswani et ses collègues ont franchi ce seuil en supprimant purement et
simplement la récurrence : l'architecture **transformeur** ne repose que sur
des mécanismes d'attention et des transformations appliquées à chaque position
indépendamment [@vaswani2017attention]. Trois éléments en font la singularité.

L'**auto-attention** fait jouer à chaque position de la séquence les trois
rôles de requête, de clé et de valeur : chaque jeton calcule une pondération
sur tous les autres jetons de la même séquence et en agrège les
représentations. La dépendance entre deux positions, aussi éloignées
soient-elles, est établie en une seule opération, là où un réseau récurrent
devait la propager de proche en proche.

L'**attention multi-têtes** répète ce calcul selon plusieurs projections
apprises en parallèle, ce qui permet au modèle de suivre simultanément
plusieurs types de relations entre jetons.

L'**encodage de position**, enfin, réinjecte l'information d'ordre, que
l'attention seule ignore puisqu'elle traite la séquence comme un ensemble.

La conséquence économique de cette architecture est aussi importante que sa
qualité linguistique : toutes les positions étant traitées en parallèle,
l'entraînement exploite pleinement les accélérateurs matériels. En contrepartie,
le coût de l'auto-attention croît de façon quadratique avec la longueur de la
séquence, ce qui fait de la taille de la **fenêtre de contexte**, c'est-à-dire
du nombre maximal de jetons que le modèle peut considérer en une fois, une
ressource coûteuse et rationnée. Ce point est déterminant pour le chapitre 2 :
il justifie qu'un système sérieux ne puisse pas se contenter de « tout donner
au modèle ».

## Pré-entraînement, transfert et lois d'échelle

### Trois familles

Peters et ses collègues ont montré avec ELMo que des représentations
contextuelles, calculées par un réseau entraîné en modélisation de langue
puis réutilisées en aval, améliorent un large éventail de tâches
[@peters2018elmo]. Le transformeur a ensuite donné naissance à trois familles.

Les modèles **à encodeur seul**, dont BERT est le représentant, sont entraînés
à reconstituer des jetons masqués dans une phrase et produisent des
représentations bidirectionnelles adaptées à la classification et à
l'extraction [@devlin2019bert]. Les modèles **à décodeur seul**, dont la série
GPT, sont entraînés à prédire le jeton suivant et sont par construction
générateurs [@radford2018improving ; @radford2019gpt2]. Les modèles
**encodeur-décodeur**, dont T5, ramènent toute tâche à une conversion de texte
en texte [@raffel2020t5].

C'est la famille à décodeur seul qui porte les systèmes conversationnels
actuels, parce que la génération libre est le mode d'interaction attendu et
parce que la même architecture sert indifféremment à répondre, à résumer, à
classer ou à produire un objet structuré.

### Lois d'échelle

Kaplan et ses collègues ont établi que la performance de ces modèles suit des
relations régulières, approximativement en loi de puissance, avec le nombre de
paramètres, la taille du corpus et le budget de calcul [@kaplan2020scaling].
Hoffmann et ses collègues ont corrigé l'équilibre proposé : à budget de calcul
constant, les modèles de l'époque étaient trop grands pour la quantité de
données sur laquelle ils étaient entraînés, et un modèle plus petit entraîné
plus longtemps obtient de meilleurs résultats [@hoffmann2022chinchilla].

### L'économie d'un appel

Une conséquence moins discutée de cette architecture mérite d'être posée, car
elle gouverne la latence perçue par l'utilisateur. Un appel à un modèle
génératif se décompose en deux phases de coûts très différents. La phase de
**préremplissage** traite en une fois l'ensemble des jetons de l'entrée ; elle
est parallélisable et son coût croît avec la longueur de l'invite. La phase de
**décodage** produit les jetons de la réponse un à un, chacun dépendant des
précédents ; elle est séquentielle et son coût croît avec la longueur de la
réponse.

Il en résulte qu'une invite longue coûte surtout de l'argent, tandis qu'une
réponse longue coûte surtout du temps. Les deux leviers d'un produit soucieux
de sa latence sont donc distincts : réduire ce que l'on envoie, et réduire ce
que l'on demande. Un troisième levier existe, la mise en cache de la partie
stable de l'invite par le fournisseur, mais il est propre à chaque fournisseur
et ne doit pas être supposé acquis dans une conception.

Deux conséquences pratiques en découlent pour un projet de la taille du nôtre.
D'une part, entraîner un modèle de fond est hors de portée : les budgets
concernés sont ceux de grandes entreprises, pas d'une petite structure
malgache, et cette impossibilité est structurelle, non conjoncturelle. D'autre
part, la frontière entre modèles « légers » et modèles « forts » est une
frontière de coût autant que de qualité, ce qui rend rationnel de router
chaque sous-tâche vers le modèle le moins cher qui la traite correctement.
Cette idée fonde l'un de nos choix d'architecture, exposé au chapitre 4.

## De la complétion à l'obéissance

### Apprentissage en contexte

Brown et ses collègues ont observé qu'un modèle à décodeur suffisamment grand
peut accomplir une tâche décrite dans son entrée, avec quelques exemples et
sans mise à jour de ses paramètres [@brown2020gpt3]. Cette capacité,
appelée **apprentissage en contexte**, déplace une partie de la programmation
vers la rédaction de l'entrée. On nomme **invite** (en anglais *prompt*) le
texte fourni au modèle pour le mettre au travail ; on distingue l'invite
système, qui fixe le rôle et les règles, de l'invite utilisateur, qui porte la
demande.

### Ajustement aux instructions et alignement

Un modèle pré-entraîné complète du texte ; il n'obéit pas. Wei et ses collègues
ont montré qu'un ajustement supervisé sur un ensemble de tâches formulées en
langue naturelle améliore fortement la capacité du modèle à suivre une
instruction inédite [@wei2022flan]. Christiano et ses collègues avaient
posé auparavant le principe d'un apprentissage par renforcement guidé par des
préférences humaines comparatives plutôt que par une fonction de récompense
écrite à la main [@christiano2017preferences]. Ouyang et ses collègues ont combiné les
deux dans la procédure devenue standard : ajustement supervisé sur des
démonstrations, apprentissage d'un modèle de récompense sur des comparaisons
humaines, puis optimisation du modèle contre cette récompense
[@ouyang2022instructgpt]. Bai et ses collègues ont proposé une variante où les
critères de comportement sont explicités dans un document et où une partie du
signal de préférence est produite par le modèle lui-même [@bai2022constitutional].

Cette chaîne d'**alignement** est ce qui rend un modèle utilisable comme
assistant. Elle a aussi deux effets qu'il faut nommer. D'abord, elle introduit
une couche de jugement normatif, définie par le fournisseur et non par
l'organisation qui déploie le modèle. Ensuite, elle rend le comportement du
modèle dépendant d'une version : deux versions successives d'un même modèle
commercial n'obéissent pas identiquement à la même invite. Pour un mémoire dont
une partie repose sur des mesures, cette instabilité impose de journaliser la
version exacte du modèle et de l'invite utilisés à chaque appel.

### Raisonnement explicite

Wei et ses collègues ont montré qu'inviter le modèle à énoncer les étapes
intermédiaires de son raisonnement améliore sensiblement ses résultats sur les
tâches à plusieurs étapes [@wei2022cot]. Cette technique, dite de **chaîne
de pensée**, est employée dans notre système sous une forme contrainte : les
étapes intermédiaires servent à sélectionner des outils, et la trace produite
est conservée pour être montrée à l'utilisateur.

## L'appel d'outils : du texte à l'action

Un modèle de langue seul ne sait rien du monde postérieur à son entraînement,
ne peut pas consulter une base de données et ne peut pas agir. La levée de
cette limite est l'étape qui fait passer du modèle à l'**agent**, au sens que
nous préciserons au chapitre 2.

Parisi, Zhao et Fiedel puis Schick et ses collègues ont montré qu'un modèle
peut apprendre à émettre lui-même des appels à des interfaces externes et à
en réinjecter les résultats dans sa génération [@parisi2022talm ;
@schick2023toolformer]. Yao et ses collègues ont formalisé l'alternance entre
raisonnement et action sous le nom de ReAct : le modèle produit une pensée,
choisit une action, observe le résultat, et recommence [@yao2023react]. Patil
et ses collègues, puis Qin et ses collègues, ont étendu le procédé à des
catalogues d'interfaces de grande taille [@patil2024gorilla ; @qin2024toolllm].

L'industrialisation de ce mécanisme a pris une forme simple et désormais
commune à tous les fournisseurs : on décrit au modèle un ensemble de fonctions
par un schéma de données, et le modèle répond, au lieu d'un texte, par un objet
structuré nommant la fonction et ses arguments. C'est le programme appelant,
et non le modèle, qui exécute effectivement la fonction. Cette séparation est
fondamentale pour la sécurité : le modèle propose, le code dispose. Le
protocole de contexte de modèle, publié par Anthropic, normalise la déclaration
et la découverte de tels outils par un serveur distinct de l'application
[@anthropic2024mcp ; @mcp2025spec].

### Sorties structurées

L'appel d'outils est un cas particulier d'un besoin plus général : obtenir du
modèle, non un texte libre, mais un objet conforme à un schéma. Les
fournisseurs proposent pour cela deux mécanismes de nature différente. Le
premier relève de la consigne : on décrit le format attendu dans l'invite et
l'on espère qu'il sera respecté. Le second relève du décodage : la génération
est contrainte, jeton par jeton, à ne produire que des suites valides au regard
d'une grammaire ou d'un schéma. Le premier est universel et faillible ; le
second est garanti mais dépend du fournisseur et ne garantit que la forme, non
le contenu.

Aucun des deux ne dispense de valider la sortie côté application : un objet
syntaxiquement valide peut porter une valeur d'énumération inexistante, une
date impossible ou un identifiant inventé. La règle que nous retiendrons est
donc invariable : toute sortie du modèle est une donnée non fiable jusqu'à
validation contre un schéma exécutable, et un échec de validation est un
événement normal du système, à traiter par une nouvelle tentative informée de
l'erreur, non par une exception remontée à l'utilisateur.

Trois propriétés de ce mécanisme conditionnent la conception d'un produit.
La sortie du modèle reste **non fiable par nature** : les arguments produits
doivent être validés contre un schéma avant toute exécution. L'exécution est
**itérative** : un agent alterne appels au modèle et appels d'outils, ce qui
multiplie la latence et le coût par le nombre d'itérations. Et l'ensemble est
**non borné** si rien ne le borne : sans limite explicite, une boucle d'agent
peut consommer indéfiniment.

## Spécialiser un modèle : trois voies et leur coût

Trois voies existent pour adapter un modèle de fond à un domaine particulier.

Le **réentraînement partiel** modifie les paramètres du modèle. Les méthodes
dites à faible rang, dont LoRA et sa variante quantifiée QLoRA, réduisent
fortement le coût de cette opération en n'apprenant que de petites matrices
additionnelles [@hu2022lora ; @dettmers2023qlora]. Le coût reste néanmoins
celui d'un cycle d'apprentissage, d'une collecte de données annotées et d'une
infrastructure de service dédiée.

L'**ingénierie d'invite** ne modifie rien au modèle et ne coûte que la
rédaction et l'évaluation d'un texte. Elle est immédiate, réversible et
lisible en revue de code, mais elle est plafonnée par les connaissances déjà
présentes dans le modèle.

L'**augmentation par le contexte** consiste à fournir au modèle, au moment de
l'appel, les données dont il a besoin. Elle suppose de savoir sélectionner ces
données ; c'est l'objet du chapitre 2.

Pour un système qui doit servir plusieurs organisations aux données
différentes, la troisième voie est la seule qui passe à l'échelle sans
multiplier les modèles. La première supposerait un modèle par client ; c'est
précisément ce qu'une petite structure ne peut pas exploiter.

## Limites établies

### Fabrication d'énoncés faux

Un modèle de langue produit l'énoncé le plus vraisemblable, non le plus vrai.
Il engendre donc, de façon fluide et assurée, des énoncés faux : c'est le
phénomène d'**hallucination**, dont Ji et ses collègues ont dressé une revue
systématique [@ji2023hallucination]. Le phénomène n'est pas un défaut d'implémentation
que l'on corrigerait : il découle de l'objectif d'entraînement lui-même. Les
seules atténuations robustes consistent à ancrer la génération dans des données
vérifiables et à exiger que chaque affirmation soit accompagnée de sa source.

### Usage effectif de la fenêtre de contexte

L'allongement des fenêtres de contexte ne résout pas le problème précédent.
Liu et ses collègues ont montré que les modèles exploitent inégalement leur
contexte : une information placée au milieu d'une longue entrée est moins bien
utilisée qu'une information placée au début ou à la fin [@liu2024lost]. Il
s'ensuit qu'entasser des documents dans le contexte dégrade à la fois le coût
et la qualité. La sélection et l'ordonnancement de ce qui entre dans le
contexte sont donc un travail d'ingénierie à part entière, et non un réglage
secondaire.

### Coût monétaire et coût énergétique

Chaque appel a un prix, fonction du nombre de jetons d'entrée et de sortie.
Un système qui traite des lots de documents multiplie ce prix par la taille du
lot, ce qui fait du coût unitaire une contrainte de conception et non une
ligne comptable. Strubell, Ganesh et McCallum ont attiré l'attention sur le
coût énergétique de l'entraînement des modèles de langue [@strubell2019energy],
et Luccioni, Viguier et Ligozat ont proposé une estimation détaillée pour un
modèle de grande taille [@luccioni2023bloom]. Ces travaux portent sur
l'entraînement ; le coût cumulé de l'inférence, à l'échelle d'un parc de
services, relève d'une littérature moins établie. Côté exploitation, les
travaux sur le service efficace de ces modèles, dont Kwon et ses collègues
pour la gestion de la mémoire d'un serveur d'inférence [@kwon2023vllm],
montrent que l'hébergement d'un modèle par soi-même est un problème
d'ingénierie système à part entière, et non un simple déploiement
d'application.

### Vulnérabilité aux instructions injectées

Un modèle ne distingue pas, dans son entrée, ce qui relève de la consigne et
ce qui relève de la donnée. Perez et Ribeiro ont décrit les techniques
consistant à faire ignorer au modèle sa consigne initiale [@perez2022ignoreprompt].
Greshake et ses collègues ont montré la forme la plus préoccupante pour un
produit d'entreprise : l'**injection indirecte de consigne**, où l'instruction
malveillante est dissimulée dans un document que l'application donne elle-même
à lire au modèle [@greshake2023indirect]. Dans notre cas, un curriculum vitæ déposé
par un candidat, ou une note de compte rendu saisie dans un logiciel de
gestion de la relation client, sont exactement de tels documents. Liu et ses collègues ont proposé une formalisation et un jeu
d'épreuves de ces attaques et de leurs parades, et montrent qu'aucune défense
connue ne les neutralise complètement [@liu2024formalizing ;
@liu2023promptinjection]. La liste OWASP des risques propres aux applications
fondées sur des modèles de langue place cette catégorie au premier rang
[@owasp2025llmtop10].

### Inégalité entre langues

Les corpus de pré-entraînement sont massivement anglophones, et les procédures
d'alignement le sont également. Il en découle une inégalité de traitement entre
langues qui a trois manifestations pratiques. La qualité des réponses est
généralement meilleure en anglais qu'en français, et l'écart s'accroît pour les
langues moins dotées. Le découpage en jetons est moins efficace hors de
l'anglais, ce qui signifie qu'un même texte consomme davantage de jetons, donc
coûte plus cher et occupe une plus grande part de la fenêtre de contexte. Et
les comportements obtenus par ajustement aux instructions, notamment le respect
d'un format de sortie, sont moins stables lorsque la consigne est rédigée dans
une langue moins représentée.

Pour un produit destiné à un marché francophone où une partie des documents
traités peut comporter du malgache, ces trois points ne sont pas anecdotiques :
ils se traduisent en coût, en latence et en taux d'échec. Nous n'avons pas
trouvé de mesure publiée portant spécifiquement sur le malgache dans les
modèles commerciaux que nous employons ; c'est une lacune que la partie 3
signale parmi les limites de notre évaluation.

### Reproductibilité et dépendance au fournisseur

Les modèles commerciaux sont servis derrière une interface distante dont les
versions évoluent, dont la disponibilité n'est pas garantie et dont le
comportement peut varier à paramètres identiques. Une expérimentation
scientifique menée sur de tels modèles n'est reproductible que si l'on
journalise l'identifiant exact du modèle, la version de l'invite et les
paramètres d'appel, et si l'on conserve les sorties obtenues.

### Biais et effets sociaux

Bender, Gebru, McMillan-Major et Shmitchell ont formulé une critique
d'ensemble des grands modèles de langue, portant notamment sur la composition
opaque des corpus, la reproduction de stéréotypes et l'illusion de
compréhension qu'ils produisent [@bender2021parrots]. Cette critique est
particulièrement contraignante pour l'un de nos deux cas d'usage : un système
qui classe des candidatures agit sur l'accès à l'emploi, et la charge de la
preuve pèse sur celui qui le déploie.

## Ce que cela implique pour notre conception

Chacune des limites qui précèdent se traduit, dans le dépôt de ce projet, par
une décision d'architecture documentée. Nous les énonçons ici brièvement ;
elles sont justifiées en détail au chapitre 4 et mises en œuvre au chapitre 5.

**L'instabilité des modèles impose de ne jamais nommer un modèle dans le
code.** Le dépôt n'expose que des alias fonctionnels (`sales.route`,
`sales.synthesize`, `hr.extract`, `hr.score`), résolus par un fichier de
configuration unique qui déclare pour chacun un modèle principal et des replis
(décision ADR-011). Changer de fournisseur est une modification de
configuration ; comparer deux modèles sur une même tâche est une
expérimentation possible sans toucher au code.

**L'écart de coût entre modèles légers et modèles forts justifie un routage
par sous-tâche.** Dans notre agent commercial, le premier appel, qui ne fait
que choisir des outils, part sur un alias léger ; la rédaction finale part sur
un alias fort. La chaîne de présélection applique la même séparation entre
la structuration d'un curriculum vitæ et sa notation.

**L'hallucination impose l'ancrage et la citation.** Aucun de nos deux agents
ne répond de mémoire : l'agent commercial ne parle que de ce que ses outils ont
effectivement lu et cite les identifiants des enregistrements concernés ;
l'agent de présélection doit joindre à chaque note une preuve extraite du
document évalué. Le harnais d'évaluation vérifie que ces preuves figurent
réellement dans le texte source.

**L'usage inégal du contexte impose un budget explicite.** Un module
déterministe, écrit en code et non en invite, classe les informations par
priorité et tronque à un budget de jetons fixé par la configuration ; le
nombre de jetons retenus et le nombre d'éléments écartés sont journalisés
(décision ADR-008).

**Le caractère non fiable des sorties impose la validation et la
confirmation.** Les arguments produits par le modèle sont validés contre un
schéma avant toute exécution, et toute action d'écriture dans le logiciel
client est soumise à une confirmation humaine explicite avant d'être exécutée
(décision ADR-009).

**Le caractère non borné des boucles d'agent impose une limite.** Notre
exécution d'agent est plafonnée à six appels au modèle, et l'atteinte de cette
limite est un état de sortie explicite du système, mesuré par le harnais
d'évaluation.

**L'injection indirecte de consigne impose de traiter les documents comme des
données hostiles.** Le texte d'un curriculum vitæ est délimité, la sortie
attendue est contrainte par un schéma, et une suite d'évaluation dédiée vérifie
que des documents porteurs d'une instruction malveillante ne modifient pas la
note attribuée.

**Le besoin de reproductibilité impose la traçabilité.** Chaque appel au
modèle est journalisé avec son identifiant de trace, son organisation, son
alias, la version de l'invite employée, le nombre de jetons, la latence et le
coût. Les invites elles-mêmes sont des fichiers versionnés du dépôt, jamais
des enregistrements de base de données (décision ADR-010) : une expérience du
chapitre 8 peut donc être rejouée contre une version antérieure d'invite.

**Le risque de biais impose la mesure.** La partie 3 du mémoire consacre une
part de son protocole à cette question, avec les limites que nous y
reconnaissons : un jeu de données synthétique et un annotateur unique ne
permettent pas de conclure sur l'équité d'un système en production.
