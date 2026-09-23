# Les agents spécialisés : moteur d'exécution, outils, prompts

## Objet et périmètre du chapitre

Le chapitre précédent a décrit la charpente. Celui-ci décrit ce qui tourne
dessus : deux agents conversationnels adossés à un moteur d'exécution unique,
deux traitements de présélection qui appellent les modèles sans passer par ce
moteur, un catalogue d'outils typés, et une manière de gérer les prompts qui
rend les uns et les autres comparables d'une expérience à l'autre. Trois enregistrements de décision y sont traités dans
leur intégralité, parce que c'est ici qu'ils s'appliquent : la récupération
contextuelle sans index vectoriel, la notation candidature par candidature, et
le versionnement des prompts.

Le chapitre progresse du général au particulier. Il commence par le moteur, qui
est commun aux agents conversationnels et tient en un fichier. Il décrit ensuite le
catalogue d'outils et la manière dont les arguments produits par un modèle de
langue sont traités, c'est-à-dire comme des données hostiles. Il traite
ensuite les deux flux applicatifs : l'assistance commerciale, qui va chercher
du contexte structuré dans un logiciel tiers, et la présélection de
candidatures, qui note des documents contre une grille. Il se clôt sur les
prompts et sur ce que leur versionnement rend possible.

Aucune mesure de performance ne figure dans ce chapitre. Les latences, les
coûts et les accords avec l'annotation humaine relèvent de la partie 3 et du
harnais d'évaluation qui les produit.

## Un moteur d'exécution unique, sans cadriciel d'agents

### Ce qu'un agent est, dans ce dépôt

Un agent n'est pas une classe à hériter mais une déclaration. Il se compose
d'un nom, d'un alias de modèle, éventuellement d'un second alias pour la phase
de synthèse, d'un nom de dossier de prompt, d'une liste d'outils,
éventuellement d'un schéma de sortie structurée, et d'un nombre maximal
d'étapes valant six par défaut. Cette structure est immuable et ne contient
aucun comportement, hormis une méthode qui décide quel alias utiliser à une
étape donnée. Le comportement, lui, vit dans une seule fonction, elle aussi
commune à tous les agents.

Il faut lever ici une ambiguïté de vocabulaire, car le mot « agent » désigne
deux choses différentes dans ce mémoire. Au sens du produit, la plateforme
offre deux agents, l'assistant commercial et l'agent de présélection. Au sens
du code, une déclaration d'agent est une structure précise, et le dépôt n'en
compte que trois : l'assistant commercial, le coach, et un agent d'écho qui ne
sert qu'aux tests du moteur. Les traitements de présélection n'en sont pas :
ils n'ont aucun outil à offrir au modèle, puisqu'ils lui soumettent un texte et
en attendent un objet structuré, et ils appellent donc directement la
passerelle décrite au chapitre précédent, sans boucle et sans catalogue. Cette
asymétrie n'est pas un oubli : dérouler une boucle bornée autour d'un appel qui
n'a rien à appeler ajouterait une indirection et aucune capacité. Le moteur
décrit dans les pages qui suivent régit donc les échanges conversationnels ; la
section consacrée à la présélection décrira l'autre chemin.

Ce choix mérite d'être justifié, car il va à l'encontre de la pratique
dominante. Les cadriciels d'agents disponibles offrent des abstractions riches :
chaînes, graphes d'états, mémoires, planificateurs. Le besoin ici est plus
étroit. Les agents qui ont besoin d'outils exécutent tous la même chose : une
boucle qui alterne appel au modèle et exécution d'outils, jusqu'à ce que le
modèle cesse de demander des outils ou qu'une borne soit atteinte. C'est le motif
décrit par la littérature sur le raisonnement entrelacé d'actions
[@yao2023react], et il tient en une fonction d'environ trois cent cinquante
lignes, commentaires compris. Écrire cette fonction plutôt que de l'importer
donne trois choses qu'aucun cadriciel n'aurait données ici : le contrôle exact
du point où une écriture est interceptée, le contrôle exact du contenu des
traces, et l'absence de dépendance à un projet dont les ruptures d'interface
sont fréquentes.

### La boucle

La figure \ref{fig:boucle} décrit la fonction d'exécution. Elle se lit du haut
vers le bas, et tous les chemins de sortie passent par l'écriture des traces.

![Boucle d'exécution d'un agent. La borne porte sur le nombre d'appels au modèle, pas sur le nombre d'outils exécutés.\label{fig:boucle}](figures/out/boucle-runtime.pdf){width=65%}

Le coeur de cette fonction tient en une vingtaine de lignes, reproduites ici
parce que la prose rendrait mal l'ordre exact des gardes, qui est ce qui donne
à la boucle ses propriétés.

```python
while True:
    if pending:                       # reprise après confirmation humaine
        blocked = await _handle_tool_calls(pending, ...)
        if blocked is not None:
            return blocked            # nouvelle confirmation demandée
        pending = []
        has_tool_results = True
        continue                      # sans consommer d'étape LLM

    if llm_steps >= definition.max_steps:
        return StepLimitExceeded(...)

    alias = definition.alias_for_step(has_tool_results)
    llm_steps += 1
    result = await gateway.complete(alias, messages, ctx=..., tools=...)

    if not result.tool_calls:
        return Final(...)             # le modèle n'appelle plus rien
    pending = [dict(c) for c in result.tool_calls]
```

Les points de suspension marquent des arguments et des champs omis pour la
lisibilité ; l'ordre des gardes, lui, est celui du code. L'ensemble de cette
boucle est enveloppé dans une clause de finalisation qui vide le tampon de
traces, ce qui est la raison pour laquelle les trois sorties possibles, et même
une exception non prévue, laissent la même trace en base.

Quatre points de cette boucle demandent un commentaire.

**La borne porte sur les appels au modèle.** La valeur par défaut de six ne
limite pas le nombre d'outils exécutés, mais le nombre d'allers-retours avec le
modèle. Un tour qui demande quatre outils en une seule réponse ne consomme
qu'une étape. Cette définition est la seule qui borne effectivement le coût,
puisque c'est l'appel au modèle qui est facturé. Lorsque la borne est atteinte,
le moteur ne lève pas d'exception : il renvoie un résultat de type dédié, que
l'appelant traduit en message explicite pour l'utilisateur.

**Les résultats sont des types, pas des exceptions.** La fonction renvoie une
valeur qui est soit une réponse finale, soit une demande de confirmation, soit
un dépassement de borne. Cette union est explicite et vérifiée par le contrôle
de types statique : il n'est pas possible d'oublier de traiter la demande de
confirmation, parce que le compilateur de types le signale. C'est la
traduction, dans le code, de l'exigence selon laquelle aucune écriture ne peut
être exécutée sans accord humain.

**Une erreur d'outil retourne au modèle.** Un outil inconnu, des arguments qui
ne passent pas la validation, ou une exception pendant l'exécution ne
remontent pas à l'appelant : ils sont transformés en résultat d'outil textuel
et réinjectés dans la conversation. Le modèle voit donc son erreur et peut la
corriger à l'étape suivante, dans la limite de la borne. Ce choix a une
conséquence mesurable, puisqu'une correction consomme une étape et un appel
facturé ; il a surtout une conséquence de robustesse, puisqu'un nom de champ
mal orthographié par le modèle ne fait pas échouer la requête de
l'utilisateur.

**Les traces sont écrites en une seule transaction, à la fin.** Le composant de
traçage accumule les événements en mémoire et les écrit dans une transaction
unique, dans un bloc d'achèvement qui s'exécute même si la fonction se termine
par une exception. Écrire chaque étape au fil de l'eau aurait multiplié les
allers-retours vers la base pendant que l'utilisateur attend. Un observateur
optionnel permet néanmoins de diffuser les étapes en temps réel vers
l'interface, sans passer par la base : c'est ce mécanisme qui alimente le flux
d'événements de l'agent commercial.

Les événements tracés portent un type : appel au modèle, exécution d'outil,
erreur d'outil, demande de confirmation, réponse finale, dépassement de borne,
et refus. Ce dernier type, qui correspond au cas où l'utilisateur envoie un
nouveau message sans avoir confirmé une écriture en attente, est émis par le
moteur mais absent de la liste documentée dans la déclaration de la table : un
écart mineur entre le code et son commentaire, relevé ici parce que la
relecture croisée l'a trouvé.

### L'escalade d'alias

Un agent peut déclarer deux alias. Le premier sert tant qu'aucun outil n'a
répondu, le second dès qu'un résultat d'outil est disponible. La règle est
déterministe et tient en trois lignes : elle ne dépend d'aucune heuristique et
ne consulte pas le modèle. L'agent commercial l'utilise avec un modèle léger
pour le choix d'outils et un modèle fort pour la rédaction du briefing ;
l'agent de coaching ne déclare qu'un seul alias, car son travail est un
jugement rédactionnel dès le premier appel.

L'intérêt de cette règle est économique autant que qualitatif. Le choix d'un
outil parmi huit, à partir d'une question courte, est une tâche que les modèles
légers réussissent ; la rédaction d'un briefing commercial à partir de données
structurées ne l'est pas. Séparer les deux phases permet de payer le tarif fort
une seule fois par tour.

## Les outils : typage, contexte et confirmation

### Déclaration et schéma

Un outil est une structure immuable portant un nom, une description destinée au
modèle, une classe de validation pour ses arguments, un drapeau indiquant s'il
écrit, une fonction d'exécution, et éventuellement une fonction de prévisualisation
en français. La conversion vers le format attendu par les modèles est
mécanique : le schéma d'arguments est engendré à partir des annotations de
types, avec les descriptions de champs telles qu'elles sont écrites dans le
code. Il n'existe donc aucune copie manuelle d'un schéma dans un prompt, et
aucune possibilité de divergence entre ce que le modèle croit pouvoir envoyer
et ce que le code accepte.

La figure \ref{fig:outils} présente le catalogue de l'agent commercial. Elle
est produite en important les objets d'outils eux-mêmes et en lisant les champs
de leurs classes d'arguments ; elle vérifie au passage qu'aucun de ces champs
ne porte un identifiant d'organisation ni un élément d'authentification, et
échouerait si c'était le cas.

![Catalogue des outils de l'agent commercial, engendré depuis les objets qui les déclarent. Le contexte de requête n'est pas un argument d'outil : il est fourni par le serveur.\label{fig:outils}](figures/out/catalogue-outils.pdf){width=80%}

### Le contexte ne vient jamais du modèle

C'est la contrainte la plus importante de tout le système, et elle est
structurelle plutôt que défensive. La fonction d'exécution d'un outil reçoit
deux arguments : les arguments validés, produits par le modèle, et un contexte
de requête, produit par le serveur. Ce contexte porte l'organisation,
l'utilisateur, le rôle, l'identifiant de trace et, pendant l'exécution d'un
outil, l'identifiant de l'appel. Aucune classe d'arguments d'outil ne déclare
de champ d'organisation ; il n'y a donc rien à valider, rien à filtrer et rien
à oublier de filtrer.

Les identifiants d'accès au logiciel client suivent la même règle mais par un
chemin plus long. L'outil ne les reçoit pas : il demande un client au moyen
d'une fabrique, qui lit l'intégration de l'organisation dans la base, sous
contexte d'isolation, et déchiffre les jetons. Un modèle qui produirait une
adresse d'instance ou un jeton dans ses arguments verrait cet argument rejeté
par la validation, puisqu'il n'existe pas dans le schéma.

Cette discipline répond à une classe d'attaques documentée, celle de
l'injection indirecte de consignes : un contenu tiers, ici une fiche de compte
ou un curriculum vitæ, peut contenir des instructions destinées au modèle
[@greshake2023indirect]. La parade retenue n'est pas de détecter ces
instructions mais de faire en sorte qu'obéir ne serve à rien : quelle que soit
la consigne qu'un document réussit à faire exécuter, elle ne peut pas changer
l'organisation dont les données sont lues.

### La validation, puis la confirmation, dans cet ordre

L'ordre des opérations dans la boucle est important et il est délibéré. Les
arguments sont validés avant toute décision sur l'exécution ; c'est seulement
ensuite que le caractère d'écriture est examiné. Un outil d'écriture dont les
arguments sont invalides produit donc une erreur renvoyée au modèle, et non une
demande de confirmation portant des arguments incohérents. L'utilisateur ne se
voit jamais proposer de confirmer une action mal formée.

Lorsque l'outil écrit et que son identifiant d'appel ne figure pas dans
l'ensemble des confirmations, le moteur s'arrête et renvoie une demande de
confirmation contenant le nom de l'outil, ses arguments et une phrase française
engendrée par la fonction de prévisualisation. Le détail du mécanisme, y
compris l'idempotence de la reprise, est traité au chapitre 6 avec la décision
ADR-009 dont il est l'application.

## Le flux commercial : récupération contextuelle structurée

### La décision ADR-008

**Contexte.** L'assistant commercial doit répondre à des questions du type
« prépare mon point de demain avec tel client » à partir des données du
logiciel de gestion de la relation client de l'organisation. Ces données sont
déjà structurées : comptes, contacts, opportunités, activités, cas de support.
La question est de savoir comment les amener jusqu'au modèle.

**Options.** L'approche par défaut de la littérature applicative consiste à
indexer les enregistrements sous forme de vecteurs et à récupérer les plus
proches de la question [@lewis2020rag]. Elle a des qualités réelles sur des
corpus non structurés et elle est abondamment outillée [@gao2024ragsurvey].
L'alternative consiste à laisser le modèle choisir des requêtes typées parmi un
catalogue, à exécuter ces requêtes telles quelles, et à mettre en forme les
résultats par du code.

**Décision.** Pas d'index vectoriel. Le modèle choisit des outils, les outils
exécutent des requêtes paramétrées dont la forme est écrite dans le code, et un
module déterministe met en forme les résultats sous un budget de jetons. Le
raisonnement est le suivant. Une recherche par similarité sur des données déjà
structurées introduit une approximation là où une jointure donne la réponse
exacte. Elle introduit aussi une latence d'indexation, donc un décalage entre
l'enregistrement et sa copie indexée, ce qui est inacceptable pour des données
dont la fraîcheur est la valeur principale : un commercial qui prépare un appel
veut l'état d'aujourd'hui, pas celui de la dernière réindexation. Elle rend
enfin l'explication difficile, alors qu'une requête nommée est lisible par un
humain.

**Conséquences.** Le catalogue d'outils devient une surface à maintenir : toute
question qui ne se ramène pas à une requête prévue reste sans réponse. C'est un
coût assumé, et l'inverse du compromis habituel, où un index répond mal à tout
plutôt que bien à peu. La décision est explicitement datée : elle doit être
réévaluée si des données non structurées entrent dans le périmètre, des
transcriptions d'appels par exemple, pour lesquelles l'argument de la donnée
déjà structurée tomberait.

### L'outil composite

Le catalogue comporte quatre outils de lecture élémentaires et un outil
composite. Ce dernier est le cœur du flux. En un seul appel, il résout un
compte à partir d'un identifiant ou d'un nom, puis exécute quatre requêtes :
les contacts du compte, ses opportunités ouvertes triées par date de clôture,
ses cas de support ouverts, et ses activités sur une fenêtre paramétrable.
Regrouper ces requêtes en un outil unique est une décision de latence : le
modèle n'a besoin que d'un aller-retour pour obtenir tout ce qu'il faut pour un
briefing, là où quatre outils séparés auraient coûté quatre étapes, donc quatre
appels facturés et quatre fois le temps d'attente.

Toutes les lectures passent par un cache de courte durée, indexé par
organisation, nom d'outil et empreinte des arguments. La durée est volontairement
faible : il s'agit d'absorber les répétitions à l'intérieur d'un même tour de
conversation, pas de servir des données périmées.

Les paramètres textuels sont échappés avant d'entrer dans une requête, et les
projections de champs sont des constantes du code. Le modèle choisit l'outil et
fournit des valeurs ; il n'écrit jamais de requête.

### La construction de contexte sous budget

Les résultats bruts ne sont pas envoyés au modèle. Ils passent par une fonction
de construction de contexte, entièrement déterministe, dont la
figure \ref{fig:contexte} décrit le fonctionnement.

![Construction du contexte commercial sous budget de jetons. L'ordre des sections est fixé par le code ; le modèle n'y participe pas.\label{fig:contexte}](figures/out/context-builder.pdf){width=54%}

Le principe est un remplissage par priorité. L'en-tête du compte est toujours
écrit et n'est jamais tronqué. Viennent ensuite, dans un ordre fixé par le
code, les opportunités ouvertes, les activités des trente derniers jours, les
contacts, les cas ouverts, et enfin les activités plus anciennes. Après chaque
élément ajouté, le texte assemblé est mesuré dans son intégralité ; dès que le
plafond est atteint, la section en cours s'arrête et le nombre d'éléments
écartés est comptabilisé. Une ligne finale indique à l'utilisateur, et au
modèle, combien d'éléments ont été omis faute de place. Le plafond retenu est
le budget diminué d'une réserve, elle-même calculée en mesurant la longueur de
cette ligne finale : la note d'omission ne peut donc pas faire dépasser le
budget qu'elle annonce.

Le comptage utilise le découpage en jetons de la famille de modèles employée,
avec un repli par estimation à partir du nombre de caractères si la
bibliothèque n'est pas disponible, ce repli étant journalisé. Le budget lui-même
est un paramètre de configuration, valant trois mille jetons par défaut ; il
n'est jamais choisi par le modèle.

Trois propriétés découlent de ce dispositif. La première est la reproductibilité :
à données identiques, le texte envoyé au modèle est identique, ce qui est la
condition pour qu'une expérience du chapitre 8 signifie quelque chose. La
deuxième est la mesurabilité : le nombre de jetons utilisés et le nombre
d'éléments écartés sont renvoyés à l'outil, qui les transmet au modèle, et
journalisés avec l'identifiant du compte. La troisième est une précaution
documentée : placer l'information la plus importante au début plutôt qu'au
milieu d'un long contexte, parce que la qualité de l'attention des modèles
dépend de la position [@liu2024lost].

La figure \ref{fig:seq-assistant} résume la séquence complète d'un tour.

![Séquence d'un tour de l'agent commercial. L'escalade d'alias est visible entre les étapes 3 et 11.\label{fig:seq-assistant}](figures/out/sequence-assistant.pdf){width=95%}

L'interface expose deux variantes de l'envoi d'un message : une version
synchrone qui rend la réponse complète, et une version en flux d'événements qui
diffuse chaque étape au fur et à mesure. La seconde utilise l'observateur
mentionné plus haut. La figure \ref{fig:ecran-sales} montre l'écran
correspondant.

![Écran de l'agent commercial, capture du 22 septembre 2026 sur l'instance de développement.\label{fig:ecran-sales}](figures/captures/out/ecran-agent-commercial.png){width=95%}

### L'agent de coaching

Un second agent commercial existe, dont l'objet est différent : il évalue un
texte écrit par un commercial, compte rendu d'appel, courriel de relance ou
script, et rend un retour structuré. Sa particularité est que sa grille est
fermée. Cinq critères sont déclarés dans le code, dans un ordre qui fait foi :
découverte des besoins, gestion des objections, proposition de valeur,
prochaine étape, ton et concision. La classe de sortie impose la présence des
cinq, sous peine de rejet, et les réordonne selon la déclaration. Un modèle qui
en oublierait un, ou en inventerait un sixième, produirait une réponse invalide
et déclencherait la reprise décrite plus loin.

Le texte évalué est encadré par des délimiteurs, et les occurrences de ces
délimiteurs présentes dans le texte de l'utilisateur sont neutralisées avant
l'encadrement. C'est une défense simple contre la tentative, par un texte, de
se faire passer pour une consigne. Le prompt la double d'une instruction
explicite.

Le coach dispose de deux outils seulement : l'outil composite de contexte, et
l'outil de journalisation d'appel. Le second est un outil d'écriture ; si le
modèle décide de l'appeler de lui-même, l'interface de programmation refuse la
requête avec un code d'erreur dédié plutôt que de propager une demande de
confirmation, parce que la procédure prévue veut que la proposition d'écriture
soit construite par la plateforme à partir du retour structuré, et non par le
modèle. C'est une restriction volontaire du pouvoir d'initiative de l'agent.

![Écran du coach commercial, capture du 22 septembre 2026 sur l'instance de développement.\label{fig:ecran-coach}](figures/captures/out/ecran-coach.png){width=95%}

## Le flux de présélection : noter contre une grille

### La décision ADR-007

**Contexte.** Une campagne de présélection met en regard une offre d'emploi et
un lot de candidatures, jusqu'à plusieurs centaines. La question est de savoir
si le modèle doit voir toutes les candidatures ensemble ou chacune séparément.

**Options.** Un prompt unique contenant l'offre et l'ensemble des candidatures
permet au modèle de comparer directement, ce qui est le mode de jugement
naturel d'un recruteur. Une notation indépendante par candidature interdit la
comparaison directe mais rend chaque unité de travail petite et reprenable.

**Décision.** Chaque candidature est notée seule, contre la grille issue de
l'offre. Quatre arguments concourent. Le parallélisme : cinq cents candidatures
se répartissent sur autant de tâches indépendantes, ce qu'un prompt unique
interdit. La reprise : un échec sur une candidature coûte une nouvelle tentative
sur cette candidature, et non sur le lot. L'absence de biais de position :
l'ordre dans lequel les candidatures arrivent au modèle n'influence pas leur
note, ce qui n'est pas vrai d'une liste. L'application uniforme de la grille,
enfin : chaque candidature affronte exactement le même texte de critères.

**Conséquences.** Le jugement relatif est perdu. Une passe de calibration
comparative sur les meilleurs profils est donc conservée en option, et elle est
implémentée : elle trie à nouveau les premiers du classement au moyen d'un alias
dédié, sans jamais modifier les notes, en conservant le rang antérieur et la
justification du changement. Elle est désactivée par défaut, la valeur du
paramètre étant nulle dans la configuration livrée. Cette désactivation n'est
pas un oubli : elle fait de la calibration une variable expérimentale, dont
l'apport pourra être mesuré au chapitre 8 en comparant deux rapports qui ne
diffèrent que par ce paramètre.

### De l'offre à la grille

La grille n'est pas écrite à la main par le recruteur, ni produite par le
modèle sans contrôle. Le parcours comporte trois temps. Le recruteur saisit une
offre ; un appel au modèle, sous l'alias léger, propose entre cinq et huit
critères, chacun avec un intitulé, une pondération de un à cinq, une
description et un drapeau indiquant s'il est éliminatoire ; le recruteur édite
cette proposition et la valide, ce qui fait passer l'offre à l'état prêt. Tant
que cet état n'est pas atteint, aucune campagne ne peut être lancée : la
vérification est faite côté serveur et renvoie un conflit explicite.

Les contraintes de forme sont portées par le schéma de validation et non par le
prompt : nombre de critères borné, pondération bornée, intitulés uniques à la
casse près. Un modèle qui produirait neuf critères, ou deux critères de même
nom, verrait sa réponse rejetée.

![Écran d'édition de la grille de critères, capture du 22 septembre 2026 sur l'instance de développement.\label{fig:ecran-grille}](figures/captures/out/ecran-hr-grille.png){width=95%}

### Extraction, profil, notation

Le traitement d'une candidature comporte trois étapes, dont une seule n'utilise
pas de modèle de langue.

L'extraction de texte lit le fichier déposé, au format PDF ou au format
bureautique, et en tire du texte brut. Elle ne fait appel à aucun modèle. Les
tableaux des documents bureautiques sont extraits ligne à ligne, parce que
beaucoup de curriculum vitæ y rangent les dates et les intitulés de poste. Le
texte est normalisé, puis tronqué à quarante mille caractères. Un document
valide mais dépourvu de texte, c'est-à-dire une image numérisée, produit une
erreur distincte des erreurs de lecture : la candidature passe à un état qui
signale le besoin d'une reconnaissance optique de caractères, laquelle n'est
pas implémentée et figure parmi les perspectives.

La structuration produit un profil : intitulé, années d'expérience,
compétences, expériences avec leurs faits saillants, formations, langues,
certifications, localisation. Elle emploie l'alias léger, puisqu'il s'agit de
remettre en forme une information présente.

La notation emploie l'alias fort et produit, pour chaque critère de la grille,
une note de zéro à cinq, une preuve citée du document, et le cas échéant une
mention de ce qui manque. La classe de sortie impose au moins un critère évalué
et une valeur de confiance entre zéro et un. Elle ne contient délibérément pas
de note globale.

### Le modèle décrit, le code décide

C'est le principe directeur de tout le flux, et il est visible dans la
figure \ref{fig:notation}.

![De l'offre au classement. Le modèle produit des appréciations par critère ; l'agrégation, le caractère éliminatoire et la note globale sont calculés par le code.\label{fig:notation}](figures/out/notation-grille.pdf){width=63%}

Après la réponse du modèle, une fonction d'alignement confronte les critères
évalués à la grille du recruteur. Un critère de la grille absent de la réponse
reçoit la note zéro, avec une mention explicite indiquant qu'aucune preuve n'a
été trouvée ; un critère présent dans la réponse mais absent de la grille est
écarté. La liste des critères éliminatoires non satisfaits est recalculée par
le code à partir des notes, avec un seuil, et non reprise de la réponse du
modèle. La note globale est ensuite calculée : zéro si un critère éliminatoire
échoue, sinon la somme des notes pondérées ramenée sur cent.

Ce dispositif a une propriété qui compte pour la suite du mémoire : la grille
du recruteur fait foi. Un modèle qui omet un critère ne fait pas disparaître ce
critère du calcul, il produit une note nulle et une explication. Un modèle qui
en invente un n'influence pas le résultat. Le pouvoir laissé au modèle se
limite à l'appréciation et à la preuve ; la décision arithmétique appartient au
code, et elle est donc déterministe, auditable et testable sans appeler de
modèle.

Le classement final est recalculé depuis la base et non depuis les valeurs
retournées par les tâches, avec un ordre de tri à trois clés : note globale
décroissante, confiance décroissante, puis identifiant de candidature. La
troisième clé n'est pas décorative : sans elle, deux candidatures de même note
et de même confiance se classeraient selon l'ordre d'arrivée des messages,
c'est-à-dire de façon non reproductible.

![Classement d'une campagne de présélection, capture du 22 septembre 2026 sur l'instance de développement.\label{fig:ecran-classement}](figures/captures/out/ecran-hr-classement.png){width=95%}

### Le modèle de données de la présélection

La figure \ref{fig:schema-rh} présente les quatre tables du module, dérivées
des classes réellement déclarées.

![Modèle de données de la présélection, dérivé des classes SQLAlchemy.\label{fig:schema-rh}](figures/out/schema-rh.pdf){width=55%}

Une contrainte d'unicité porte sur le couple formé de la campagne et de la
candidature. Ce n'est pas une précaution ornementale : c'est le filet qui
garantit que deux exécutants qui rejoueraient la même tâche ne peuvent pas
produire deux notations. Le chapitre 6 décrit le reste du dispositif
d'idempotence, dont cette contrainte est le dernier recours.

Le chemin du fichier déposé est stocké, mais jamais exposé par l'interface de
programmation. Les fichiers vivent hors du dépôt, dans une arborescence dont
chaque niveau est créé avec des droits restreints, sous un chemin composé de
l'organisation, de l'offre et d'un identifiant tiré au hasard. Le type réel du
fichier est déterminé par ses premiers octets et non par l'extension ou par
l'en-tête annoncé par le navigateur.

## Les prompts comme artefacts versionnés

### La décision ADR-010

**Contexte.** Un prompt est le paramètre le plus sensible d'un système fondé
sur un modèle de langue, et le plus facile à modifier sans trace. Une
expérience dont on ne sait pas quel prompt elle a employé ne prouve rien.

**Options.** Stocker les prompts en base permet de les modifier sans
redéploiement, au prix de leur sortie du champ de la revue de code. Les écrire
dans le code les met sous revue mais rend les différences illisibles dans une
chaîne de caractères longue. Les écrire dans des fichiers versionnés du dépôt
concilie les deux.

**Décision.** Un prompt est un fichier `prompts/<agent>/v<N>.md`. Une
modification crée un nouveau fichier de numéro supérieur, jamais un écrasement.
Le chargeur retient par défaut la version la plus élevée, et retourne à la fois
le texte et le numéro ; ce numéro est inscrit dans la ligne de traçage de
chaque appel, et, pour la présélection, également dans le résultat de notation
et dans l'offre pour la grille.

**Conséquences.** Le dossier s'allonge et ne se nettoie pas. C'est le prix à
payer, et il est faible : la figure \ref{fig:prompts} montre l'état du dépôt à
la date de rédaction.

![Prompts versionnés présents dans le dépôt, avec le nombre de mots de chaque version et celle que le chargeur retient.\label{fig:prompts}](figures/out/versions-prompts.pdf){width=95%}

Sept dossiers de prompts existent, totalisant douze versions. Trois d'entre
eux ont connu plusieurs révisions. Le prompt de l'assistant commercial en est à sa
quatrième version, passant de deux cent quatre-vingt-trois à quatre cent
quarante et un mots ; les ajouts successifs portent sur la discipline de
citation des identifiants d'enregistrements et sur le traitement des données du
logiciel client comme données et non comme consignes. Le prompt de notation en
est à sa deuxième version, qui ajoute une section de calibrage entière :
l'instruction que la mention d'une technologie dans un curriculum vitæ n'est
pas une preuve d'usage, et un plafond de note correspondant. C'est exactement
le genre de changement dont l'effet doit être mesuré plutôt que supposé, et que
le versionnement rend mesurable, puisque les deux versions coexistent dans le
dépôt et que chaque notation porte le numéro de celle qui l'a produite.

Une précision de nommage. Les documents de cadrage donnaient comme exemple un
dossier nommé d'après la tâche, avec un tiret bas. Le dépôt utilise le nom de
l'agent avec un point, ce qui aligne les noms de dossiers de prompts sur les
noms d'agents et sur les valeurs de la colonne d'agent de la table de traçage.
L'écart est sans conséquence, mais il est réel et signalé ici.

### La sortie structurée et sa reprise

Les prompts qui demandent une sortie structurée ne sont pas seuls à la garantir.
La passerelle ajoute, lorsqu'un schéma de sortie est demandé, un message
contenant le schéma engendré à partir de la classe de validation, avec une
consigne de ne répondre qu'avec un objet conforme. La réponse est ensuite
analysée, après retrait d'un éventuel encadrement en bloc de code, et validée.
En cas d'échec, un unique nouvel essai est fait, en renvoyant au modèle sa
propre réponse et la première erreur de validation ; un second échec lève une
erreur dédiée.

Ce mécanisme appelle une remarque de fidélité. Il n'emploie pas les modes de
sortie structurée natifs des fournisseurs, qui contraignent le décodage. Le
choix rend la passerelle indépendante des capacités du fournisseur, au prix
d'un risque de réponse mal formée que la reprise absorbe. C'est un compromis
qui sera réexaminé si la mesure montre un taux de reprise non négligeable.

## Ce que cela implique pour l'évaluation

Le chapitre a établi trois points dont dépend la mesurabilité du système. Le
premier est la séparation entre ce que le modèle produit et ce que le code
décide : une note globale, un classement, un caractère éliminatoire et un
budget de contexte sont calculés par du code déterministe, donc testables sans
appeler de modèle et reproductibles à données égales. Le deuxième est la
traçabilité fine : chaque appel porte son alias, sa version de prompt, ses
jetons et sa latence, et chaque étape d'agent porte son type, son outil et son
résumé, de sorte qu'une exactitude de sélection d'outil se mesure par une
requête. Le troisième est la coexistence des versions de prompts, qui fait
d'un changement de formulation une variable expérimentale explicite plutôt
qu'un événement invisible entre deux mesures.
