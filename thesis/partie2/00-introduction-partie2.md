# Introduction de la partie 2

La première partie a établi ce qu'un grand modèle de langue sait faire, ce
qu'il ne sait pas faire, et ce que des équipes commerciales et de recrutement
attendent réellement d'un assistant logiciel. Elle s'est close sur une liste de
contraintes de conception, présentées comme des conséquences des limites
documentées des modèles plutôt que comme des préférences techniques.

Cette deuxième partie décrit le système qui en est sorti. Elle porte sur un
dépôt de code existant, déployé sur un serveur, et non sur une architecture
souhaitée : chaque affirmation des trois chapitres qui suivent renvoie à un
fichier, à une table, à une route ou à une unité de service que le lecteur peut
ouvrir. Les figures obéissent à la même règle. Huit d'entre elles ne sont pas
dessinées mais dérivées du dépôt par un script : le diagramme des tables est
produit à partir des métadonnées de l'outil de correspondance objet-relationnel,
le graphe des dépendances entre modules à partir d'une analyse syntaxique des
importations, la carte des alias de modèles à partir du fichier de
configuration, l'inventaire des outils à partir des objets qui les déclarent.
Une figure fausse est ainsi une figure qui ne compile plus, et non une figure
qu'un relecteur doit déceler.

Les vingt-huit figures de la partie se répartissent en deux familles, toutes
deux reproductibles. Les vingt schémas sont écrits en notation Mermaid dans
`thesis/figures/src/` et rendus en PDF vectoriel par `thesis/figures/render.sh`,
qui engendre au passage les huit sources dérivées du dépôt avant de compiler
l'ensemble. Les huit captures d'écran proviennent de l'application réellement
lancée sur ses ports fixes, prises par `thesis/figures/captures/capturer.mjs`
après une préparation de compte idempotente ; chaque campagne écrit un
manifeste horodaté portant la révision du dépôt capturée, et les légendes
reprennent cette date. Aucune figure de cette partie n'a été dessinée à la
main dans un éditeur graphique.

Le chapitre 4 traite de l'architecture et des choix technologiques. Il prend
pour colonne vertébrale les onze décisions d'architecture consignées dans
`docs/adr/` et les restitue sous la forme qui leur donne leur valeur : le
contexte qui rendait la question ouverte, les options qui étaient réellement
disponibles, la décision prise, et ce qu'elle a coûté. Le chapitre 5 décrit les
agents eux-mêmes : le moteur d'exécution commun, le catalogue d'outils, la
récupération contextuelle de l'agent commercial, la notation de l'agent de
présélection, et la gestion des prompts comme artefacts versionnés. Le
chapitre 6 traite de ce qui relie le système au monde extérieur et au temps :
la connexion au logiciel de gestion commerciale organisation par organisation,
la validation humaine des écritures, et la chaîne de traitement asynchrone.

Ce que cette partie ne fait pas : elle ne mesure rien. Les chiffres de
performance, de qualité et de coût, ainsi que le harnais qui les produit, font
l'objet de la partie 3. Les fragments de code cités ici le sont uniquement
lorsque la prose ne suffit pas à établir un fait, et jamais au-delà d'une
vingtaine de lignes.
